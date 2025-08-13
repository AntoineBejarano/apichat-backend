import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.engine import create_engine
import asyncio
from datetime import datetime, timezone

from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
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
        model = getattr(settings, "OPENAI_SQL_MODEL", None) or settings.OPENAI_MODEL
        self.llm = ChatOpenAI(
            temperature=getattr(settings, "OPENAI_TEMPERATURE", 0),
            model=model,
            max_tokens=600,
            timeout=30,
            max_retries=1,
        )

    def build_connection_string(self, db: DatabaseConnection) -> str:
        return f"{db.db_type}://{db.username}:{db.password}@{db.host}:{db.port}/{db.database}"

    async def ask_database_question(self, db: DatabaseConnection, question: str) -> Dict[str, Any]:
        """
        🔧 FASE 5: Método async que siempre devuelve un dict estandarizado.
        
        Args:
            db: Conexión a la base de datos
            question: Pregunta en lenguaje natural
            
        Returns:
            Dict con estructura estandarizada: {rows, sql, summary}
        """
        logger.info(f"[LangchainService] 🧠 FASE 5: Preguntando a DB {db.id}: '{question}'")
        
        try:
            engine = create_engine(self.build_connection_string(db))
            sql_db = SQLDatabase(engine, sample_rows_in_table_info=0)
            db_chain = SQLDatabaseChain.from_llm(llm=self.llm, db=sql_db, verbose=False, use_query_checker=True)
            
            # 🔧 FASE 5: Ejecutar de forma asíncrona
            out = await asyncio.to_thread(db_chain.invoke, {"query": question})
            
            # 🔧 FASE 5: Estandarizar respuesta como dict
            if isinstance(out, dict):
                # Si ya es un dict, extraer información relevante
                result = out.get("result", str(out))
                sql = out.get("sql", "")
            else:
                # Si es string u otro tipo, convertir a dict estandarizado
                result = str(out) if out else ""
                sql = ""
            
            # 🔧 FASE 5: Estructura estandarizada siempre
            standardized_response = {
                "rows": result if isinstance(result, (list, dict)) else [],
                "sql": sql,
                "summary": str(result) if result else "No se encontraron resultados",
                "source": "langchain_sql_chain",
                "database_id": str(db.id),
                "question": question,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"[LangchainService] ✅ FASE 5: Respuesta estandarizada generada para DB {db.id}")
            return standardized_response
            
        except Exception as e:
            logger.exception(f"[LangchainService] ❌ FASE 5: Error con LangChain SQLDatabaseChain: {str(e)}")
            
            # 🔧 FASE 5: Devolver error estandarizado en lugar de raise
            return {
                "rows": [],
                "sql": "",
                "summary": f"Error procesando la pregunta: {str(e)}",
                "error": str(e),
                "source": "langchain_sql_chain_error",
                "database_id": str(db.id),
                "question": question,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def generate_sql_from_question_sync(self, question: str, db_id: UUID, table_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        🔧 FASE 6: Versión síncrona de generate_sql_from_question para contextos síncronos.
        
        Args:
            question: Pregunta en lenguaje natural
            db_id: ID de la base de datos
            table_schema: Esquema de tablas opcional para contexto
            
        Returns:
            Dict con SQL generado y metadata
        """
        logger.info(f"[LangchainService] 🔧 FASE 6: Generando SQL sincrónicamente para pregunta: '{question[:50]}...'")
        
        try:
            # Crear prompt para generación de SQL
            sql_prompt = f"""
            Genera una consulta SQL segura para la siguiente pregunta:
            
            Pregunta: {question}
            
            Reglas de seguridad:
            - SOLO usar SELECT (no INSERT, UPDATE, DELETE, DROP, CREATE)
            - SIEMPRE incluir LIMIT para evitar volcados masivos
            - Usar columnas específicas, no SELECT *
            - Incluir filtros WHERE cuando sea apropiado
            
            {f'Esquema disponible: {table_schema[:500]}...' if table_schema else 'No hay esquema disponible'}
            
            Responde SOLO con la consulta SQL válida, sin explicaciones adicionales.
            """
            
            # 🔧 FASE 6: Usar asyncio.run para ejecutar el método async en contexto síncrono
            import asyncio
            
            async def _generate_async():
                return await self.llm.ainvoke(sql_prompt)
            
            # Ejecutar de forma síncrona
            response = asyncio.run(_generate_async())
            
            # Extraer SQL de la respuesta
            sql = response.content.strip() if hasattr(response, 'content') else str(response)
            
            # Limpiar y validar SQL
            sql = sql.strip()
            if sql.startswith('```sql'):
                sql = sql[7:]
            if sql.endswith('```'):
                sql = sql[:-3]
            sql = sql.strip()
            
            # 🔧 FASE 6: Validaciones de seguridad básicas
            sql_upper = sql.upper()
            if any(dangerous in sql_upper for dangerous in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']):
                logger.warning(f"[LangchainService] 🚫 FASE 6: SQL peligroso detectado: {sql}")
                return {
                    "sql": "",
                    "error": "Operación no permitida por seguridad",
                    "blocked_operations": [op for op in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER'] if op in sql_upper],
                    "question": question,
                    "database_id": str(db_id),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # 🔧 FASE 6: Asegurar LIMIT en SELECTs
            if sql_upper.startswith('SELECT') and 'LIMIT' not in sql_upper:
                sql = f"{sql.rstrip(';')} LIMIT 100;"
                logger.info(f"[LangchainService] 🔧 FASE 6: LIMIT 100 agregado automáticamente")
            
            # 🔧 FASE 6: Respuesta estandarizada
            return {
                "sql": sql,
                "question": question,
                "database_id": str(db_id),
                "source": "langchain_sql_generation",
                "security_validated": True,
                "auto_limit_added": 'LIMIT' not in sql_upper and sql_upper.startswith('SELECT'),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.exception(f"[LangchainService] ❌ FASE 6: Error generando SQL sincrónicamente: {str(e)}")
            return {
                "sql": "",
                "error": f"Error generando SQL: {str(e)}",
                "question": question,
                "database_id": str(db_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def generate_sql_from_question(self, question: str, db_id: UUID, table_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        🔧 FASE 6: Genera SQL desde una pregunta en lenguaje natural.
        
        Args:
            question: Pregunta en lenguaje natural
            db_id: ID de la base de datos
            table_schema: Esquema de tablas opcional para contexto
            
        Returns:
            Dict con SQL generado y metadata
        """
        logger.info(f"[LangchainService] 🔧 FASE 6: Generando SQL para pregunta: '{question[:50]}...'")
        
        try:
            # Crear prompt para generación de SQL
            sql_prompt = f"""
            Genera una consulta SQL segura para la siguiente pregunta:
            
            Pregunta: {question}
            
            Reglas de seguridad:
            - SOLO usar SELECT (no INSERT, UPDATE, DELETE, DROP, CREATE)
            - SIEMPRE incluir LIMIT para evitar volcados masivos
            - Usar columnas específicas, no SELECT *
            - Incluir filtros WHERE cuando sea apropiado
            
            {f'Esquema disponible: {table_schema[:500]}...' if table_schema else 'No hay esquema disponible'}
            
            Responde SOLO con la consulta SQL válida, sin explicaciones adicionales.
            """
            
            # Generar SQL usando el LLM
            response = await asyncio.to_thread(
                self.llm.invoke,
                sql_prompt
            )
            
            # Extraer SQL de la respuesta
            sql = response.content.strip() if hasattr(response, 'content') else str(response)
            
            # Limpiar y validar SQL
            sql = sql.strip()
            if sql.startswith('```sql'):
                sql = sql[7:]
            if sql.endswith('```'):
                sql = sql[:-3]
            sql = sql.strip()
            
            # 🔧 FASE 6: Validaciones de seguridad básicas
            sql_upper = sql.upper()
            if any(dangerous in sql_upper for dangerous in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER']):
                logger.warning(f"[LangchainService] 🚫 FASE 6: SQL peligroso detectado: {sql}")
                return {
                    "sql": "",
                    "error": "Operación no permitida por seguridad",
                    "blocked_operations": [op for op in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER'] if op in sql_upper],
                    "question": question,
                    "database_id": str(db_id),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # 🔧 FASE 6: Asegurar LIMIT en SELECTs
            if sql_upper.startswith('SELECT') and 'LIMIT' not in sql_upper:
                sql = f"{sql.rstrip(';')} LIMIT 100;"
                logger.info(f"[LangchainService] 🔧 FASE 6: LIMIT 100 agregado automáticamente")
            
            # 🔧 FASE 6: Respuesta estandarizada
            return {
                "sql": sql,
                "question": question,
                "database_id": str(db_id),
                "source": "langchain_sql_generation",
                "security_validated": True,
                "auto_limit_added": 'LIMIT' not in sql_upper and sql_upper.startswith('SELECT'),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.exception(f"[LangchainService] ❌ FASE 6: Error generando SQL: {str(e)}")
            return {
                "sql": "",
                "error": f"Error generando SQL: {str(e)}",
                "question": question,
                "database_id": str(db_id),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def get_function_retriever(self) -> "LangchainService.FunctionRetriever":
        functions: List[Function] = self.factory.get_function_service().list_all_for_user()
        return self.FunctionRetriever(functions)

    class FunctionRetriever:
        def __init__(self, functions: List[Function]):
            self.functions = functions
            self.embeddings = OpenAIEmbeddings(model=getattr(settings, "OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small"))
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
        apps: List[App] = self.factory.get_apps_service().get_all()
        return self.AppRetriever(apps)

    class AppRetriever:
        def __init__(self, apps: List[App]):
            self.apps = apps
            self.embeddings = OpenAIEmbeddings(model=getattr(settings, "OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small"))
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
            self.embeddings = OpenAIEmbeddings(model=getattr(settings, "OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small"))
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
