import logging
import sqlalchemy
from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.database_model import DatabaseConnection
from app.schemas.database_schema import DatabaseConnectionCreate, DatabaseConnectionUpdate
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri
from langchain_community.utilities.sql_database import SQLDatabase

from app.core.servicefactory import ServiceFactory  # ✅ nuevo import

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info(f"[DatabaseService] 🧩 Creando conexión DB para user {self.user_id}")
        connection = DatabaseConnection(user_id=self.user_id, **data.model_dump())
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        logger.debug(f"[DatabaseService] ✅ Conexión creada con ID {connection.id}")
        return connection

    def update_connection(self, db_id: int, updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info(f"[DatabaseService] 🔄 Actualizando DB {db_id} para user {self.user_id}")
        conn = self.get_record(db_id)
        if not conn:
            logger.warning(f"[DatabaseService] DB {db_id} no encontrada para user {self.user_id}")
            raise ValueError("Database connection not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)

        self.db.commit()
        self.db.refresh(conn)
        logger.debug(f"[DatabaseService] ✅ DB {db_id} actualizada")
        return conn

    def get_user_databases(self) -> List[DatabaseConnection]:
        logger.info(f"[DatabaseService] 📦 Listando DBs del user {self.user_id}")
        return self.db.query(DatabaseConnection).filter(DatabaseConnection.user_id == self.user_id).all()

    def get_record(self, db_id: int) -> Optional[DatabaseConnection]:
        logger.debug(f"[DatabaseService] 🔍 Buscando DB {db_id} del user {self.user_id}")
        return self.db.query(DatabaseConnection).filter_by(id=db_id, user_id=self.user_id).first()

    def delete_connection(self, db_id: int) -> bool:
        logger.info(f"[DatabaseService] 🗑 Eliminando conexión DB {db_id} del user {self.user_id}")
        conn = self.get_record(db_id)
        if not conn:
            logger.warning(f"[DatabaseService] DB {db_id} no encontrada para eliminación")
            raise ValueError("Database not found")

        try:
            self.db.delete(conn)
            self.db.commit()
            logger.info(f"[DatabaseService] ✅ Conexión DB {db_id} eliminada correctamente")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"[DatabaseService] ❌ Error eliminando DB {db_id}: {str(e)}")
            raise RuntimeError("Failed to delete database connection")

    def get_sql_database_from_record(self, record: DatabaseConnection) -> Optional[SQLDatabase]:
        logger.info(f"[DatabaseService] 🧠 Generando SQLDatabase desde conexión ID {record.id}")
        try:
            uri = build_sqlalchemy_uri(record)
            engine = sqlalchemy.create_engine(uri)
            logger.debug(f"[DatabaseService] 🔗 SQLAlchemy URI construido correctamente")
            return SQLDatabase(engine)
        except Exception as e:
            logger.error(f"[DatabaseService] ❌ Error creando conexión SQLDatabase: {str(e)}")
            return None

    def get_sql_database_by_id(self, db_id: int) -> Optional[SQLDatabase]:
        logger.info(f"[DatabaseService] 🔍 Solicitando SQLDatabase desde DB ID {db_id}")
        record = self.get_record(db_id)
        if not record:
            logger.warning(f"[DatabaseService] DB {db_id} no encontrada para user {self.user_id}")
            return None
        return self.get_sql_database_from_record(record)

    def get_sql_instance(self, db_id: int) -> SQLDatabase:
        logger.info(f"[DatabaseService] 🧪 Obteniendo instancia SQL para DB {db_id} del user {self.user_id}")
        db_instance = self.get_sql_database_by_id(db_id)
        if not db_instance:
            raise ValueError(f"No se pudo conectar a la base de datos {db_id}")
        return db_instance
