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

        # ⚡ OPTIMIZACIÓN: Ejecutar operaciones en paralelo (sin duplicación)
        # 🔧 FIX: _load_context_parallel ya maneja store_task y usage_task internamente
        context_tasks = await self._load_context_parallel(chat_id, message, db_ids, app_ids, explorer)
        
        # Actualizar el contexto con el parámetro explorer
        context_tasks["explorer"] = explorer

        # 🔧 FIX: Validar compact_schemas antes de ejecutar el grafo
        if db_ids and not self._validate_compact_schemas(context_tasks.get("compact_schemas", {}), db_ids):
            logger.error("[OrchestratorService] ❌ Sin schemas válidos para DBs solicitadas - abortando ejecución")
            return {
                "assistant_response": "❌ Error: No se pudo obtener información de las bases de datos solicitadas. Por favor, verifica la conexión.",
                "error": "missing_valid_schemas"
            }

        # 🎯 Ejecutar el grafo
        graph_runner = self._select_graph_runner(explorer)
        
        try:
            execution_results = await graph_runner.run(context_tasks)
            logger.info("[OrchestratorService] Graph execution completed")
            
            # 🔄 Ejecutar el plan si se generó uno
            if execution_results.get("plan"):
                logger.info("[OrchestratorService] 🚀 Ejecutando plan generado")
                plan_actions = len(execution_results['plan'].actions) if hasattr(execution_results['plan'], 'actions') else 'N/A'
                logger.info(f"[OrchestratorService] 📋 Plan generado con {plan_actions} acciones")
                execution_engine = self.factory.get_execution_engine_service()
                
                # Asegurar que el contexto tenga db_ids
                execution_context = context_tasks.copy()
                if db_ids:
                    execution_context["db_ids"] = db_ids  # 🔧 Mantener como UUID end-to-end
                
                # 🔧 FIX: Mover execution_engine.run a thread pool para evitar bloquear el loop
                loop = asyncio.get_running_loop()
                final_results = await loop.run_in_executor(
                    None,  # Usar default thread pool
                    lambda: execution_engine.run(
                        plan=execution_results["plan"].model_dump(),
                        chat_id=chat_id,
                        ctx=execution_context
                    )
                )
                # Combinar resultados
                execution_results.update(final_results)
                logger.info("[OrchestratorService] ✅ Plan ejecutado correctamente")
                logger.info(f"[OrchestratorService] 📤 Variables generadas: {len(final_results.get('variables', {}))}")
            else:
                logger.info("[OrchestratorService] 📝 No se generó plan, usando respuesta directa")
                # Manejar tanto diccionarios como objetos ChatMessage
                if hasattr(execution_results, 'get'):
                    # Es un diccionario
                    content_length = len(str(execution_results.get('message', {}).get('content', '')))
                else:
                    # Es un objeto (probablemente ChatMessage)
                    content_length = len(str(execution_results))
                logger.info(f"[OrchestratorService] 📤 Respuesta directa generada (longitud: {content_length} chars)")
                
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

    async def run_iterative_rag(
        self,
        chat_id: UUID,
        message: "ChatMessage",
        db_ids: List[UUID],
        app_ids: List[str],
        explorer: bool = False,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Versión iterativa del orchestrator que usa RAG para replanificar
        basándose en resultados intermedios.
        """
        logger.info(f"[OrchestratorService] 🔄 Iniciando flujo RAG iterativo (max {max_iterations} iteraciones)")

        
        # Inicialización similar al método run original
        perfmon = self.factory.get_performance_monitoring_service()
        perfmon.take_snapshot("iterative_orchestrator_start")
        
        # 🔧 FIX: _load_context_parallel ya maneja usage y store internamente
        context_tasks = await self._load_context_parallel(chat_id, message, db_ids, app_ids, explorer)
        context_tasks["explorer"] = explorer
        
        # Variables para el bucle iterativo
        iteration = 1
        accumulated_results = {}
        final_answer = None
        
        # Evaluador de resultados
        # 🔧 Result evaluator eliminado - funcionalidad integrada en el flujo principal
        
        while iteration <= max_iterations and not final_answer:
            logger.info(f"[OrchestratorService] 🔄 Iteración {iteration}/{max_iterations}")
            
            # 🔧 FIX: Validar compact_schemas antes de cada iteración
            db_ids = context_tasks.get("db_ids", [])
            if db_ids and not self._validate_compact_schemas(context_tasks.get("compact_schemas", {}), db_ids):
                logger.error(f"[OrchestratorService] ❌ Sin schemas válidos en iteración {iteration} - abortando")
                return {
                    "assistant_response": "❌ Error: No se pudo obtener información de las bases de datos en esta iteración.",
                    "error": "missing_valid_schemas_iteration"
                }

            # Ejecutar grafo (exploración o plan específico)
            # 🔧 SIMPLIFICADO: Solo usar exploración en todas las iteraciones
            graph_runner = self._select_graph_runner(True)  # Siempre exploración
            execution_results = await graph_runner.run(context_tasks)
            
            # Si el grafo devuelve una respuesta directa, terminar
            if execution_results.get("assistant_response") and not execution_results.get("plan"):
                final_answer = execution_results["assistant_response"]
                logger.info(f"[OrchestratorService] ✅ Respuesta directa obtenida en iteración {iteration}")
                break
            
            # Acumular resultados
            if execution_results.get("variables"):
                accumulated_results.update(execution_results["variables"])
            
            # 🔧 SIMPLIFICADO: Evaluación básica sin evaluador externo
            logger.info(f"[OrchestratorService] 📊 Iteración {iteration} completada - {len(accumulated_results)} variables acumuladas")
            
            # Decidir si continuar basándose en criterios simples
            if accumulated_results and iteration >= 2:
                logger.info("[OrchestratorService] ✅ Información suficiente encontrada después de 2 iteraciones")
                
                # Generar respuesta final con toda la información acumulada
                final_answer = await self._generate_final_answer(
                    message.content, accumulated_results, context_tasks
                )
                break
            
            iteration += 1
        
        # Si llegamos al máximo de iteraciones sin respuesta completa
        if not final_answer:
            logger.warning(f"[OrchestratorService] ⚠️ Máximo de iteraciones alcanzado ({max_iterations})")
            final_answer = await self._generate_final_answer(
                message.content, accumulated_results, context_tasks
            )
        
        # Guardar respuesta del asistente
        await self._save_assistant_message_async(
            chat_id=chat_id,
            content=final_answer,
            token_count=None,  # TODO: calcular tokens
            executed_strategy_id=None,
        )
        
        perfmon.take_snapshot("iterative_orchestrator_end")
        
        return {
            "assistant_response": final_answer,
            "execution_results": accumulated_results,
            "iterations_used": iteration - 1,
            "steps": [],  # TODO: agregar pasos detallados
        }

    def _validate_compact_schemas(self, compact_schemas: Dict, db_ids: List) -> bool:
        """Validar que hay compact_schemas válidos para las DBs solicitadas"""
        if not compact_schemas or not db_ids:
            return False
        
        for db_id in db_ids:
            # Convertir a str si es UUID para comparación
            db_key = str(db_id) if hasattr(db_id, 'hex') else db_id
            
            # Buscar tanto con UUID como con str
            schema_found = False
            for key in [db_id, db_key, str(db_id)]:
                if key in compact_schemas and compact_schemas[key] and compact_schemas[key].strip():
                    schema_found = True
                    break
            
            if not schema_found:
                logger.warning(f"[OrchestratorService] ⚠️ No hay compact_schema válido para DB {db_id}")
                return False
        
        logger.info(f"[OrchestratorService] ✅ Compact schemas válidos para {len(db_ids)} DBs")
        return True

    async def _generate_final_answer(
        self, 
        question: str, 
        accumulated_results: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Genera la respuesta final basándose en todos los resultados acumulados.
        """
        logger.info("[OrchestratorService] 📝 Generando respuesta final con información acumulada")
        
        # Construir prompt con toda la información
        results_summary = self._format_results_for_final_answer(accumulated_results)
        
        final_prompt = f"""
Pregunta del usuario: {question}

Información encontrada en la base de datos:
{results_summary}

Por favor, responde la pregunta del usuario de manera clara y completa usando la información encontrada.
Si no encuentras información específica, menciona qué se buscó y qué alternativas podrían existir.
"""
        
        try:
            openai_service = self.factory.get_openai_service()
            response = openai_service.complete_chat([
                {"role": "system", "content": "Eres un asistente experto que responde preguntas basándose en datos de base de datos. Sé claro, preciso y útil."},
                {"role": "user", "content": final_prompt}
            ])
            return response
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error generando respuesta final: {e}")
            return f"He encontrado información en tu base de datos, pero hubo un error al generar la respuesta final. Información encontrada: {results_summary}"

    def _format_results_for_final_answer(self, results: Dict[str, Any]) -> str:
        """Formatea los resultados acumulados para la respuesta final"""
        formatted = []
        
        for key, value in results.items():
            if isinstance(value, list):
                if len(value) <= 20:  # Mostrar listas pequeñas completas
                    formatted.append(f"- {key}: {value}")
                else:
                    formatted.append(f"- {key}: {value[:10]}... (y {len(value)-10} más)")
            elif isinstance(value, dict):
                if value.get("error"):
                    formatted.append(f"- {key}: Error - {value['error']}")
                else:
                    formatted.append(f"- {key}: {value}")
            else:
                formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted) if formatted else "No se encontró información específica."

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
            loop = asyncio.get_running_loop()  # 🔧 Python 3.11+ compatible
            
            # Tareas paralelas optimizadas - solo cargar lo esencial
            tasks = [
                self._store_user_message_async(chat_id, message),
                self._load_history_async(chat_id),
                self._check_usage_limit_async(),
                self._load_database_schemas_async(db_ids),
                self._load_apps_async(app_ids)
            ]
            
            # 🔧 FIX: Ejecutar con timeout para evitar bloqueos
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0  # 30 segundos timeout
                )
            except asyncio.TimeoutError:
                logger.error("[OrchestratorService] ⏰ Timeout en _load_context_parallel - usando valores por defecto")
                results = [False, [], True, {'schemas': {}, 'compact_schemas': {}, 'cache_status': {}}, []]
            
            # Procesar resultados
            user_message_stored = results[0] if not isinstance(results[0], Exception) else False
            history = results[1] if not isinstance(results[1], Exception) else []
            usage_ok = results[2] if not isinstance(results[2], Exception) else True
            schema_result = results[3] if not isinstance(results[3], Exception) else {
                'schemas': {}, 'compact_schemas': {}, 'cache_status': {}
            }
            apps = results[4] if not isinstance(results[4], Exception) else []
            
            # Extraer componentes del schema result
            database_schemas = schema_result.get('schemas', {})  # Legacy format
            compact_schemas = schema_result.get('compact_schemas', {})  # Para LLM
            cache_status = schema_result.get('cache_status', {})  # Para debugging
            
            # Construir contexto básico - sin optimizaciones complejas por ahora
            context = {
                "chat_id": chat_id,
                "message": message,
                "history": history,
                "database_schemas": database_schemas,  # Legacy format (mantener compatibilidad)
                "compact_schemas": compact_schemas,  # 🔧 NUEVO: Para el LLM
                "cache_status": cache_status,  # Para debugging
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
                    optimized_context["optimized_schema"][db_id] = optimized_schema  # 🔧 UUID como clave
                    optimized_context["semantic_hints"].extend(optimized_prompt.semantic_hints)
                    optimized_context["prompt_optimization"][db_id] = {  # 🔧 UUID como clave
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
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Cargar esquemas de base de datos con ensure_warm (L1/L2/L3 → introspección).
        
        Returns:
            Dict con:
            - 'schemas': Dict[UUID, List[Dict]] - Esquemas detallados (legacy)
            - 'compact_schemas': Dict[UUID, str] - Esquemas compactos para LLM
            - 'cache_status': Dict[UUID, str] - Estado del cache por DB
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._ensure_warm_schemas, db_ids)

    def _ensure_warm_schemas(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Implementa ensure_warm: L1/L2/L3 → introspección mínima.
        Garantiza que siempre hay schema compacto disponible para el LLM.
        """
        try:
            cache_service = self.factory.get_detailed_schema_cache_service()
            
            schemas = {}  # Legacy format
            compact_schemas = {}  # Para el LLM
            cache_status = {}  # Para debugging
            
            for db_id in db_ids:
                logger.info(f"[OrchestratorService] 🔍 Ensure warm para DB {db_id}")
                
                try:
                    # 🔧 PASO 1: Intentar obtener de cache (L1/L2)
                    cache_entry = cache_service.get_schema_cache(self.user_id, db_id)
                    
                    if cache_entry and cache_entry.compact:
                        # ✅ Cache HIT - tenemos schema compacto
                        logger.info(f"[OrchestratorService] ⚡ Cache HIT para DB {db_id}")
                        compact_schemas[db_id] = cache_entry.compact
                        cache_status[db_id] = "cache_hit"
                        
                        # Convertir snapshot a formato legacy si es necesario
                        if cache_entry.snapshot and cache_entry.snapshot.tables:
                            schemas[db_id] = self._convert_snapshot_to_legacy(cache_entry.snapshot.tables)
                        else:
                            schemas[db_id] = []
                    
                    else:
                        # ❌ Cache MISS - hacer introspección mínima (L3)
                        logger.warning(f"[OrchestratorService] 🔄 Cache MISS para DB {db_id} - introspección mínima")
                        cache_status[db_id] = "cache_miss_introspecting"
                        
                        # Hacer introspección básica y crear cache
                        introspected_schema = self._introspect_minimal_schema(db_id)
                        
                        if introspected_schema:
                            # Crear cache entry
                            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
                            
                            snapshot = SchemaSnapshot(
                                tables=introspected_schema['tables'],
                                dialect=introspected_schema.get('dialect', 'unknown')
                            )
                            
                            # Crear y guardar cache
                            cache_entry = cache_service.create_or_update_cache(
                                user_id=self.user_id,
                                db_id=db_id,
                                snapshot=snapshot,
                                enrichment_level=EnrichmentLevel.BASIC
                            )
                            
                            compact_schemas[db_id] = cache_entry.compact
                            schemas[db_id] = self._convert_snapshot_to_legacy(introspected_schema['tables'])
                            cache_status[db_id] = "cache_created"
                            
                            logger.info(f"[OrchestratorService] ✨ Cache creado para DB {db_id}")
                        else:
                            # Introspección falló - schema vacío
                            logger.error(f"[OrchestratorService] ❌ Introspección falló para DB {db_id}")
                            compact_schemas[db_id] = "-- No schema available --"
                            schemas[db_id] = []
                            cache_status[db_id] = "introspection_failed"
                
                except Exception as e:
                    logger.exception(f"[OrchestratorService] ❌ Error ensure_warm DB {db_id}: {e}")
                    compact_schemas[db_id] = f"-- Error loading schema: {str(e)} --"
                    schemas[db_id] = []
                    cache_status[db_id] = "error"
            
            # Log resumen
            hits = sum(1 for status in cache_status.values() if status == "cache_hit")
            misses = sum(1 for status in cache_status.values() if status.startswith("cache_miss"))
            
            logger.info(f"[OrchestratorService] 📊 Ensure warm completado: {hits} hits, {misses} misses, {len(db_ids)} total")
            
            return {
                'schemas': schemas,  # Legacy format para compatibilidad
                'compact_schemas': compact_schemas,  # Para el LLM
                'cache_status': cache_status  # Para debugging
            }
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error crítico en ensure_warm: {e}")
            # Fallback seguro
            return {
                'schemas': {db_id: [] for db_id in db_ids},
                'compact_schemas': {db_id: "-- Error loading schemas --" for db_id in db_ids},
                'cache_status': {db_id: "critical_error" for db_id in db_ids}
            }
    
    def _introspect_minimal_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección mínima de schema para crear cache básico"""
        try:
            database_service = self.factory.get_database_service()
            db_instance = database_service.get_sql_instance(db_id)
            
            if not db_instance:
                return None
            
            # Query básica para obtener tablas y columnas
            tables_query = """
                SELECT 
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """
            
            # 🔧 FIX: Usar API pública con engine.connect() y text() para obtener filas
            from sqlalchemy import text
            with db_instance._engine.connect() as conn:
                result = conn.execute(text(tables_query))
                rows = [dict(row._mapping) for row in result]
            
            # Procesar resultado en formato de snapshot
            tables = {}
            for row in rows:
                table_name = row['table_name']
                if table_name not in tables:
                    tables[table_name] = {
                        'columns': {},
                        'primary_keys': [],
                        'foreign_keys': [],
                        'indexes': []
                    }
                
                tables[table_name]['columns'][row['column_name']] = {
                    'type': row['data_type'],
                    'nullable': row['is_nullable'] == 'YES',
                    'default': row['column_default'],
                    'primary_key': False  # Se puede enriquecer después
                }
            
            logger.info(f"[OrchestratorService] 🔍 Introspección básica: {len(tables)} tablas")
            
            return {
                'tables': tables,
                'dialect': 'postgresql'  # Asumimos PostgreSQL por ahora
            }
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error introspección mínima DB {db_id}: {e}")
            return None
    
    def _convert_snapshot_to_legacy(self, snapshot_tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convierte formato de snapshot a formato legacy para compatibilidad"""
        tables = []
        for table_name, table_info in snapshot_tables.items():
            table_dict = {
                "name": table_name,
                "columns": [
                    {
                        "name": col_name,
                        "type": col_info.get('type', 'unknown'),
                        "nullable": col_info.get('nullable', True),
                        "default": col_info.get('default'),
                        "primary_key": col_info.get('primary_key', False)
                    }
                    for col_name, col_info in table_info.get('columns', {}).items()
                ],
                "primary_keys": table_info.get('primary_keys', []),
                "foreign_keys": table_info.get('foreign_keys', []),
                "indexes": table_info.get('indexes', [])
            }
            tables.append(table_dict)
        return tables

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
        logger.info(f"[OrchestratorService] 🔍 Extrayendo respuesta del resultado (keys: {list(execution_results.keys()) if isinstance(execution_results, dict) else 'no dict'})")
        
        if isinstance(execution_results, dict):
            # Buscar la respuesta en diferentes campos posibles
            for key in ["assistant_response", "response", "content", "message"]:
                if key in execution_results and execution_results[key]:
                    # 🔧 FIX: Si es un dict con 'content', extraer el content
                    response_value = execution_results[key]
                    if isinstance(response_value, dict) and 'content' in response_value:
                        actual_response = response_value['content']
                        logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en '{key}.content' (longitud: {len(str(actual_response))} chars)")
                        return str(actual_response)
                    else:
                        response_length = len(str(response_value))
                        logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en '{key}' (longitud: {response_length} chars)")
                        return str(response_value)
            
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
