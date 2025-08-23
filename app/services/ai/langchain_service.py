import logging
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.engine import create_engine
import asyncio
from datetime import datetime, timezone
import time
import re # Added for extract_tables_from_sql

from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from app.models.app_model import App
from app.core.config import settings
from app.core.langsmith_config import langsmith_config, traceable_if_enabled
from app.services.ai.language_detection_service import LanguageDetectionService

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
        
        # 🔧 FASE 1: Inicializar servicio de detección de idioma
        self.language_service = LanguageDetectionService()

    def is_valid_sql(self, sql: str) -> bool:
        """
        🔧 FASE 1: Valida si el output del LLM es una consulta SQL válida.
        
        Args:
            sql: String a validar como SQL
            
        Returns:
            True si parece ser SQL válido, False en caso contrario
        """
        if not sql or not isinstance(sql, str):
            return False
            
        sql = sql.strip().lower()
        
        # Verificar que comience con SELECT y contenga FROM
        if not sql.startswith("select") or "from" not in sql:
            return False
            
        # Verificar que no sea solo texto explicativo
        explanatory_phrases = [
            "lo siento", "no puedo", "necesitaría", "reemplaza", "no tengo",
            "no hay", "no existe", "no se puede", "imposible", "error"
        ]
        
        if any(phrase in sql for phrase in explanatory_phrases):
            return False
            
        return True

    def extract_tables_from_sql(self, sql: str) -> List[str]:
        """
        🔧 FASE 1: Extrae nombres de tablas mencionadas en una consulta SQL.
        
        Args:
            sql: Consulta SQL a analizar
            
        Returns:
            Lista de nombres de tablas mencionadas
        """
        if not sql:
            return []
        
        tables = []
        sql_upper = sql.upper()
        
        # Buscar patrones comunes de tablas en SQL
        # FROM table_name
        from_pattern = r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        from_matches = re.findall(from_pattern, sql_upper)
        tables.extend(from_matches)
        
        # JOIN table_name
        join_pattern = r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        join_matches = re.findall(join_pattern, sql_upper)
        tables.extend(join_matches)
        
        # UPDATE table_name (aunque no debería aparecer en SELECTs)
        update_pattern = r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        update_matches = re.findall(update_pattern, sql_upper)
        tables.extend(update_matches)
        
        # INSERT INTO table_name (aunque no debería aparecer en SELECTs)
        insert_pattern = r'INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        insert_matches = re.findall(insert_pattern, sql_upper)
        tables.extend(insert_matches)
        
        # Eliminar duplicados y convertir a minúsculas
        unique_tables = list(set([table.lower() for table in tables]))
        
        logger.debug(f"[LangchainService] 🔍 Tablas extraídas del SQL: {unique_tables}")
        return unique_tables

    def validate_tables_exist(self, sql: str, available_tables: List[str]) -> Dict[str, Any]:
        """
        🔧 FASE 1: Valida que las tablas mencionadas en el SQL existan en la base de datos.
        
        Args:
            sql: Consulta SQL a validar
            available_tables: Lista de tablas disponibles en la base de datos
            
        Returns:
            Dict con resultado de validación y sugerencias
        """
        if not sql or not available_tables:
            return {
                "valid": False,
                "missing_tables": [],
                "suggestions": [],
                "error": "SQL o tablas disponibles no proporcionados"
            }
        
        # Extraer tablas del SQL
        mentioned_tables = self.extract_tables_from_sql(sql)
        
        if not mentioned_tables:
            return {
                "valid": True,
                "missing_tables": [],
                "suggestions": [],
                "message": "No se detectaron tablas en la consulta SQL"
            }
        
        # Verificar qué tablas faltan
        available_tables_lower = [table.lower() for table in available_tables]
        missing_tables = [table for table in mentioned_tables if table not in available_tables_lower]
        
        if missing_tables:
            # Generar sugerencias de tablas similares
            suggestions = []
            for missing_table in missing_tables:
                # Buscar tablas que contengan palabras similares
                similar_tables = []
                for available_table in available_tables:
                    # Si la tabla faltante contiene palabras que están en la tabla disponible
                    missing_words = missing_table.split('_')
                    available_words = available_table.lower().split('_')
                    
                    # Calcular similitud simple
                    common_words = set(missing_words) & set(available_words)
                    if len(common_words) > 0:
                        similar_tables.append(available_table)
                
                if similar_tables:
                    suggestions.append({
                        "missing_table": missing_table,
                        "similar_tables": similar_tables[:3]  # Máximo 3 sugerencias
                    })
            
            return {
                "valid": False,
                "missing_tables": missing_tables,
                "suggestions": suggestions,
                "error": f"Tablas no encontradas: {', '.join(missing_tables)}",
                "available_tables": available_tables
            }
        
        return {
            "valid": True,
            "missing_tables": [],
            "suggestions": [],
            "message": "Todas las tablas mencionadas existen en la base de datos"
        }

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

    async def generate_sql_from_question_sync(self, question: str, db_id: UUID, table_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        🔧 FASE 6: Genera SQL desde una pregunta en lenguaje natural.
        MÉTODO DEPRECADO: Usar generate_sql_from_question() en su lugar.
        
        Args:
            question: Pregunta en lenguaje natural
            db_id: ID de la base de datos
            table_schema: Esquema de tablas opcional para contexto
            
        Returns:
            Dict con SQL generado y metadata
        """
        logger.warning(f"[LangchainService] ⚠️ FASE 6: generate_sql_from_question_sync está deprecado, usando generate_sql_from_question")
        return await self.generate_sql_from_question(question, db_id, table_schema)

    @traceable_if_enabled(
        name="generate_sql_from_question",
        tags=["sql_generation", "langchain"],
        metadata={"service": "LangchainService"}
    )
    async def generate_sql_from_question(self, question: str, db_id: UUID, table_schema: Optional[str] = None) -> Dict[str, Any]:
        """
        🔧 FASE 6: Genera SQL desde una pregunta en lenguaje natural con tracing de Langsmith.
        
        Args:
            question: Pregunta en lenguaje natural
            db_id: ID de la base de datos
            table_schema: Esquema de tablas opcional para contexto
            
        Returns:
            Dict con SQL generado y metadata
        """
        start_time = time.time()
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
            response = await self.llm.ainvoke(sql_prompt)
            
            # Extraer SQL de la respuesta
            generated_sql = response.content.strip() if hasattr(response, 'content') else str(response)
            
            # Limpiar y validar SQL
            sql = generated_sql.strip()
            if sql.startswith('```sql'):
                sql = sql[7:]
            if sql.endswith('```'):
                sql = sql[:-3]
            sql = sql.strip()
            
            # 🔧 FASE 1: Validar si el output del LLM es una consulta SQL válida
            if not self.is_valid_sql(sql):
                logger.warning(f"[LangchainService] ⚠️ FASE 1: La respuesta no parece SQL válido. Respuesta: {sql}")
                return {
                    "sql": "",
                    "content": generated_sql,
                    "error": "Respuesta del modelo no es una consulta SQL ejecutable.",
                    "status": "llm_response",
                    "question": question,
                    "database_id": str(db_id),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
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
            
            # 🔧 FASE 1: Validar que las tablas mencionadas existan en la base de datos
            if table_schema:
                try:
                    # Extraer nombres de tablas del esquema
                    available_tables = self._extract_available_tables_from_schema(table_schema)
                    
                    if available_tables:
                        # Validar que las tablas del SQL existan
                        table_validation = self.validate_tables_exist(sql, available_tables)
                        
                        if not table_validation["valid"]:
                            logger.warning(f"[LangchainService] ⚠️ FASE 1: Tablas no encontradas en SQL: {table_validation['missing_tables']}")
                            
                            # Generar SQL alternativo con tablas existentes
                            fallback_sql = self._generate_fallback_sql_with_available_tables(
                                question, available_tables, table_validation["suggestions"]
                            )
                            
                            if fallback_sql:
                                logger.info(f"[LangchainService] 🔧 FASE 1: SQL alternativo generado con tablas existentes")
                                sql = fallback_sql
                            else:
                                return {
                                    "sql": "",
                                    "error": f"Tablas no encontradas: {', '.join(table_validation['missing_tables'])}",
                                    "missing_tables": table_validation["missing_tables"],
                                    "suggestions": table_validation["suggestions"],
                                    "available_tables": available_tables,
                                    "question": question,
                                    "database_id": str(db_id),
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                        else:
                            logger.info(f"[LangchainService] ✅ FASE 1: Todas las tablas validadas correctamente")
                    else:
                        logger.warning(f"[LangchainService] ⚠️ FASE 1: No se pudieron extraer tablas del esquema")
                        
                except Exception as e:
                    logger.warning(f"[LangchainService] ⚠️ FASE 1: Error validando tablas: {e}")
                    # Continuar sin validación de tablas si hay error
            
            # 🔧 FASE 6: Asegurar LIMIT en SELECTs
            if sql_upper.startswith('SELECT') and 'LIMIT' not in sql_upper:
                sql = f"{sql.rstrip(';')} LIMIT 100;"
                logger.info(f"[LangchainService] 🔧 FASE 6: LIMIT 100 agregado automáticamente")
            
            # 🔧 FASE 6: Calcular tiempo de respuesta
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 🔧 FASE 6: Tracking de LLM run en base de datos
            # 🔧 NUEVO: Obtener chat_id del factory si está disponible
            chat_id = getattr(self.factory, 'current_chat_id', None)
            if chat_id:
                await self._track_llm_run(
                    question=question,
                    response=sql,
                    database_id=db_id,
                    table_schema=table_schema,
                    response_time_ms=response_time_ms,
                    chat_id=chat_id,
                    status="success",
                    sql_validated=True,
                    sql_generated=sql
                )
            else:
                logger.warning("[LangchainService] ⚠️ No se pudo obtener chat_id para tracking de LLM run")
            
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
            
            # 🔧 FASE 6: Calcular tiempo de respuesta
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # 🔧 FASE 6: Tracking de LLM run en base de datos (con error)
            # 🔧 NUEVO: Obtener chat_id del factory si está disponible
            chat_id = getattr(self.factory, 'current_chat_id', None)
            if chat_id:
                await self._track_llm_run(
                    question=question,
                    response=f"Error: {str(e)}",
                    database_id=db_id,
                    table_schema=table_schema,
                    response_time_ms=response_time_ms,
                    chat_id=chat_id,
                    status="error",
                    error_message=str(e),
                    sql_validated=False,
                    sql_generated=None
                )
            else:
                logger.warning("[LangchainService] ⚠️ No se pudo obtener chat_id para tracking de LLM run (error)")
            
            # 🔧 FASE 1: Fallback SQL genérico y seguro
            fallback_sql = self._generate_fallback_sql(question, db_id)
            
            return {
                "sql": fallback_sql,
                "question": question,
                "database_id": str(db_id),
                "source": "fallback_sql_generation",
                "security_validated": True,
                "fallback_used": True,
                "error": f"Error generando SQL: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _generate_fallback_sql(self, question: str, db_id: UUID) -> str:
        """
        🔧 FASE 1: Genera SQL de fallback genérico y seguro cuando falla la generación principal.
        Ahora incluye detección de idioma y búsqueda difusa para mejorar la precisión.
        """
        # 🔧 FASE 1: Usar servicio de detección de idioma para mejorar la consulta
        enhanced_query_info = self.language_service.enhance_query_for_schema_search(question)
        enhanced_question = enhanced_query_info['enhanced_query']
        detected_language = enhanced_query_info['detected_language']
        
        logger.info(f"[LangchainService] 🔧 FASE 1: Idioma detectado: {detected_language}, consulta mejorada: '{enhanced_question[:50]}...'")
        
        # Detectar si la pregunta es sobre esquema/tablas usando búsqueda difusa
        schema_keywords = [
            'tabla', 'table', 'esquema', 'schema', 'estructura', 'structure', 
            'columnas', 'columns', 'database', 'base de datos', 'datos', 'data'
        ]
        
        # Usar búsqueda difusa para determinar el tipo de consulta
        fuzzy_results = self.language_service.fuzzy_search(enhanced_question, schema_keywords, threshold=60.0)
        is_schema_question = len(fuzzy_results) > 0 and fuzzy_results[0][1] > 60.0
        
        if is_schema_question:
            # SQL genérico para listar tablas (funciona en cualquier DB estándar)
            fallback_sql = """
            SELECT 
                table_schema,
                table_name,
                table_type,
                table_rows,
                table_comment
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE'
                AND table_schema NOT IN ('pg_catalog', 'information_schema', 'mysql', 'performance_schema')
            ORDER BY table_schema, table_name
            LIMIT 50;
            """
            logger.info(f"[LangchainService] 🔧 FASE 1: Usando fallback SQL para esquema (idioma: {detected_language}): {fallback_sql[:100]}...")
        else:
            # SQL genérico para explorar datos
            fallback_sql = """
            SELECT 
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default,
                column_comment
            FROM information_schema.columns 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'mysql', 'performance_schema')
            ORDER BY table_name, ordinal_position
            LIMIT 100;
            """
            logger.info(f"[LangchainService] 🔧 FASE 1: Usando fallback SQL para exploración (idioma: {detected_language}): {fallback_sql[:100]}...")
        
        return fallback_sql.strip()

    def _extract_available_tables_from_schema(self, schema_text: str) -> List[str]:
        """
        🔧 FASE 1: Extrae nombres de tablas mencionadas en un texto de esquema.
        
        Args:
            schema_text: Texto que contiene el esquema de la base de datos.
            
        Returns:
            Lista de nombres de tablas mencionadas.
        """
        if not schema_text:
            return []
        
        tables = []
        schema_upper = schema_text.upper()
        
        # Buscar patrones comunes de tablas en el texto del esquema
        # CREATE TABLE table_name
        create_table_pattern = r'CREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        create_table_matches = re.findall(create_table_pattern, schema_upper)
        tables.extend(create_table_matches)
        
        # ALTER TABLE table_name
        alter_table_pattern = r'ALTER\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        alter_table_matches = re.findall(alter_table_pattern, schema_upper)
        tables.extend(alter_table_matches)
        
        # DROP TABLE table_name
        drop_table_pattern = r'DROP\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        drop_table_matches = re.findall(drop_table_pattern, schema_upper)
        tables.extend(drop_table_matches)
        
        # Eliminar duplicados y convertir a minúsculas
        unique_tables = list(set([table.lower() for table in tables]))
        
        logger.debug(f"[LangchainService] 🔍 Tablas extraídas del esquema: {unique_tables}")
        return unique_tables

    def _generate_fallback_sql_with_available_tables(self, question: str, available_tables: List[str], suggestions: List[Dict[str, Any]]) -> Optional[str]:
        """
        🔧 FASE 1: Genera un SQL de fallback que usa tablas existentes, incluyendo sugerencias.
        
        Args:
            question: Pregunta original del usuario.
            available_tables: Lista de tablas que sí existen.
            suggestions: Sugerencias de tablas similares si faltan.
            
        Returns:
            SQL de fallback o None si no se puede generar.
        """
        # 🔧 FASE 1: Usar servicio de detección de idioma para mejorar la consulta
        enhanced_query_info = self.language_service.enhance_query_for_schema_search(question)
        enhanced_question = enhanced_query_info['enhanced_query']
        detected_language = enhanced_query_info['detected_language']
        
        logger.info(f"[LangchainService] 🔧 FASE 1: Idioma detectado: {detected_language}, consulta mejorada: '{enhanced_question[:50]}...'")
        
        # Detectar si la pregunta es sobre esquema/tablas usando búsqueda difusa
        schema_keywords = [
            'tabla', 'table', 'esquema', 'schema', 'estructura', 'structure', 
            'columnas', 'columns', 'database', 'base de datos', 'datos', 'data'
        ]
        
        # Usar búsqueda difusa para determinar el tipo de consulta
        fuzzy_results = self.language_service.fuzzy_search(enhanced_question, schema_keywords, threshold=60.0)
        is_schema_question = len(fuzzy_results) > 0 and fuzzy_results[0][1] > 60.0
        
        if is_schema_question:
            # SQL genérico para listar tablas (funciona en cualquier DB estándar)
            fallback_sql = """
            SELECT 
                table_schema,
                table_name,
                table_type,
                table_rows,
                table_comment
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE'
                AND table_schema NOT IN ('pg_catalog', 'information_schema', 'mysql', 'performance_schema')
            ORDER BY table_schema, table_name
            LIMIT 50;
            """
            logger.info(f"[LangchainService] 🔧 FASE 1: Usando fallback SQL para esquema (idioma: {detected_language}): {fallback_sql[:100]}...")
        else:
            # SQL genérico para explorar datos
            fallback_sql = """
            SELECT 
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default,
                column_comment
            FROM information_schema.columns 
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'mysql', 'performance_schema')
            ORDER BY table_name, ordinal_position
            LIMIT 100;
            """
            logger.info(f"[LangchainService] 🔧 FASE 1: Usando fallback SQL para exploración (idioma: {detected_language}): {fallback_sql[:100]}...")
        
        # Si las tablas mencionadas en la pregunta no están en las disponibles,
        # intentar generar un SQL que use las tablas disponibles.
        # Esto es un poco más complejo y puede requerir un análisis más profundo
        # de la pregunta y las tablas disponibles.
        # Por ahora, simplemente retornamos el SQL genérico.
        return fallback_sql.strip()

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
    
    async def _track_llm_run(
        self,
        question: str,
        response: str,
        database_id: UUID,
        table_schema: Optional[str],
        response_time_ms: int,
        chat_id: Optional[UUID] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        sql_validated: Optional[bool] = None,
        sql_generated: Optional[str] = None
    ):
        """
        🔧 FASE 6: Tracking interno de LLM runs para trazabilidad.
        
        Args:
            question: Pregunta original del usuario
            response: Respuesta del LLM
            database_id: ID de la base de datos
            table_schema: Esquema de tablas usado
            response_time_ms: Tiempo de respuesta en milisegundos
            status: Estado de la operación
            error_message: Mensaje de error si aplica
            sql_validated: Si el SQL pasó validación
            sql_generated: SQL generado por el LLM
        """
        try:
            # Obtener servicio de LLM runs
            llm_runs_service = self.factory.get_llm_runs_service()
            if not llm_runs_service:
                logger.warning("[LangchainService] ⚠️ LLM runs service no disponible")
                return
            
            # Obtener información del usuario
            user_id = getattr(self.factory.user, 'id', None)
            
            if not user_id:
                logger.warning("[LangchainService] ⚠️ No se pudo obtener user_id para tracking")
                return
            
            # Usar chat_id pasado como parámetro o crear uno por defecto
            if not chat_id:
                logger.warning("[LangchainService] ⚠️ No se proporcionó chat_id para tracking")
                return
            
            # Crear datos del LLM run
            from app.schemas.llm_runs_schema import LLMRunCreate
            
            llm_run_data = LLMRunCreate(
                chat_id=chat_id,
                user_id=user_id,
                model_name=self.llm.model_name,
                provider="openai",
                prompt_text=question,
                response_text=response,
                prompt_tokens=len(question.split()),  # Estimación simple
                response_tokens=len(response.split()),  # Estimación simple
                total_tokens=0,  # Se calcula automáticamente
                response_time_ms=response_time_ms,
                status=status,
                error_message=error_message,
                table_schema=table_schema,
                database_id=database_id,
                sql_generated=sql_generated,
                sql_validated=sql_validated,
                sql_executed=False  # Se marcará como True cuando se ejecute
            )
            
            # Guardar en base de datos
            await llm_runs_service.create_llm_run(llm_run_data)
            logger.info(f"[LangchainService] ✅ LLM run trackeado: {status}, {response_time_ms}ms")
            
        except Exception as e:
            logger.error(f"[LangchainService] ❌ Error tracking LLM run: {e}")
            # No fallar la operación principal por errores de tracking
