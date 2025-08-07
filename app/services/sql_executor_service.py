import logging
import sqlalchemy
from typing import List, Optional, TYPE_CHECKING, Dict, Any
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.services.proxy_service import ProxyService
from app.utils.text import truncate_words

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class SQLExecutorService:
    """
    Ejecuta SQL directamente con SQLAlchemy, útil para introspección (inspector)
    o consultas ad-hoc. Si se proporciona proxy_id y tu ProxyService expone
    get_sql_config(proxy_id), lo usa; en caso contrario, crea el engine a partir
    de la conexión de DatabaseService (database_id).
    """

    def __init__(self, factory: "ServiceFactory"):
        self.db = factory.db
        self.user = factory.user
        self.factory = factory
        self.proxy_service: ProxyService = factory.get_proxy_service()
        logger.info("[SQLExecutorService] 🧠 Inicializado para user_id=%s", self.user.id)

    # ─────────────────────────────────────────────
    #   Engine helpers
    # ─────────────────────────────────────────────
    def _get_engine_direct(self, database_id: int) -> Engine:
        db_service = self.factory.get_database_service()
        record = db_service.get_record(database_id)
        if not record:
            logger.error("[SQLExecutorService] ❌ DB id=%s no encontrada para el usuario", database_id)
            raise ValueError("Database connection not found")
        engine = db_service.build_sqlalchemy_engine(record)
        logger.debug("[SQLExecutorService] 🔗 Engine directo construido para DB id=%s", database_id)
        return engine

    def _get_engine_via_proxy(self, proxy_id: int) -> Engine:
        """
        Espera que ProxyService.get_sql_config devuelva algo como:
        {
            "dsn" | "url" | "base_url": "postgresql+psycopg2://user:pass@host/db",
            "connect_args": { ... }  # opcional
        }
        """
        if not hasattr(self.proxy_service, "get_sql_config"):
            logger.error("[SQLExecutorService] ❌ ProxyService no implementa get_sql_config")
            raise RuntimeError("Proxy SQL no soportado por ProxyService")

        cfg: Dict[str, Any] = self.proxy_service.get_sql_config(proxy_id)
        if not cfg:
            logger.error("[SQLExecutorService] ❌ Proxy ID %s no válido o no encontrado", proxy_id)
            raise ValueError("Proxy no válido o no encontrado")

        dsn = cfg.get("dsn") or cfg.get("url") or cfg.get("base_url")
        if not dsn:
            logger.error("[SQLExecutorService] ❌ Config de proxy sin DSN/URL")
            raise ValueError("Config de proxy inválida: falta DSN/URL")

        connect_args = cfg.get("connect_args") or {}
        engine = create_engine(dsn, connect_args=connect_args)
        logger.debug("[SQLExecutorService] 🔗 Engine via proxy creado (proxy_id=%s)", proxy_id)
        return engine

    def _get_engine(self, database_id: int, proxy_id: Optional[int]) -> Engine:
        return self._get_engine_via_proxy(proxy_id) if proxy_id else self._get_engine_direct(database_id)

    # ─────────────────────────────────────────────
    #   SQL execution (+ traducción SHOW TABLES)
    # ─────────────────────────────────────────────
    def _translate_sql_if_needed(self, engine: Engine, sql: str) -> str:
        """Traduce 'SHOW TABLES' a la sintaxis del dialecto si hace falta."""
        try:
            dialect_name = engine.dialect.name.lower()
        except Exception:
            dialect_name = "unknown"

        sql_upper = sql.strip().upper()
        translated_sql = sql

        if sql_upper == "SHOW TABLES":
            if dialect_name in ("postgresql", "postgres"):
                translated_sql = (
                    "SELECT table_name "
                    "FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                    "ORDER BY table_name;"
                )
            elif dialect_name in ("sqlite",):
                translated_sql = (
                    "SELECT name AS table_name "
                    "FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name;"
                )
            elif dialect_name in ("mssql", "sqlserver"):
                translated_sql = "SELECT name AS table_name FROM sys.tables ORDER BY name;"
            # mysql/mariadb sí soportan SHOW TABLES tal cual

            logger.debug(
                "[SQLExecutorService] 🔀 Dialecto=%s → SQL traducido: %s",
                dialect_name, translated_sql
            )

        return translated_sql

    def execute_sql(self, database_id: int, sql: str, proxy_id: Optional[int] = None) -> List[dict]:
        logger.info(
            "[SQLExecutorService] ▶ Ejecutando SQL para DB %s: %s",
            database_id, truncate_words(sql, 20)
        )
        engine = self._get_engine(database_id, proxy_id)

        try:
            translated_sql = self._translate_sql_if_needed(engine, sql)
            with engine.connect() as conn:
                if translated_sql.strip().lower().startswith("select"):
                    result = conn.execute(sqlalchemy.text(translated_sql))
                    rows = [dict(row._mapping) for row in result]
                    logger.info("[SQLExecutorService] ✅ SELECT ejecutado, %d filas", len(rows))
                    return rows
                else:
                    res = conn.execute(sqlalchemy.text(translated_sql))
                    conn.commit()
                    logger.info("[SQLExecutorService] ✅ DML ejecutado, %d filas afectadas", res.rowcount)
                    return [{"rows_affected": res.rowcount}]
        except SQLAlchemyError as e:
            logger.exception("[SQLExecutorService] ❌ Error durante la ejecución SQL: %s", str(e))
            raise RuntimeError("Error ejecutando SQL en la base de datos")

    # ─────────────────────────────────────────────
    #   Introspección / Metadatos
    # ─────────────────────────────────────────────
    def get_table_info(self, database_id: int, proxy_id: Optional[int] = None) -> str:
        """
        Devuelve una descripción detallada de todas las tablas y sus columnas.
        """
        logger.info("[SQLExecutorService] 🧾 Obteniendo info de tablas para DB %s", database_id)
        engine = self._get_engine(database_id, proxy_id)

        try:
            with engine.connect() as conn:
                inspector = sqlalchemy.inspect(conn)
                tables = inspector.get_table_names()
                lines: List[str] = []
                for table in tables:
                    columns = inspector.get_columns(table)
                    col_info = ", ".join([f"{col['name']} ({col['type']})" for col in columns])
                    lines.append(f"Tabla {table}: {col_info}")
                result = "\n".join(lines)
                logger.info("[SQLExecutorService] ✅ Info obtenida de %d tablas", len(tables))
                return result
        except SQLAlchemyError as e:
            logger.exception("[SQLExecutorService] ❌ Error inspeccionando la base de datos: %s", str(e))
            raise RuntimeError("Error obteniendo información de las tablas")

    def list_tables(self, database_id: int, proxy_id: Optional[int] = None) -> List[str]:
        """
        Devuelve una lista simple con los nombres de las tablas.
        """
        logger.info("[SQLExecutorService] 📋 list_tables para DB %s", database_id)
        engine = self._get_engine(database_id, proxy_id)

        try:
            with engine.connect() as conn:
                inspector = sqlalchemy.inspect(conn)
                tables = inspector.get_table_names()
                logger.info("[SQLExecutorService] ✅ %d tablas encontradas", len(tables))
                return tables
        except SQLAlchemyError as e:
            logger.exception("[SQLExecutorService] ❌ Error obteniendo tablas: %s", str(e))
            raise RuntimeError("Error obteniendo lista de tablas")
