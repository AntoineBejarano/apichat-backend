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
from app.services.base_service import BaseService
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class DatabaseService(BaseService):
    """Gestión de conexiones y consultas SQL para cada usuario."""

    def __init__(self, factory: "ServiceFactory") -> None:
        super().__init__(factory)
        logger.info("[DatabaseService] ✅ Inicializado para user_id=%s", self.user_id)

    # ---------------------------------------------------------
    # CRUD CONEXIONES
    # ---------------------------------------------------------

    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info("[DatabaseService] ➕ Creando conexión DB para user_id=%s", self.user_id)
        connection = DatabaseConnection(user_id=self.user_id, **data.model_dump())
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def update_connection(self, db_id: int, updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info("[DatabaseService] 🔄 Actualizando DB id=%s para user_id=%s", db_id, self.user_id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database connection not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)

        self.db.commit()
        self.db.refresh(conn)
        return conn

    def get_user_databases(self) -> List[DatabaseConnection]:
        logger.info("[DatabaseService] 📥 Listando todas las conexiones DB para user_id=%s", self.user_id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == self.user_id)
            .all()
        )

    def get_record(self, db_id: int) -> Optional[DatabaseConnection]:
        logger.debug("[DatabaseService] 🔎 Buscando DB id=%s para user_id=%s", db_id, self.user_id)
        return (
            self.db.query(DatabaseConnection)
            .filter_by(id=db_id, user_id=self.user_id)
            .first()
        )

    def delete_connection(self, db_id: int) -> bool:
        logger.warning("[DatabaseService] 🗑️ Eliminando DB id=%s para user_id=%s", db_id, self.user_id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database not found")

        self.db.delete(conn)
        self.db.commit()
        return True

    # ---------------------------------------------------------
    # INSTANCIAS SQL
    # ---------------------------------------------------------

    def build_sqlalchemy_engine(self, record: DatabaseConnection):
        uri = build_sqlalchemy_uri(record)
        logger.debug("[DatabaseService] 🛠️ Construyendo engine para URI: %s", uri)
        return sqlalchemy.create_engine(uri)

    def get_sql_database_from_record(self, record: DatabaseConnection) -> Optional[SQLDatabase]:
        try:
            engine = self.build_sqlalchemy_engine(record)
            return SQLDatabase(engine)
        except Exception as exc:
            logger.error("[DatabaseService] ❌ Error creando SQLDatabase: %s", exc)
            return None

    def get_sql_database_by_id(self, db_id: int) -> Optional[SQLDatabase]:
        logger.info("[DatabaseService] 🔄 Obteniendo SQLDatabase para DB id=%s", db_id)
        record = self.get_record(db_id)
        return self.get_sql_database_from_record(record) if record else None

    def get_sql_instance(self, db_id: int) -> SQLDatabase:
        logger.info("[DatabaseService] 🎯 Obteniendo instancia SQL para DB id=%s", db_id)
        db_instance = self.get_sql_database_by_id(db_id)
        if not db_instance:
            logger.error("[DatabaseService] ❌ No se pudo conectar a la base de datos id=%s", db_id)
            raise ValueError(f"No se pudo conectar a la base de datos {db_id}")
        return db_instance

    # ---------------------------------------------------------
    # VALIDACIÓN DE CONEXIONES
    # ---------------------------------------------------------

    def validate_connection(self, data: DatabaseConnectionCreate) -> bool:
        """
        Valida que la configuración de conexión sea válida antes de guardarla.
        """
        try:
            record = DatabaseConnection(user_id=self.user_id, **data.model_dump())
            engine = self.build_sqlalchemy_engine(record)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            logger.info("[DatabaseService] ✅ Conexión válida para URI: %s", record.url)
            return True
        except Exception as e:
            logger.warning("[DatabaseService] ⚠️ Conexión inválida: %s", e)
            return False
