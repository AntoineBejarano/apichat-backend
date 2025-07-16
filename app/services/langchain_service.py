import logging
from sqlalchemy.engine import create_engine
from langchain_community.chat_models import ChatOpenAI
from langchain_experimental.sql import SQLDatabaseChain
from langchain.sql_database import SQLDatabase

from app.models.database_model import DatabaseConnection
from app.core.servicefactory import ServiceFactory
from app.core.config import settings  # ✅ Importamos configuración

logger = logging.getLogger(__name__)


class LangchainService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.llm = ChatOpenAI(
            temperature=settings.openai_temperature,
            model=settings.openai_model
        )

    def build_connection_string(self, db: DatabaseConnection) -> str:
        return f"{db.db_type}://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}"

    def ask_database_question(self, db: DatabaseConnection, question: str) -> str:
        logger.info(f"[LangchainService] 🧠 Pregunta a DB {db.id}: '{question}'")
        conn_str = self.build_connection_string(db)
        engine = create_engine(conn_str)

        try:
            sql_db = SQLDatabase(engine)
            db_chain = SQLDatabaseChain.from_llm(self.llm, sql_db, verbose=False)
            return db_chain.run(question)
        except Exception as e:
            logger.exception(f"[LangchainService] ❌ Error al procesar pregunta: {str(e)}")
            raise RuntimeError("Error al procesar la pregunta con LangChain.")
