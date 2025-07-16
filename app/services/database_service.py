import logging
from typing import List, Optional, TYPE_CHECKING

import sqlalchemy
from sqlalchemy.orm import Session
from langchain_community.utilities.sql_database import SQLDatabase

from app.models.database_model import DatabaseConnection
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
)
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri
from app.utils.text import truncate_words

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class DatabaseService:
    """Gestión de conexiones y consultas SQL para cada usuario."""

    # ------------------------------------------------------------------
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id
        logger.info("[DatabaseService] Inicializado para user_id=%s", self.user_id)

    # ------------------------------------------------------------------
    # CRUD CONEXIONES ---------------------------------------------------
    # ------------------------------------------------------------------
    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info("[DatabaseService] ➕ Creando conexión DB para user %s", self.user_id)
        connection = DatabaseConnection(user_id=self.user_id, **data.model_dump())
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def update_connection(self, db_id: int, updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info("[DatabaseService] 🔄 Actualizando DB %s", db_id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database connection not found")
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)
        self.db.commit()
        self.db.refresh(conn)
        return conn

    def get_user_databases(self) -> List[DatabaseConnection]:
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == self.user_id)
            .all()
        )

    def get_record(self, db_id: int) -> Optional[DatabaseConnection]:
        return (
            self.db.query(DatabaseConnection)
            .filter_by(id=db_id, user_id=self.user_id)
            .first()
        )

    def delete_connection(self, db_id: int) -> bool:
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database not found")
        self.db.delete(conn)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # INSTANCIAS SQL ----------------------------------------------------
    # ------------------------------------------------------------------
    def _build_sqlalchemy_engine(self, record: DatabaseConnection):
        uri = build_sqlalchemy_uri(record)
        return sqlalchemy.create_engine(uri)

    def get_sql_database_from_record(self, record: DatabaseConnection) -> Optional[SQLDatabase]:
        try:
            engine = self._build_sqlalchemy_engine(record)
            return SQLDatabase(engine)
        except Exception as exc:
            logger.error("[DatabaseService] Error creando SQLDatabase: %s", exc)
            return None

    def get_sql_database_by_id(self, db_id: int) -> Optional[SQLDatabase]:
        record = self.get_record(db_id)
        return self.get_sql_database_from_record(record) if record else None

    def get_sql_instance(self, db_id: int) -> SQLDatabase:
        db_instance = self.get_sql_database_by_id(db_id)
        if not db_instance:
            raise ValueError(f"No se pudo conectar a la base de datos {db_id}")
        return db_instance

    # ------------------------------------------------------------------
    # EJECUCIÓN SQL -----------------------------------------------------
    # ------------------------------------------------------------------
    def execute_sql(self, db_id: int, sql: str) -> List[dict]:
        """Ejecuta una sentencia SQL y devuelve una lista de filas (dict).

        • `SELECT` → usa `SQLDatabase.run` (LangChain) y devuelve filas.
        • `INSERT`/`UPDATE`/`DELETE` → ejecuta directamente y devuelve filas
          afectadas.
        """
        logger.info(
            "[DatabaseService] ▶ Ejecutando SQL en DB %s: %s",
            db_id,
            truncate_words(sql, 18),
        )
        db_instance = self.get_sql_instance(db_id)

        try:
            if sql.strip().lower().startswith("select"):
                result = db_instance.run(sql)
                # langchain puede devolver str; normalizamos a list[dict]
                if isinstance(result, str):
                    return [{"result": result}]
                return result  # ya es list[dict]
            else:
                with db_instance._engine.connect() as conn:
                    res = conn.execute(sqlalchemy.text(sql))
                    conn.commit()
                    return [{"rows_affected": res.rowcount}]
        except Exception as exc:
            logger.exception("[DatabaseService] ❌ Error ejecutando SQL: %s", exc)
            raise RuntimeError("Failed to execute SQL query")
