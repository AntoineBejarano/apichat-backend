import logging
from typing import List, Optional, TYPE_CHECKING, Union
from uuid import UUID

import sqlalchemy
from sqlalchemy.orm import Session
from langchain_community.utilities.sql_database import SQLDatabase

from app.models.database_model import DatabaseConnection
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
)
from app.services.base_service import BaseService
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri
from .connection_pool_service import ConnectionPoolService

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class DatabaseService(BaseService):
    def __init__(self, factory: "ServiceFactory") -> None:
        super().__init__(factory)
        # Inicializar pool de conexiones
        self.connection_pool = ConnectionPoolService()
        logger.info("[DatabaseService] ✅ Inicializado para user_id=%s", self.user.id)

    # ───────────────── CRUD ─────────────────
    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info("[DatabaseService] ➕ Creando conexión DB para user_id=%s", self.user.id)
        
        # 🔧 NUEVO: Crear conexión con estado inicial "pending"
        connection = DatabaseConnection(
            user_id=self.user.id, 
            schema_status="pending",  # Estado inicial
            **data.model_dump()
        )
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        
        # 🔧 NUEVO: Lanzar generación de schema en background
        self._launch_schema_generation_background(connection.id)
        
        return connection

    def update_connection(self, db_id: Union[int, str, "UUID"], updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info("[DatabaseService] 🔄 Actualizando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database connection not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)

        self.db.commit()
        self.db.refresh(conn)
        return conn

    def delete_connection(self, db_id: Union[int, str, "UUID"]) -> bool:
        logger.warning("[DatabaseService] 🗑️ Eliminando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            return False
        self.db.delete(conn)
        self.db.commit()
        return True

    # ─────────────── Queries / utils ───────────────
    def get_user_databases(self) -> List[DatabaseConnection]:
        logger.info("[DatabaseService] 📥 Listando todas las conexiones DB para user_id=%s", self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == self.user.id)
            .all()
        )

    # alias para compatibilidad con código antiguo
    def list_all_for_user(self) -> List[DatabaseConnection]:
        return self.get_user_databases()

    def get_record(self, db_id: Union[int, str, "UUID"]) -> Optional[DatabaseConnection]:
        logger.debug("[DatabaseService] 🔎 Buscando DB id=%s para user_id=%s", db_id, self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.id == db_id, DatabaseConnection.user_id == self.user.id)
            .first()
        )

    def build_sqlalchemy_engine(self, record: DatabaseConnection):
        uri = build_sqlalchemy_uri(record)
        logger.debug("[DatabaseService] 🛠️ Construyendo engine para URI: %s", uri)
        return sqlalchemy.create_engine(uri)

    def get_sql_database_from_record(self, record: DatabaseConnection) -> Optional[SQLDatabase]:
        try:
            # Usar pool de conexiones en lugar de crear nuevo engine
            engine = self.connection_pool.get_engine(record)
            return SQLDatabase(engine)
        except Exception as exc:
            logger.error("[DatabaseService] ❌ Error creando SQLDatabase: %s", exc)
            return None
    
    def _launch_schema_generation_background(self, db_id: UUID) -> None:
        """
        Lanza la generación de schema en background usando FastAPI BackgroundTasks.
        
        Args:
            db_id: ID de la base de datos recién creada
        """
        try:
            logger.info(f"[DatabaseService] 🚀 Lanzando generación de schema en background para DB {db_id}")
            
            # 🔧 IMPLEMENTACIÓN: Usar FastAPI BackgroundTasks
            # Por ahora, solo logueamos. La implementación completa se hará en el router
            logger.info(f"[DatabaseService] ⏳ Schema generation scheduled for DB {db_id}")
            
        except Exception as e:
            logger.error(f"[DatabaseService] ❌ Error lanzando generación de schema: {e}")

    def get_sql_database_by_id(self, db_id: Union[int, str, "UUID"]) -> Optional[SQLDatabase]:
        logger.info("[DatabaseService] 🔄 Obteniendo SQLDatabase para DB id=%s", db_id)
        record = self.get_record(db_id)
        return self.get_sql_database_from_record(record) if record else None

    def get_sql_instance(self, db_id: Union[int, str, "UUID"]) -> SQLDatabase:
        logger.info("[DatabaseService] 🎯 Obteniendo instancia SQL para DB id=%s", db_id)
        db_instance = self.get_sql_database_by_id(db_id)
        if not db_instance:
            logger.error("[DatabaseService] ❌ No se pudo conectar a la base de datos id=%s", db_id)
            raise ValueError(f"No se pudo conectar a la base de datos {db_id}")
        return db_instance

    # Opcional: soporte de proxy (placeholder). Si no usas proxy real, deja que llame al normal.
    def get_sql_instance_with_proxy(self, db_id: Union[int, str, "UUID"], proxy_config: Optional[dict]) -> SQLDatabase:
        if proxy_config:
            logger.info("[DatabaseService] 🌐 Proxy DB recibido (no-op): %s", proxy_config)
        # Aquí podrías construir el engine usando túneles/SSH/DSN con proxy. Por ahora, directo:
        return self.get_sql_instance(db_id)

    def test_connection_by_id(self, db_id: Union[int, str, "UUID"]) -> bool:
        try:
            record = self.get_record(db_id)
            if not record:
                logger.warning("[DatabaseService] ⚠️ No existe conexión con id=%s", db_id)
                return False

            engine = self.build_sqlalchemy_engine(record)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))

            logger.info("[DatabaseService] ✅ Conexión válida para DB id=%s", db_id)
            return True
        except Exception as e:
            logger.warning("[DatabaseService] ❌ Error al validar DB id=%s: %s", db_id, e)
            return False

    # Mantén este helper para llamadas antiguas desde otros servicios
    def get_sql_instance_from_action(self, action: dict, proxy_config: Optional[dict] = None) -> SQLDatabase:
        db_id = action.get("database_id") or action.get("db_id")
        if not db_id:
            raise ValueError("Acción db_query sin 'database_id'")

        logger.info("[DatabaseService] 📡 Obteniendo SQL instance para acción con DB id=%s", db_id)
        if proxy_config:
            return self.get_sql_instance_with_proxy(db_id, proxy_config)
        return self.get_sql_instance(db_id)

    def execute_sql(self, db_conn: SQLDatabase, sql: str) -> list:
        try:
            logger.info("[DatabaseService] 💾 Ejecutando SQL: %s", sql)
            result = db_conn.run(sql)
            logger.debug("[DatabaseService] ✅ Resultado: %s", result)
            return result
        except Exception as e:
            logger.error("[DatabaseService] ❌ Error al ejecutar SQL: %s", e)
            raise

    def get_dialect_name(self, db_id: int) -> Optional[str]:
            """
            Devuelve el nombre del dialecto (postgresql, mysql, mssql, sqlite, etc.)
            extraído del URI SQLAlchemy.
            """
            record = self.get_record(db_id)
            if not record:
                return None
            uri = build_sqlalchemy_uri(record)  # p.ej. "postgresql+psycopg2://..."
            scheme = uri.split("://", 1)[0]     # "postgresql+psycopg2"
            return scheme.split("+", 1)[0].lower()
    
    def get_connection_pool_stats(self) -> dict:
        """Obtiene estadísticas del pool de conexiones"""
        return self.connection_pool.get_pool_stats()
    
    def clear_connection_pool(self, db_id: Optional[str] = None):
        """Limpia el pool de conexiones"""
        self.connection_pool.clear_pool(db_id)
    
    def health_check_connections(self) -> dict:
        """Realiza health check de todas las conexiones del pool"""
        return self.connection_pool.health_check()