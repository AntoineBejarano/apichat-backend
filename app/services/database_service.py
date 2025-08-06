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
        logger.info("[DatabaseService] ✅ Inicializado para user_id=%s", self.user.id)

    # ---------------------------------------------------------
    # CRUD CONEXIONES
    # ---------------------------------------------------------

    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info("[DatabaseService] ➕ Creando conexión DB para user_id=%s", self.user.id)
        connection = DatabaseConnection(user_id=self.user.id, **data.model_dump())
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def update_connection(self, db_id: int, updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info("[DatabaseService] 🔄 Actualizando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database connection not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)

        self.db.commit()
        self.db.refresh(conn)
        return conn

    def get_user_databases(self) -> List[DatabaseConnection]:
        logger.info("[DatabaseService] 📥 Listando todas las conexiones DB para user_id=%s", self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == self.user.id)
            .all()
        )

    def get_record(self, db_id: int) -> Optional[DatabaseConnection]:
        logger.debug("[DatabaseService] 🔎 Buscando DB id=%s para user_id=%s", db_id, self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter_by(id=db_id, user_id=self.user.id)
            .first()
        )

    def delete_connection(self, db_id: int) -> bool:
        logger.warning("[DatabaseService] 🗑️ Eliminando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            return False

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
    # VALIDACIÓN DE CONEXIONES EXISTENTES
    # ---------------------------------------------------------

    def test_connection_by_id(self, db_id: int) -> bool:
        """
        Valida si una conexión existente (guardada en la DB) es válida.
        """
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

    def get_sql_instance_from_action(self, action: dict, proxy_config: Optional[dict] = None) -> SQLDatabase:
        """
        Recibe una acción (que contiene el ID de la DB) y devuelve una instancia SQLDatabase.
        Soporta configuración de proxy si es necesario en el futuro.
        """
        db_id = action.get("database_id") or action.get("db_id")
        if not db_id:
            raise ValueError("Acción db_query sin 'database_id'")

        logger.info("[DatabaseService] 📡 Obteniendo SQL instance para acción con DB id=%s", db_id)
        
        # Aquí podrías adaptar si usas proxies en la conexión (por ahora no se usa)
        return self.get_sql_instance(db_id)

    def execute_sql(self, db_conn: SQLDatabase, sql: str) -> list:
        """
        Ejecuta una sentencia SQL directamente usando langchain_community.SQLDatabase.
        """
        try:
            logger.info("[DatabaseService] 💾 Ejecutando SQL: %s", sql)
            result = db_conn.run(sql)
            logger.debug("[DatabaseService] ✅ Resultado: %s", result)
            return result
        except Exception as e:
            logger.error("[DatabaseService] ❌ Error al ejecutar SQL: %s", e)
            raise
