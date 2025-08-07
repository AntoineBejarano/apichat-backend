import logging
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID
from sqlalchemy.engine import create_engine

from langchain.agents import initialize_agent, AgentType
from langchain_community.chat_models import ChatOpenAI
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document

from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from app.models.app_model import App

from app.core.config import settings

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class LangchainService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.llm = ChatOpenAI(
            temperature=settings.OPENAI_TEMPERATURE,
            model=settings.OPENAI_MODEL
        )

    def build_connection_string(self, db: DatabaseConnection) -> str:
        return f"{db.db_type}://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}"

    def ask_database_question(self, db: DatabaseConnection, question: str) -> str:
        logger.info(f"[LangchainService] 🧠 Preguntando a DB {db.id}: '{question}'")
        try:
            engine = create_engine(self.build_connection_string(db))
            sql_db = SQLDatabase(engine)

            db_chain = SQLDatabaseChain.from_llm(
                llm=self.llm,
                db=sql_db,
                verbose=False
            )

            return db_chain.run(question)
        except Exception as e:
            logger.exception(f"[LangchainService] ❌ Error con LangChain SQLDatabaseChain: {str(e)}")
            raise RuntimeError("Error procesando la pregunta con LangChain SQLDatabaseChain.")

    def get_function_retriever(self) -> "LangchainService.FunctionRetriever":
        functions: List[Function] = self.factory.get_function_service().list_all_for_user()
        return self.FunctionRetriever(functions)

    class FunctionRetriever:
        def __init__(self, functions: List[Function]):
            self.functions = functions
            self.embeddings = OpenAIEmbeddings()
            self.vectorstore = self._build_vectorstore()

        def _build_vectorstore(self):
            texts = [f"{f.name}: {f.description}" for f in self.functions]
            metadatas = [{"function_id": f.id} for f in self.functions]
            return FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)

        def search_relevant_functions(self, query: str, k: int = 5) -> List[Function]:
            docs: List[Document] = self.vectorstore.similarity_search(query, k=k)
            relevant_ids = {doc.metadata["function_id"] for doc in docs}
            return [f for f in self.functions if f.id in relevant_ids]

    def get_app_retriever(self) -> "LangchainService.AppRetriever":
        apps: List[App] = self.factory.get_apps_service().list_all_for_user()
        return self.AppRetriever(apps)

    class AppRetriever:
        def __init__(self, apps: List[App]):
            self.apps = apps
            self.embeddings = OpenAIEmbeddings()
            self.vectorstore = self._build_vectorstore()

        def _build_vectorstore(self):
            texts = [f"{a.name}: {a.description}" for a in self.apps]
            metadatas = [{"app_id": a.id} for a in self.apps]
            return FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)

        def search_relevant_apps(self, query: str, k: int = 2) -> List[App]:
            docs: List[Document] = self.vectorstore.similarity_search(query, k=k)
            relevant_ids = {doc.metadata["app_id"] for doc in docs}
            return [a for a in self.apps if a.id in relevant_ids]

    def get_database_retriever(self) -> "LangchainService.DatabaseRetriever":
        databases: List[DatabaseConnection] = self.factory.get_database_service().list_all_for_user()
        return self.DatabaseRetriever(databases)

    class DatabaseRetriever:
        def __init__(self, databases: List[DatabaseConnection]):
            self.databases = databases
            self.embeddings = OpenAIEmbeddings()
            self.vectorstore = self._build_vectorstore()

        def _build_vectorstore(self):
            texts = [f"{db.name}: {db.description or db.host}" for db in self.databases]
            metadatas = [{"db_id": db.id} for db in self.databases]
            return FAISS.from_texts(texts, self.embeddings, metadatas=metadatas)

        def infer_best_database(self, query: str, k: int = 1) -> Optional[DatabaseConnection]:
            docs: List[Document] = self.vectorstore.similarity_search(query, k=k)
            if not docs:
                return None
            best_id = docs[0].metadata["db_id"]
            return next((db for db in self.databases if db.id == best_id), None)
