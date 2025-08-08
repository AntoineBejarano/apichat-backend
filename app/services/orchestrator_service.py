# app/services/orchestrator_service.py
"""
OrchestratorService
───────────────────
1. Guarda el mensaje del usuario.
2. Lanza Guided / Exploration Graph y obtiene:
      • una respuesta simple, o
      • un PlanModel con acciones.
3. Si hay plan, ejecuta acciones con ExecutionEngineService y
   renderiza la respuesta final.
4. Devuelve siempre `assistant_response` al front y registra todo.
"""
from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.schemas.plan_schema import PlanModel
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context, memory_profiler
from app.core.database import SessionLocal

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Modelo auxiliar (por si lo sigues usando en PlanModel)
# ──────────────────────────────────────────────────────
class ActionModel(BaseModel):
    type: str = Field(..., description="db_query, api_function, mcp_tool")
    sql: Optional[str] = None
    question: Optional[str] = None
    function_id: Optional[int] = None
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    store_as: Optional[str] = None
    proxy_id: Optional[int] = None


# ──────────────────────────────────────────────────────
#   Servicio
# ──────────────────────────────────────────────────────
class OrchestratorService:
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        self.history_service = factory.get_chat_history_service()
        logger.info("[OrchestratorService] Initialized for user_id=%s", self.user_id)

    # ===================================================
    #  PUBLIC ENTRY-POINT
    # ===================================================
    @monitor_performance("orchestrator_handle_message")
    @profile_function("orchestrator_handle_message")
    async def handle_user_message(
        self,
        chat_id: UUID,
        db_ids: Optional[List[UUID]],
        app_ids: Optional[List[UUID]],
        explorer: bool,
        agent_id: Optional[UUID],
        message: ChatMessage,
    ) -> Dict[str, Any]:

        # 📊 Profiling de memoria
        memory_profiler.take_snapshot("orchestrator_start")

        # ⚡ OPTIMIZACIÓN: Ejecutar operaciones en paralelo
        tasks = []
        
        # 1) Límite de uso (async)
        usage_task = asyncio.create_task(self._check_usage_limit_async())
        
        # 2) Guardar mensaje del usuario (async)
        store_task = asyncio.create_task(self._store_user_message_async(chat_id, message))
        
        # 3) Cargar contexto en paralelo
        context_tasks = await self._load_context_parallel(chat_id, message, db_ids, app_ids, explorer)
        
        # Actualizar el contexto con el parámetro explorer
        context_tasks["explorer"] = explorer

        # ⏳ Esperar a que terminen las tareas asíncronas
        try:
            await asyncio.gather(usage_task, store_task, return_exceptions=True)
        except Exception as e:
            logger.warning("[OrchestratorService] Error en tareas asíncronas: %s", e)

        # 🎯 Ejecutar el grafo
        graph_runner = self._select_graph_runner(explorer)
        
        try:
            execution_results = await graph_runner.run(context_tasks)
            logger.info("[OrchestratorService] Graph execution completed")
            
            # 🔄 Ejecutar el plan si se generó uno
            if execution_results.get("plan"):
                logger.info("[OrchestratorService] 🚀 Ejecutando plan generado")
                logger.info(f"[OrchestratorService] 📋 Plan: {execution_results['plan']}")
                execution_engine = self.factory.get_execution_engine_service()
                
                # Asegurar que el contexto tenga db_ids
                execution_context = context_tasks.copy()
                if db_ids:
                    execution_context["db_ids"] = [str(db_id) for db_id in db_ids]
                
                final_results = execution_engine.run(
                    plan=execution_results["plan"].model_dump(),
                    chat_id=chat_id,
                    ctx=execution_context
                )
                # Combinar resultados
                execution_results.update(final_results)
                logger.info("[OrchestratorService] ✅ Plan ejecutado correctamente")
                logger.info(f"[OrchestratorService] 📤 Resultados finales: {final_results}")
            else:
                logger.info("[OrchestratorService] 📝 No se generó plan, usando respuesta directa")
                logger.info(f"[OrchestratorService] 📤 Resultados del grafo: {execution_results}")
                
        except Exception as e:
            logger.exception("[OrchestratorService] Graph execution failed: %s", e)
            execution_results = {"error": str(e)}

        # 📝 Guardar respuesta del asistente
        assistant_response = self._extract_assistant_response(execution_results)
        
        # 💾 Guardar mensaje del asistente de forma async
        await self._save_assistant_message_async(
            chat_id=chat_id,
            content=assistant_response,
            token_count=execution_results.get("token_count"),
            executed_strategy_id=execution_results.get("executed_strategy_id"),
        )

        # 📊 Profiling final
        memory_profiler.take_snapshot("orchestrator_end")

        return {
            "assistant_response": assistant_response,
            "execution_results": execution_results,
            "steps": execution_results.get("steps", []),
        }

    # ===================================================
    #  ASYNC HELPERS (con sesiones separadas)
    # ===================================================
    @monitor_performance("check_usage_limit")
    @profile_function("check_usage_limit")
    async def _check_usage_limit_async(self):
        """Verificar límites de uso de forma async"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._check_usage_limit)

    @monitor_performance("store_user_message")
    @profile_function("store_user_message")
    async def _store_user_message_async(self, chat_id: UUID, message: ChatMessage):
        """Guardar mensaje del usuario de forma async con sesión separada"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._store_user_message_with_session, chat_id, message)

    @monitor_performance("save_assistant_message")
    @profile_function("save_assistant_message")
    async def _save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ):
        """Guardar respuesta del asistente de forma async con sesión separada"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, 
            self._save_assistant_message_with_session, 
            chat_id, content, token_count, executed_strategy_id
        )

    @monitor_performance("load_context_parallel")
    @profile_function("load_context_parallel")
    async def _load_context_parallel(
        self, 
        chat_id: str, 
        message: ChatMessage, 
        db_ids: List[UUID], 
        app_ids: List[UUID], 
        explorer: bool = False
    ) -> Dict[str, Any]:
        """Cargar contexto en paralelo con optimizaciones avanzadas"""
        try:
            # Crear loop para operaciones asíncronas
            loop = asyncio.get_event_loop()
            
            # Tareas paralelas optimizadas - solo cargar lo esencial
            tasks = [
                self._store_user_message_async(chat_id, message),
                self._load_history_async(chat_id),
                self._check_usage_limit_async(),
                self._load_database_schemas_async(db_ids),
                self._load_apps_async(app_ids)
            ]
            
            # Ejecutar todas las tareas en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Procesar resultados
            user_message_stored = results[0] if not isinstance(results[0], Exception) else False
            history = results[1] if not isinstance(results[1], Exception) else []
            usage_ok = results[2] if not isinstance(results[2], Exception) else True
            database_schemas = results[3] if not isinstance(results[3], Exception) else {}
            apps = results[4] if not isinstance(results[4], Exception) else []
            
            # Construir contexto básico - sin optimizaciones complejas por ahora
            context = {
                "chat_id": chat_id,
                "message": message,
                "history": history,
                "database_schemas": database_schemas,
                "apps": apps,
                "explorer": explorer,
                # Servicios básicos - se cargarán solo si se necesitan
                "functions": [],  # Se cargará solo si el usuario pide funciones
                "available_mcp_tools": {}  # Se cargará solo si el usuario pide MCP tools
            }
            
            logger.info(f"[OrchestratorService] 📊 Contexto básico cargado: {len(database_schemas)} DBs")
            return context
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error cargando contexto: {e}")
            # Fallback a contexto básico
            return {
                "chat_id": chat_id,
                "message": message,
                "history": [],
                "database_schemas": {},
                "apps": [],
                "functions": [],
                "available_mcp_tools": {},
                "explorer": explorer
            }
    
    async def _optimize_context_with_ai(
        self, 
        user_query: str, 
        database_schemas: Dict[UUID, List[Dict[str, Any]]], 
        db_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Optimizar contexto usando Vector Search y Prompt Engineering.
        
        Args:
            user_query: Query del usuario
            database_schemas: Esquemas de base de datos
            db_ids: IDs de las bases de datos
            
        Returns:
            Contexto optimizado con información semántica
        """
        try:
            vector_search = self.factory.get_vector_search_service()
            prompt_engineering = self.factory.get_prompt_engineering_service()
            
            optimized_context = {
                "optimized_schema": {},
                "semantic_hints": [],
                "prompt_optimization": {}
            }
            
            # Para cada base de datos, optimizar el contexto
            for db_id in db_ids:
                if db_id in database_schemas:
                    # 1. Búsqueda vectorial para encontrar elementos relevantes
                    search_results = await vector_search.semantic_search(
                        db_id, user_query, top_k=5
                    )
                    
                    # 2. Optimizar esquema basado en resultados de búsqueda
                    optimized_schema = self._optimize_schema_with_search_results(
                        database_schemas[db_id], search_results
                    )
                    
                    # 3. Optimizar prompt para la query específica
                    optimized_prompt = prompt_engineering.optimize_prompt_for_query(
                        user_query, optimized_schema, search_results
                    )
                    
                    # 4. Agregar al contexto optimizado
                    optimized_context["optimized_schema"][str(db_id)] = optimized_schema
                    optimized_context["semantic_hints"].extend(optimized_prompt.semantic_hints)
                    optimized_context["prompt_optimization"][str(db_id)] = {
                        "system_prompt": optimized_prompt.system_prompt,
                        "user_prompt": optimized_prompt.user_prompt,
                        "confidence_score": optimized_prompt.confidence_score,
                        "optimization_notes": optimized_prompt.optimization_notes
                    }
            
            logger.info(f"[OrchestratorService] 🦄 Contexto optimizado para {len(db_ids)} DBs")
            return optimized_context
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error optimizando contexto: {e}")
            return {
                "optimized_schema": {},
                "semantic_hints": [],
                "prompt_optimization": {}
            }
    
    def _optimize_schema_with_search_results(
        self, 
        schema: List[Dict[str, Any]], 
        search_results: List[Any]
    ) -> Dict[str, Any]:
        """
        Optimizar esquema basado en resultados de búsqueda vectorial.
        
        Args:
            schema: Esquema original
            search_results: Resultados de búsqueda vectorial
            
        Returns:
            Esquema optimizado con elementos más relevantes
        """
        try:
            # Crear esquema optimizado
            optimized_schema = {"tables": {}}
            
            # Procesar resultados de búsqueda para priorizar elementos relevantes
            relevant_elements = {}
            for result in search_results:
                element_id = result.element_id
                similarity_score = result.similarity_score
                relevance_boost = result.relevance_boost
                
                # Calcular score final
                final_score = similarity_score * relevance_boost
                relevant_elements[element_id] = final_score
            
            # Filtrar y ordenar tablas por relevancia
            for table in schema:
                table_name = table.get("name", "")
                table_relevance = 0.0
                
                # Calcular relevancia de la tabla basada en sus columnas
                for col in table.get("columns", []):
                    col_name = col.get("name", "")
                    element_id = f"column_{table_name}_{col_name}"
                    
                    if element_id in relevant_elements:
                        table_relevance += relevant_elements[element_id]
                
                # Solo incluir tablas con relevancia significativa
                if table_relevance > 0.1:  # Threshold mínimo
                    optimized_schema["tables"][table_name] = {
                        **table,
                        "relevance_score": table_relevance
                    }
            
            return optimized_schema
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error optimizando esquema: {e}")
            return {"tables": {}}

    @monitor_performance("load_database_schemas")
    @profile_function("load_database_schemas")
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[UUID, List[Dict[str, Any]]]:
        """Cargar esquemas de base de datos de forma async"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_database_schemas, db_ids)

    def _load_database_schemas(self, db_ids: List[UUID]) -> Dict[UUID, List[Dict[str, Any]]]:
        """Cargar esquemas de base de datos usando cache detallado"""
        try:
            schema_explorer = self.factory.get_schema_explorer_service()
            detailed_cache = self.factory.get_detailed_schema_cache()
            
            schemas = {}
            for db_id in db_ids:
                # Intentar obtener esquema detallado
                detailed_schema = detailed_cache.get_detailed_schema(db_id)
                if detailed_schema:
                    # Convertir a formato compatible con el sistema actual
                    tables = []
                    for table_name, table_info in detailed_schema.tables.items():
                        table_dict = {
                            "name": table_name,
                            "columns": [
                                {
                                    "name": col.name,
                                    "type": col.type,
                                    "nullable": col.nullable,
                                    "default": col.default,
                                    "primary_key": col.primary_key,
                                    "semantic_type": col.semantic_type.value
                                }
                                for col in table_info.columns.values()
                            ],
                            "primary_keys": table_info.primary_keys,
                            "foreign_keys": table_info.foreign_keys,
                            "indexes": table_info.indexes,
                            "row_count": table_info.row_count
                        }
                        tables.append(table_dict)
                    schemas[db_id] = tables
                else:
                    # Fallback al método anterior
                    schemas[db_id] = schema_explorer.get_schema_for_user_dbs(self.user_id, [db_id]).get(db_id, [])
            
            logger.info(f"[OrchestratorService] 📊 Esquemas detallados cargados: {len(schemas)}/{len(db_ids)} DBs")
            return schemas
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error cargando esquemas detallados: {e}")
            return {}

    @monitor_performance("load_agent_prompt")
    @profile_function("load_agent_prompt")
    async def _load_agent_prompt_async(self, agent_id: UUID) -> str:
        """Cargar prompt del agente de forma async"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_agent_prompt, agent_id)

    @monitor_performance("load_history")
    @profile_function("load_history")
    async def _load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Cargar historial de chat de forma asíncrona"""
        try:
            history_records = self._load_history_with_session(chat_id)
            
            # Convertir objetos ChatHistory a diccionarios serializables
            serializable_history = []
            for record in history_records:
                if hasattr(record, 'model_dump'):
                    # Si es un Pydantic model
                    serializable_history.append(record.model_dump())
                elif hasattr(record, '__dict__'):
                    # Si es un objeto SQLAlchemy
                    serializable_history.append({
                        'id': getattr(record, 'id', None),
                        'chat_id': str(getattr(record, 'chat_id', '')),
                        'user_id': getattr(record, 'user_id', None),
                        'role': getattr(record, 'role', ''),
                        'content': getattr(record, 'content', ''),
                        'name': getattr(record, 'name', None),
                        'token_count': getattr(record, 'token_count', None),
                        'is_function_call': getattr(record, 'is_function_call', False),
                        'function_call_id': getattr(record, 'function_call_id', None),
                        'executed_strategy_id': str(getattr(record, 'executed_strategy_id', '')) if getattr(record, 'executed_strategy_id', None) else None,
                        'created_at': getattr(record, 'created_at', '').isoformat() if getattr(record, 'created_at', None) else None,
                        'updated_at': getattr(record, 'updated_at', '').isoformat() if getattr(record, 'updated_at', None) else None
                    })
                else:
                    # Si ya es un diccionario
                    serializable_history.append(record)
            
            return serializable_history
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cargando historial: {e}")
            return []

    @monitor_performance("load_apps")
    @profile_function("load_apps")
    async def _load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Cargar aplicaciones de forma asíncrona"""
        try:
            if not app_ids:
                return []
            
            # Obtener información de las aplicaciones
            apps = []
            for app_id in app_ids:
                try:
                    # Aquí puedes implementar la lógica para cargar apps
                    # Por ahora retornamos una estructura básica
                    app_info = {
                        "id": str(app_id),
                        "name": f"App {app_id}",
                        "type": "default",
                        "config": {}
                    }
                    apps.append(app_info)
                except Exception as e:
                    logger.error(f"[OrchestratorService] ❌ Error cargando app {app_id}: {e}")
                    continue
            
            return apps
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cargando apps: {e}")
            return []

    @monitor_performance("load_functions")
    @profile_function("load_functions")
    async def _load_functions_async(self) -> List[Dict[str, Any]]:
        """Cargar funciones disponibles de forma asíncrona"""
        try:
            # Obtener funciones del executor service
            executor_service = self.factory.get_executor_service()
            functions = executor_service.get_available_functions()
            return functions
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cargando funciones: {e}")
            return []

    @monitor_performance("load_mcp_tools")
    @profile_function("load_mcp_tools")
    async def _load_mcp_tools_async(self) -> Dict[str, Any]:
        """Cargar herramientas MCP de forma asíncrona"""
        try:
            # Obtener herramientas MCP disponibles
            mcp_service = self.factory.get_mcp_service()
            tools = mcp_service.get_available_tools()
            return tools
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cargando MCP tools: {e}")
            return {}

    # ===================================================
    #  HELPERS (mantienen la funcionalidad original)
    # ===================================================
    def _select_graph_runner(self, explorer: bool):
        from app.services.graphs.exploration_graph import ExplorationGraph
        from app.services.graphs.guided_graph import GuidedGraph
        GraphClass = ExplorationGraph if explorer else GuidedGraph
        logger.info("[OrchestratorService] Using graph: %s", GraphClass.__name__)
        return GraphClass(self.factory)

    def _store_user_message_with_session(self, chat_id: UUID, message: ChatMessage) -> None:
        """Guardar mensaje del usuario con sesión separada"""
        db = SessionLocal()
        try:
            # Crear una nueva instancia del servicio con la sesión separada
            from app.core.service_factory import ServiceFactory
            temp_factory = ServiceFactory(db, self.factory.request)
            history_service = temp_factory.get_chat_history_service()
            
            history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role=message.role,
                    content=message.content,
                    name=message.name,
                    is_function_call=False,
                )
            )
            logger.info("[OrchestratorService] User message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store user message: %s", e)
        finally:
            db.close()

    def _save_assistant_message_with_session(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        """Guardar mensaje del asistente con sesión separada"""
        db = SessionLocal()
        try:
            # Crear una nueva instancia del servicio con la sesión separada
            from app.core.service_factory import ServiceFactory
            temp_factory = ServiceFactory(db, self.factory.request)
            history_service = temp_factory.get_chat_history_service()
            
            history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role="assistant",
                    content=content,
                    token_count=token_count,
                    is_function_call=False,
                    executed_strategy_id=executed_strategy_id,
                )
            )
            logger.info("[OrchestratorService] Assistant message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store assistant message: %s", e)
        finally:
            db.close()

    def _load_history_with_session(self, chat_id: UUID) -> List[Any]:
        """Cargar historial con sesión separada"""
        db = SessionLocal()
        try:
            # Crear una nueva instancia del servicio con la sesión separada
            from app.core.service_factory import ServiceFactory
            temp_factory = ServiceFactory(db, self.factory.request)
            history_service = temp_factory.get_chat_history_service()
            
            return history_service.get_history(chat_id, limit=20)
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to load history: %s", e)
            return []
        finally:
            db.close()

    def _store_user_message(self, chat_id: UUID, message: ChatMessage) -> None:
        """Método original (mantenido para compatibilidad)"""
        try:
            self.history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role=message.role,
                    content=message.content,
                    name=message.name,
                    is_function_call=False,
                )
            )
            logger.info("[OrchestratorService] User message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store user message: %s", e)

    def _load_agent_prompt(self, agent_id: Optional[UUID]) -> str:
        if not agent_id:
            return ""
        try:
            prompt = self.factory.get_agent_service().get_prompt(agent_id)
            logger.info("[OrchestratorService] Loaded prompt for agent_id=%s", agent_id)
            return prompt
        except Exception as e:
            logger.warning("[OrchestratorService] Agent prompt load failed: %s", e)
            return ""

    def _save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        """Método original (mantenido para compatibilidad)"""
        try:
            self.history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role="assistant",
                    content=content,
                    token_count=token_count,
                    is_function_call=False,
                    executed_strategy_id=executed_strategy_id,
                )
            )
            logger.info("[OrchestratorService] Assistant message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store assistant message: %s", e)

    def _check_usage_limit(self) -> None:
        """Verificar límites de uso"""
        try:
            self.factory.get_usage_service().check_limit()
        except Exception as e:
            logger.warning("[OrchestratorService] Usage limit check failed: %s", e)

    def _extract_assistant_response(self, execution_results: Dict[str, Any]) -> str:
        """Extraer la respuesta del asistente de los resultados de ejecución"""
        logger.info(f"[OrchestratorService] 🔍 Extrayendo respuesta de: {execution_results}")
        
        if isinstance(execution_results, dict):
            # Buscar la respuesta en diferentes campos posibles
            for key in ["assistant_response", "response", "content", "message"]:
                if key in execution_results and execution_results[key]:
                    logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en '{key}': {execution_results[key]}")
                    return str(execution_results[key])
            
            # Si hay error, devolver mensaje de error
            if "error" in execution_results:
                logger.error(f"[OrchestratorService] ❌ Error encontrado: {execution_results['error']}")
                return f"❌ Error: {execution_results['error']}"
            
            # Si hay execution_error, devolver mensaje de error
            if "execution_error" in execution_results:
                logger.error(f"[OrchestratorService] ❌ Error de ejecución: {execution_results['execution_error']}")
                return f"❌ Error de ejecución: {execution_results['execution_error']}"
            
            # Si no hay respuesta, devolver mensaje por defecto
            logger.warning("[OrchestratorService] ⚠️ No se encontró respuesta en los resultados")
        
        logger.error("[OrchestratorService] ❌ No se pudo extraer respuesta")
        return "🤖 No se pudo generar una respuesta"
