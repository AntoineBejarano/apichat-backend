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
import json
import time
from datetime import datetime, timezone
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
    # 🔒 CONTROL DE TOKENS - Presupuesto por llamada (actualizado)
    MAX_INPUT_TOKENS = 8000  # Presupuesto sugerido para input
    MAX_OUTPUT_TOKENS = 2048  # Cap de output tokens
    MAX_HISTORY_TURNS = 6     # Máximo de turnos de historial (reducido de 8 a 6)
    MAX_SCHEMA_CHARS = 3000   # Máximo de caracteres de schema (reducido de 4000 a 3000)
    TOP_K_DBS = 2             # Top-K bases de datos
    TOP_K_APPS = 2            # Top-K aplicaciones
    
    # 🔒 CONTROL DE TOKENS - Límites adicionales para trimming inteligente
    MAX_HISTORY_CHARS = 5000  # Máximo de caracteres de historial
    MAX_APP_DESCRIPTOR_CHARS = 2000  # Máximo de caracteres de descriptores de apps
    MAX_FUNCTION_DESCRIPTION_CHARS = 100  # Máximo de caracteres por descripción de función

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        self.history_service = factory.get_chat_history_service()
        
        # 🔒 CONTROL DE TOKENS - Token bucket para rate limiting
        self._token_bucket = {
            "tokens_used": 0,
            "window_start": time.time(),
            "window_size": 60,  # 1 minuto
            "max_tokens_per_window": 10000  # Límite de OpenAI
        }
        
        logger.info(f"[OrchestratorService] Initialized for user_id={self.user_id}")

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

        # 🔒 CONTROL DE TOKENS: Aplicar presupuesto antes de cargar contexto
        db_ids = self._apply_token_budget_to_db_ids(db_ids)
        app_ids = self._apply_token_budget_to_app_ids(app_ids)
        
        # 🔒 CONTROL DE TOKENS: Verificar token bucket antes de proceder
        if not self._check_token_bucket():
            logger.warning("[OrchestratorService] 🔒 Token bucket limitado - usando contexto mínimo")
            return await self._handle_message_with_minimal_context(
                chat_id, db_ids, app_ids, explorer, agent_id, message
            )
        
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

        # 🔒 CONTROL DE TOKENS: Aplicar trimming dinámico al contexto
        trimmed_context = self._apply_intelligent_context_trimming(context_tasks)
        
        # 🎯 Ejecutar el grafo
        graph_runner = self._select_graph_runner(explorer)
        
        try:
            execution_results = await graph_runner.run(trimmed_context)
            logger.info("[OrchestratorService] Graph execution completed")
            
            # 🔄 NORMALIZAR SIEMPRE la salida del grafo a dict antes de tocarla
            execution_results = self._normalize_graph_output(execution_results)
            logger.info(f"[OrchestratorService] ✅ Salida del grafo normalizada a dict con claves: {list(execution_results.keys())}")
            
            # 🔒 CONTROL DE TOKENS: Forzar plan cuando hay intención de base de datos
            if self._should_force_plan(db_ids, message.content, execution_results):
                logger.info("[OrchestratorService] 🔒 Forzando generación de plan por intención de base de datos")
                if not execution_results.get("plan"):
                    # Generar plan mínimo si no se generó uno
                    execution_results["plan"] = self._generate_minimal_plan_for_db_intention(message.content, db_ids)
            
            # 🔄 Ejecutar el plan si se generó uno
            if execution_results.get("plan"):
                logger.info("[OrchestratorService] 🚀 Ejecutando plan generado")
                
                # 🔧 FIX: Preservar los steps originales del plan antes de ejecutarlo
                original_steps = execution_results.get("plan", {}).get("steps", [])
                logger.info(f"[OrchestratorService] 📋 Plan generado con {len(original_steps)} steps originales")
                
                plan_actions = len(execution_results.get('plan', {}).get('actions', [])) if execution_results.get('plan', {}).get('actions') else 0
                logger.info(f"[OrchestratorService] 📋 Plan generado con {plan_actions} acciones")
                execution_engine = self.factory.get_execution_engine_service()
                
                # Asegurar que el contexto tenga db_ids
                execution_context = trimmed_context.copy()
                if db_ids:
                    execution_context["db_ids"] = db_ids  # 🔧 Mantener como UUID end-to-end
                
                # 🔧 FIX: Mover execution_engine.run a thread pool para evitar bloquear el loop
                loop = asyncio.get_running_loop()
                final_results = await loop.run_in_executor(
                    None,  # Usar default thread pool
                    lambda: execution_engine.run(
                        plan=execution_results.get("plan", {}),
                        chat_id=chat_id,
                        ctx=execution_context
                    )
                )
                # Combinar resultados
                execution_results.update(final_results)
                
                # 🔧 FIX: Preservar los steps originales del plan
                execution_results["steps"] = original_steps
                logger.info("[OrchestratorService] ✅ Plan ejecutado correctamente")
                logger.info(f"[OrchestratorService] 📤 Variables generadas: {len(final_results.get('variables', {}))}")
                logger.info(f"[OrchestratorService] 📋 Steps preservados: {len(original_steps)}")
            else:
                logger.info("[OrchestratorService] 📝 No se generó plan, usando respuesta directa")
                # Ahora execution_results es SIEMPRE un dict, calcular longitud de forma segura
                content_length = self._calculate_content_length(execution_results)
                logger.info(f"[OrchestratorService] 📤 Respuesta directa generada (longitud: {content_length} chars)")
                
        except Exception as e:
            logger.exception("[OrchestratorService] Graph execution failed: %s", e)
            execution_results = {"error": str(e)}

        # 📝 Guardar respuesta del asistente
        assistant_response = self._extract_assistant_response(execution_results)
        
        # 💾 Guardar mensaje del asistente de forma async
        # Ahora execution_results es SIEMPRE un dict
        token_count = execution_results.get("token_count")
        executed_strategy_id = execution_results.get("executed_strategy_id")
        steps = execution_results.get("steps", [])
        
        # 🔍 DEBUG: Log del assistant_response antes de guardar
        logger.info(f"[OrchestratorService] 🔍 ASSISTANT_RESPONSE extraído: '{assistant_response}' (tipo: {type(assistant_response)}, longitud: {len(str(assistant_response))})")
        
        await self._save_assistant_message_async(
            chat_id=chat_id,
            content=assistant_response,
            token_count=token_count,
            executed_strategy_id=executed_strategy_id,
        )

        # 🔒 CONTROL DE TOKENS: Actualizar token bucket
        estimated_tokens = self._estimate_tokens_for_context(trimmed_context)
        self._update_token_bucket(estimated_tokens)

        # 📊 Profiling final
        memory_profiler.take_snapshot("orchestrator_end")

        # 🔧 FIX: Determinar el tipo de respuesta basado en si hay steps
        if steps and len(steps) > 0:
            # Si hay steps, devolver respuesta tipo "step" para el websocket
            final_response = {
                "type": "step",
                "message": assistant_response,
                "steps": steps,
                "execution_results": execution_results,
                "formatted": True,
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"[OrchestratorService] 🎯 DEVOLVIENDO RESPUESTA FINAL tipo 'step'")
            logger.info(f"[OrchestratorService] 🎯 MESSAGE field: '{final_response['message']}' (tipo: {type(final_response['message'])})")
            logger.info(f"[OrchestratorService] 🎯 STEPS count: {len(final_response['steps'])}")
            logger.info(f"[OrchestratorService] 🎯 EXECUTION_RESULTS keys: {list(final_response['execution_results'].keys())}")
            return final_response
        else:
            # Si no hay steps, devolver respuesta normal
            final_response = {
                "assistant_response": assistant_response,
                "execution_results": execution_results,
                "steps": steps,
            }
            logger.info(f"[OrchestratorService] 🎯 DEVOLVIENDO RESPUESTA FINAL tipo normal: {final_response}")
            return final_response

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
            
            # 🔄 NORMALIZAR SIEMPRE la salida del grafo a dict antes de tocarla
            execution_results = self._normalize_graph_output(execution_results)
            logger.info(f"[OrchestratorService] ✅ Salida del grafo normalizada en iteración {iteration} (claves: {list(execution_results.keys())})")
            
            # Si el grafo devuelve una respuesta directa, terminar
            if (execution_results.get("assistant_response") and 
                not execution_results.get("plan")):
                final_answer = execution_results.get("assistant_response", "")
                logger.info(f"[OrchestratorService] ✅ Respuesta directa obtenida en iteración {iteration}")
                break
            
            # Acumular resultados
            if execution_results.get("variables"):
                accumulated_results.update(execution_results.get("variables", {}))
            
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
        """Verificar límite de uso con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                usage_service = temp_factory.get_usage_service()
                
                # Verificar límite de uso
                usage_ok = usage_service.check_limit()
                
                logger.info(f"[OrchestratorService] Usage limit checked with separate session: {usage_ok}")
                return usage_ok
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to check usage limit: {e}")
            return True  # Permitir por defecto si falla la verificación

    @monitor_performance("store_user_message")
    @profile_function("store_user_message")
    async def _store_user_message_async(self, chat_id: UUID, message: ChatMessage):
        """Guardar mensaje del usuario con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
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
                logger.info("[OrchestratorService] User message stored with separate session")
                return True
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to store user message: {e}")
            return False

    @monitor_performance("save_assistant_message")
    @profile_function("save_assistant_message")
    async def _save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ):
        """Guardar mensaje del asistente con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                history_service = temp_factory.get_chat_history_service()
                
                history_service.create_message(
                    data=ChatHistoryCreate(
                        chat_id=chat_id,
                        user_id=self.user_id,
                        role="assistant",
                        content=content,
                        name=None,
                        is_function_call=False,
                    )
                )
                logger.info("[OrchestratorService] Assistant message saved with separate session")
                return True
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to save assistant message: {e}")
            return False

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
        """Cargar contexto en paralelo con optimizaciones avanzadas y sesiones separadas"""
        try:
            # Crear loop para operaciones asíncronas
            loop = asyncio.get_running_loop()  # 🔧 Python 3.11+ compatible
            
            # 🔧 FIX: Crear sesiones separadas para cada tarea para evitar conflictos de concurrencia
            from app.core.database import SessionLocal
            
            # Tareas paralelas optimizadas - cada una con su propia sesión
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
                # 🔧 FIX: Incluir db_ids y app_ids para que el grafo los reconozca
                "db_ids": db_ids,
                "app_ids": app_ids,
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
                "explorer": explorer,
                # 🔧 FIX: Incluir db_ids y app_ids en fallback también
                "db_ids": db_ids,
                "app_ids": app_ids
            }
    
    # 🔒 CONTROL DE TOKENS - Métodos de presupuesto
    def _apply_token_budget_to_db_ids(self, db_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """
        Aplica presupuesto de tokens limitando el número de bases de datos.
        """
        if not db_ids:
            return db_ids
        
        # Limitar a TOP_K_DBS para controlar tokens
        limited_db_ids = db_ids[:self.TOP_K_DBS]
        
        if len(limited_db_ids) < len(db_ids):
            logger.info(f"[OrchestratorService] 🔒 Token budget: limitando DBs de {len(db_ids)} a {len(limited_db_ids)}")
        
        return limited_db_ids
    
    def _apply_token_budget_to_app_ids(self, app_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """
        Aplica presupuesto de tokens limitando el número de aplicaciones.
        """
        if not app_ids:
            return app_ids
        
        # Limitar a TOP_K_APPS para controlar tokens
        limited_app_ids = app_ids[:self.TOP_K_APPS]
        
        if len(limited_app_ids) < len(app_ids):
            logger.info(f"[OrchestratorService] 🔒 Token budget: limitando apps de {len(app_ids)} a {len(limited_app_ids)}")
        
        return limited_app_ids
    
    def _estimate_tokens_for_context(self, context: Dict[str, Any]) -> int:
        """
        Estima el número de tokens para el contexto.
        """
        try:
            # Estimación aproximada: 1 token ≈ 4 caracteres
            total_chars = 0
            
            # Historial
            history = context.get("history", [])
            for msg in history:
                content = msg.get("content", "")
                total_chars += len(content)
            
            # Schemas de DB
            schemas = context.get("database_schemas", {})
            for db_schema in schemas.values():
                if isinstance(db_schema, list):
                    for table in db_schema:
                        if isinstance(table, dict):
                            total_chars += len(str(table))
            
            # Apps
            apps = context.get("apps", [])
            for app in apps:
                if isinstance(app, dict):
                    total_chars += len(str(app))
            
            # Mensaje del usuario
            message = context.get("message", {})
            if isinstance(message, dict):
                total_chars += len(str(message))
            
            estimated_tokens = total_chars // 4
            logger.info(f"[OrchestratorService] 🔍 Tokens estimados: {estimated_tokens} (chars: {total_chars})")
            
            return estimated_tokens
            
        except Exception as e:
            logger.warning(f"[OrchestratorService] ⚠️ Error estimando tokens: {e}")
            return 0
    
    def _should_use_lite_payload(self, estimated_tokens: int) -> bool:
        """
        Determina si se debe usar payload lite basado en estimación de tokens.
        """
        return estimated_tokens > self.MAX_INPUT_TOKENS
    
    async def _build_lite_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye un payload lite para evitar exceder límites de tokens.
        """
        logger.info("[OrchestratorService] 🔒 Construyendo payload lite para control de tokens")
        
        lite_context = context.copy()
        
        # 1. Limitar historial a últimos turnos
        history = context.get("history", [])
        if len(history) > self.MAX_HISTORY_TURNS:
            lite_context["history"] = history[-self.MAX_HISTORY_TURNS:]
            logger.info(f"[OrchestratorService] 🔒 Historial recortado: {len(history)} → {len(lite_context['history'])} turnos")
        
        # 2. Limitar schema a caracteres máximos
        schemas = context.get("database_schemas", {})
        if schemas:
            lite_schemas = {}
            for db_id, db_schema in schemas.items():
                if isinstance(db_schema, list):
                    # Solo incluir lista de tablas y schema truncado
                    table_names = [table.get("name", "unknown") for table in db_schema if isinstance(table, dict)]
                    lite_schemas[db_id] = {
                        "table_names": table_names,
                        "schema_preview": str(db_schema)[:self.MAX_SCHEMA_CHARS]
                    }
            
            lite_context["database_schemas"] = lite_schemas
            logger.info(f"[OrchestratorService] 🔒 Schema recortado a {self.MAX_SCHEMA_CHARS} chars")
        
        # 3. Limitar apps a TOP_K
        apps = context.get("apps", [])
        if len(apps) > self.TOP_K_APPS:
            lite_context["apps"] = apps[:self.TOP_K_APPS]
            logger.info(f"[OrchestratorService] 🔒 Apps limitadas: {len(apps)} → {len(lite_context['apps'])}")
        
        return lite_context

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
        # 🔧 FIX: Crear una nueva sesión para evitar conflictos de concurrencia
        from app.core.database import SessionLocal
        
        def _ensure_warm_schemas_with_new_session(db_ids: List[UUID]) -> Dict[str, Any]:
            """Wrapper que crea una nueva sesión para evitar conflictos de concurrencia"""
            db = SessionLocal()
            try:
                # Crear un nuevo factory con la nueva sesión
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                
                # Crear una instancia temporal del servicio con la nueva sesión
                from app.services.detailed_schema_cache_service import DetailedSchemaCacheService
                temp_cache_service = DetailedSchemaCacheService(temp_factory)
                
                schemas = {}  # Legacy format
                compact_schemas = {}  # Para el LLM
                cache_status = {}  # Para debugging
                
                for db_id in db_ids:
                    logger.info(f"[OrchestratorService] 🔍 Ensure warm para DB {db_id}")
                    
                    try:
                        # 🔧 PASO 1: Intentar obtener de cache (L1/L2)
                        cache_entry = temp_cache_service.get_schema_cache(self.user_id, db_id)
                        
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
                                    dialect=introspected_schema.get('dialect', 'unknown'),
                                    generated_at=datetime.now(timezone.utc)  # Usar datetime.now(timezone.utc) en lugar del valor por defecto
                                )
                                
                                # Crear y guardar cache
                                cache_entry = temp_cache_service.create_or_update_cache(
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
                
                # 🔒 CONTROL DE TOKENS: Aplicar límite de caracteres a compact_schemas
                for db_id, schema_content in compact_schemas.items():
                    if isinstance(schema_content, str) and len(schema_content) > self.MAX_SCHEMA_CHARS:
                        original_length = len(schema_content)
                        compact_schemas[db_id] = schema_content[:self.MAX_SCHEMA_CHARS] + "... [truncado]"
                        logger.info(f"[OrchestratorService] 🔒 Token budget: schema DB {db_id} truncado de {original_length} a {self.MAX_SCHEMA_CHARS} chars")
                
                return {
                    'schemas': schemas,  # Legacy format para compatibilidad
                    'compact_schemas': compact_schemas,  # Para el LLM
                    'cache_status': cache_status  # Para debugging
                }
            finally:
                db.close()
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _ensure_warm_schemas_with_new_session, db_ids)
    
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
        """Cargar prompt del agente con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                agent_service = temp_factory.get_agent_service()
                
                # Obtener prompt del agente
                agent = agent_service.get_agent(agent_id)
                if agent and agent.prompt:
                    logger.info(f"[OrchestratorService] Agent prompt loaded with separate session for agent {agent_id}")
                    return agent.prompt
                else:
                    logger.warning(f"[OrchestratorService] No prompt found for agent {agent_id}")
                    return ""
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load agent prompt: {e}")
            return ""

    @monitor_performance("load_history")
    @profile_function("load_history")
    async def _load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Cargar historial del chat con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                history_service = temp_factory.get_chat_history_service()
                
                # Obtener historial
                history = history_service.get_chat_history(chat_id)
                
                # Convertir a formato de diccionario de forma segura
                history_dicts = []
                for msg in history:
                    try:
                        # 🔧 FIX: Usar método auxiliar para conversión segura
                        msg_dict = self._safe_sqlalchemy_to_dict(msg)
                        
                        # 🔧 FIX: Asegurar campos requeridos con valores por defecto
                        msg_dict = {
                            'role': msg_dict.get('role', 'unknown'),
                            'content': msg_dict.get('content', ''),
                            'name': msg_dict.get('name'),
                            'timestamp': msg_dict.get('timestamp'),
                            'is_function_call': msg_dict.get('is_function_call', False)
                        }
                        
                        history_dicts.append(msg_dict)
                        
                    except Exception as msg_error:
                        logger.warning(f"[OrchestratorService] Error procesando mensaje del historial: {msg_error}")
                        # Agregar mensaje básico en caso de error
                
                # 🔒 CONTROL DE TOKENS: Aplicar límite de turnos de historial
                if len(history_dicts) > self.MAX_HISTORY_TURNS:
                    original_count = len(history_dicts)
                    history_dicts = history_dicts[-self.MAX_HISTORY_TURNS:]
                    logger.info(f"[OrchestratorService] 🔒 Token budget: historial limitado de {original_count} a {len(history_dicts)} turnos")
                
                logger.info(f"[OrchestratorService] History loaded with separate session: {len(history_dicts)} messages")
                return history_dicts
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load history: {e}")
            return []

    @monitor_performance("load_apps")
    @profile_function("load_apps")
    async def _load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Cargar aplicaciones con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                app_service = temp_factory.get_app_service()
                
                # Obtener aplicaciones
                apps = []
                for app_id in app_ids:
                    try:
                        app = app_service.get_by_id(app_id)
                        if app:
                            apps.append({
                                'id': str(app.id),
                                'name': app.name,
                                'description': app.description,
                                'type': app.type,
                                'config': app.config
                            })
                    except Exception as e:
                        logger.warning(f"[OrchestratorService] Failed to load app {app_id}: {e}")
                        continue
                
                logger.info(f"[OrchestratorService] Apps loaded with separate session: {len(apps)} apps")
                return apps
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load apps: {e}")
            return []

    @monitor_performance("load_functions")
    @profile_function("load_functions")
    async def _load_functions_async(self) -> List[Dict[str, Any]]:
        """Cargar funciones disponibles con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                function_service = temp_factory.get_function_service()
                
                # Obtener funciones disponibles
                functions = function_service.get_functions()
                
                # Convertir a formato de diccionario
                function_dicts = []
                for func in functions:
                    function_dicts.append({
                        'id': func.id,
                        'name': func.name,
                        'description': func.description,
                        'parameters': func.parameters,
                        'group_id': func.group_id
                    })
                
                logger.info(f"[OrchestratorService] Functions loaded with separate session: {len(function_dicts)} functions")
                return function_dicts
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load functions: {e}")
            return []

    @monitor_performance("load_mcp_tools")
    @profile_function("load_mcp_tools")
    async def _load_mcp_tools_async(self) -> Dict[str, Any]:
        """Cargar herramientas MCP disponibles con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                mcp_service = temp_factory.get_mcp_integration_service()
                
                # Obtener herramientas MCP disponibles
                mcp_tools = mcp_service.get_available_tools()
                
                logger.info(f"[OrchestratorService] MCP tools loaded with separate session: {len(mcp_tools)} tools")
                return mcp_tools
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load MCP tools: {e}")
            return {}

    # ===================================================
    #  MÉTODOS DE CONTROL DE TOKENS MEJORADOS
    # ===================================================
    def _check_token_bucket(self) -> bool:
        """Verifica si hay tokens disponibles en el bucket"""
        current_time = time.time()
        
        # Resetear bucket si ha pasado la ventana de tiempo
        if current_time - self._token_bucket["window_start"] > self._token_bucket["window_size"]:
            self._token_bucket["tokens_used"] = 0
            self._token_bucket["window_start"] = current_time
            logger.debug("[OrchestratorService] 🔒 Token bucket reseteado")
        
        # Verificar si hay tokens disponibles
        available_tokens = self._token_bucket["max_tokens_per_window"] - self._token_bucket["tokens_used"]
        
        if available_tokens < self.MAX_INPUT_TOKENS:
            logger.warning(f"[OrchestratorService] 🔒 Token bucket limitado: {available_tokens} disponibles, {self.MAX_INPUT_TOKENS} necesarios")
            return False
        
        return True

    def _update_token_bucket(self, tokens_used: int):
        """Actualiza el token bucket con los tokens utilizados"""
        self._token_bucket["tokens_used"] += tokens_used
        logger.debug(f"[OrchestratorService] 🔒 Token bucket actualizado: {self._token_bucket['tokens_used']} tokens usados")

    def _apply_intelligent_context_trimming(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica trimming inteligente basado en presupuesto de tokens"""
        trimmed_context = context.copy()
        
        # 1. Limitar historial
        if "history" in trimmed_context and len(trimmed_context["history"]) > self.MAX_HISTORY_TURNS:
            trimmed_context["history"] = trimmed_context["history"][-self.MAX_HISTORY_TURNS:]
            logger.info(f"[OrchestratorService] 🔒 Historial recortado: {len(context['history'])} → {len(trimmed_context['history'])} turnos")
        
        # 2. Limitar schema a caracteres máximos
        if "compact_schemas" in trimmed_context:
            for db_id, schema_data in trimmed_context["compact_schemas"].items():
                if isinstance(schema_data, dict) and "compact" in schema_data:
                    schema_text = schema_data["compact"]
                    if len(schema_text) > self.MAX_SCHEMA_CHARS:
                        trimmed_context["compact_schemas"][db_id]["compact"] = (
                            schema_text[:self.MAX_SCHEMA_CHARS] + "\n\n... (truncado por límite de tokens)"
                        )
                        logger.info(f"[OrchestratorService] 🔒 Schema para DB {db_id} recortado: {len(schema_text)} → {self.MAX_SCHEMA_CHARS} caracteres")
        
        # 3. Limitar descriptores de apps
        if "app_descriptors_compact" in trimmed_context and trimmed_context["app_descriptors_compact"]:
            app_desc = trimmed_context["app_descriptors_compact"]
            if len(app_desc) > self.MAX_APP_DESCRIPTOR_CHARS:
                trimmed_context["app_descriptors_compact"] = (
                    app_desc[:self.MAX_APP_DESCRIPTOR_CHARS] + "\n\n... (descriptores truncados por límite de tokens)"
                )
                logger.info(f"[OrchestratorService] 🔒 Descriptores de apps recortados: {len(app_desc)} → {self.MAX_APP_DESCRIPTOR_CHARS} caracteres")
        
        # 4. Limitar funciones
        if "functions" in trimmed_context and len(trimmed_context["functions"]) > self.TOP_K_APPS:
            trimmed_context["functions"] = trimmed_context["functions"][:self.TOP_K_APPS]
            logger.info(f"[OrchestratorService] 🔒 Funciones limitadas: {len(context['functions'])} → {len(trimmed_context['functions'])}")
        
        # 5. Limitar herramientas MCP
        if "mcp_tools" in trimmed_context and trimmed_context["mcp_tools"]:
            mcp_tools = trimmed_context["mcp_tools"]
            if isinstance(mcp_tools, dict) and "tools" in mcp_tools:
                if len(mcp_tools["tools"]) > 3:
                    trimmed_context["mcp_tools"]["tools"] = mcp_tools["tools"][:3]
                    logger.info(f"[OrchestratorService] 🔒 MCP tools limitadas: {len(mcp_tools['tools'])} → 3")
        
        return trimmed_context

    def _should_force_plan(self, db_ids: Optional[List[UUID]], user_message: str, execution_results: Dict[str, Any]) -> bool:
        """Determina si se debe forzar la generación de un plan basado en la intención del usuario"""
        # 1. Si hay bases de datos especificadas, forzar plan
        if db_ids:
            logger.info("[OrchestratorService] 🔒 Forzando plan por presencia de bases de datos")
            return True
        
        # 2. Si el mensaje contiene palabras clave de consulta de base de datos
        db_keywords = [
            "consulta", "query", "select", "buscar", "encontrar", "mostrar", "listar",
            "cuántos", "cuántas", "dónde", "cuándo", "datos", "información",
            "tabla", "registro", "fila", "columna", "base de datos", "database"
        ]
        
        user_message_lower = user_message.lower()
        has_db_intention = any(keyword in user_message_lower for keyword in db_keywords)
        
        if has_db_intention:
            logger.info("[OrchestratorService] 🔒 Forzando plan por palabras clave de consulta de base de datos")
            return True
        
        # 3. Si ya hay un plan generado, no forzar
        if execution_results.get("plan"):
            return False
        
        # 4. Por defecto, no forzar (dejar que el LLM decida)
        return False

    def _generate_minimal_plan_for_db_intention(self, user_message: str, db_ids: List[UUID]) -> Dict[str, Any]:
        """Genera un plan mínimo cuando se detecta intención de base de datos"""
        logger.info("[OrchestratorService] 🔒 Generando plan mínimo para intención de base de datos")
        
        # Crear un plan básico con una acción de consulta y steps
        plan = {
            "actions": [
                {
                    "type": "db_query",
                    "question": user_message,
                    "store_as": "query_result"
                }
            ],
            "steps": [
                {
                    "type": "step",
                    "message": "Consultando base de datos para obtener la información solicitada",
                    "status": "in_progress"
                },
                {
                    "type": "step", 
                    "message": "Resultados obtenidos: {query_result}",
                    "status": "pending",
                    "depends_on": "query_result",
                    "template": "Resultados obtenidos: {query_result}"
                }
            ]
        }
        
        logger.info(f"[OrchestratorService] ✅ Plan mínimo generado con {len(plan['actions'])} acción(es) y {len(plan['steps'])} steps")
        return plan

    async def _handle_message_with_minimal_context(
        self,
        chat_id: UUID,
        db_ids: Optional[List[UUID]],
        app_ids: Optional[List[UUID]],
        explorer: bool,
        agent_id: Optional[UUID],
        message: ChatMessage,
    ) -> Dict[str, Any]:
        """Maneja el mensaje con contexto mínimo cuando el token bucket está limitado"""
        logger.info("[OrchestratorService] 🔒 Usando contexto mínimo por limitación de token bucket")
        
        try:
            # Cargar solo contexto esencial
            minimal_context = await self._load_minimal_context(chat_id, message, db_ids, app_ids, explorer)
            
            # Ejecutar con contexto mínimo
            graph_runner = self._select_graph_runner(explorer)
            execution_results = await graph_runner.run(minimal_context)
            
            # Normalizar resultados
            execution_results = self._normalize_graph_output(execution_results)
            
            # Extraer respuesta
            assistant_response = self._extract_assistant_response(execution_results)
            
            # Guardar mensaje del asistente
            await self._save_assistant_message_async(
                chat_id=chat_id,
                content=assistant_response,
                token_count=None,
                executed_strategy_id=None,
            )
            
            return {
                "assistant_response": assistant_response,
                "execution_results": execution_results,
                "steps": execution_results.get("steps", []),
            }
            
        except Exception as e:
            logger.exception("[OrchestratorService] ❌ Error con contexto mínimo: %s", e)
            return {
                "assistant_response": "Estoy reduciendo contexto para cumplir límites. Por favor, reformula tu consulta de manera más específica.",
                "error": str(e)
            }

    async def _load_minimal_context(
        self, 
        chat_id: UUID, 
        message: ChatMessage, 
        db_ids: Optional[List[UUID]], 
        app_ids: Optional[List[UUID]], 
        explorer: bool
    ) -> Dict[str, Any]:
        """Carga contexto mínimo para evitar exceder límites de tokens"""
        logger.info("[OrchestratorService] 🔒 Cargando contexto mínimo")
        
        # Solo cargar historial mínimo
        history = await self._load_history_async(chat_id)
        if len(history) > 3:  # Solo últimos 3 turnos
            history = history[-3:]
        
        # Cargar solo esquemas básicos si hay DBs
        compact_schemas = {}
        if db_ids:
            for db_id in db_ids[:1]:  # Solo primera DB
                try:
                    cache_service = self.factory.get_detailed_schema_cache_service()
                    cache_entry = cache_service.get_schema_cache(self.user.id, db_id)
                    if cache_entry and cache_entry.compact:
                        # Truncar schema a caracteres mínimos
                        schema_text = cache_entry.compact[:1500]  # Muy limitado
                        compact_schemas[db_id] = {"compact": schema_text}
                except Exception as e:
                    logger.warning(f"[OrchestratorService] ⚠️ Error cargando schema mínimo para DB {db_id}: {e}")
        
        # Cargar solo funciones básicas
        functions = []
        if app_ids:
            try:
                function_service = self.factory.get_function_service()
                for app_id in app_ids[:1]:  # Solo primera app
                    app_functions = function_service.get_by_app(app_id)
                    if app_functions:
                        functions.extend(app_functions[:2])  # Solo 2 funciones
            except Exception as e:
                logger.warning(f"[OrchestratorService] ⚠️ Error cargando funciones mínimas: {e}")
        
        return {
            "history": history,
            "compact_schemas": compact_schemas,
            "functions": functions,
            "explorer": explorer,
            "minimal_context": True  # Flag para indicar contexto mínimo
        }

    def _estimate_tokens_for_context(self, context: Dict[str, Any]) -> int:
        """Estima el número de tokens para un contexto dado"""
        try:
            total_chars = 0
            
            # 1. Historial
            if "history" in context:
                for msg in context["history"]:
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        total_chars += len(content)
                    elif hasattr(msg, 'content'):
                        total_chars += len(msg.content or "")
            
            # 2. Esquemas de base de datos
            if "compact_schemas" in context:
                for db_id, schema_data in context["compact_schemas"].items():
                    if isinstance(schema_data, dict) and "compact" in schema_data:
                        total_chars += len(schema_data["compact"])
            
            # 3. Descriptores de apps
            if "app_descriptors_compact" in context and context["app_descriptors_compact"]:
                total_chars += len(context["app_descriptors_compact"])
            
            # 4. Funciones
            if "functions" in context:
                for func in context["functions"]:
                    if hasattr(func, 'description') and func.description:
                        total_chars += len(func.description)
                    if hasattr(func, 'name'):
                        total_chars += len(func.name)
            
            # 5. Herramientas MCP
            if "mcp_tools" in context and context["mcp_tools"]:
                mcp_tools = context["mcp_tools"]
                if isinstance(mcp_tools, dict) and "tools" in mcp_tools:
                    for tool in mcp_tools["tools"]:
                        if isinstance(tool, dict):
                            total_chars += len(tool.get("name", ""))
                            total_chars += len(tool.get("description", ""))
            
            # Estimación aproximada: 1 token ≈ 4 caracteres
            estimated_tokens = total_chars // 4
            logger.debug(f"[OrchestratorService] 🔍 Tokens estimados para contexto: {estimated_tokens}")
            return estimated_tokens
            
        except Exception as e:
            logger.warning(f"[OrchestratorService] ⚠️ Error estimando tokens del contexto: {e}")
            return 0

    # ===================================================
    #  HELPERS (mantienen la funcionalidad original)
    # ===================================================
    def _select_graph_runner(self, explorer: bool):
        from app.services.graphs.exploration_graph import ExplorationGraph
        from app.services.graphs.guided_graph import GuidedGraph
        GraphClass = ExplorationGraph if explorer else GuidedGraph
        logger.info("[OrchestratorService] Using graph: %s", GraphClass.__name__)
        return GraphClass(self.factory)

    def _normalize_graph_output(self, output: Any) -> Dict[str, Any]:
        """
        Normaliza la salida del grafo para que siempre sea un diccionario.
        Esto asegura que las claves de acceso sean consistentes.
        """
        if isinstance(output, dict):
            # 🔧 FIX: Normalizar también el message anidado si existe
            normalized = output.copy()
            if "message" in normalized and hasattr(normalized["message"], "model_dump"):
                # Si message es un ChatMessage, convertirlo a dict también
                normalized["message"] = normalized["message"].model_dump()
            return normalized
        elif hasattr(output, 'model_dump'):  # Pydantic models como ChatMessage
            # Convertir Pydantic model a dict
            normalized = output.model_dump()
            # Si es un ChatMessage, extraer el contenido principal
            if hasattr(output, 'content') and hasattr(output, 'role'):
                if output.role == 'assistant':
                    normalized['assistant_response'] = output.content
                else:
                    normalized['message'] = output.content
            return normalized
        elif hasattr(output, 'content'):  # Objetos con atributo content
            return {
                'assistant_response': str(output.content),
                'result': output
            }
        elif isinstance(output, list):
            return {"results": output}
        elif output is None:
            return {}
        else:
            # Para cualquier otro tipo, convertirlo a string y guardarlo
            return {
                'assistant_response': str(output),
                'result': output
            }

    def _calculate_content_length(self, data: Dict[str, Any]) -> int:
        """Calcula la longitud del contenido de la respuesta del asistente."""
        if "assistant_response" in data:
            response_content = data["assistant_response"]
            if isinstance(response_content, dict) and "content" in response_content:
                return len(str(response_content["content"]))
            return len(str(response_content))
        elif "response" in data:
            return len(str(data["response"]))
        elif "content" in data:
            return len(str(data["content"]))
        elif "message" in data:
            return len(str(data["message"]))
        return 0

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
        logger.info(f"[OrchestratorService] 🔍 Extrayendo respuesta del resultado (keys: {list(execution_results.keys())}")
        logger.info(f"[OrchestratorService] 🔍 Contenido completo de execution_results: {execution_results}")
        
        # 🔍 DEBUG: Verificar si hay query_result en variables
        if "variables" in execution_results and execution_results["variables"]:
            variables = execution_results["variables"]
            if "query_result" in variables:
                logger.info(f"[OrchestratorService] 🔍 QUERY_RESULT encontrado en variables: {variables['query_result']}")
            else:
                logger.info(f"[OrchestratorService] 🔍 NO hay query_result en variables")
        else:
            logger.info(f"[OrchestratorService] 🔍 NO hay variables en execution_results")
        
        # 🔧 FIX: Priorizar assistant_response como primera opción
        if "assistant_response" in execution_results and execution_results["assistant_response"]:
            response_value = execution_results["assistant_response"]
            logger.info(f"[OrchestratorService] 🔍 Encontrado assistant_response: {response_value}")
            if isinstance(response_value, dict) and 'content' in response_value:
                actual_response = response_value['content']
                logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en 'assistant_response.content' (longitud: {len(str(actual_response))} chars)")
                logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO assistant_response.content")
                return str(actual_response)
            else:
                response_length = len(str(response_value))
                logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en 'assistant_response' (longitud: {response_length} chars)")
                logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO assistant_response directo")
                return str(response_value)
        else:
            logger.info(f"[OrchestratorService] 🔍 NO hay assistant_response o está vacío")
        
        # 🔧 FIX: Buscar en objeto response estructurado si existe
        if "response" in execution_results and execution_results["response"]:
            response_obj = execution_results["response"]
            logger.info(f"[OrchestratorService] 🔍 Encontrado response: {response_obj}")
            if isinstance(response_obj, dict):
                # Buscar content, message, o text en el objeto response
                for content_key in ["content", "message", "text", "answer"]:
                    if content_key in response_obj and response_obj[content_key]:
                        content_value = response_obj[content_key]
                        response_length = len(str(content_value))
                        logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en 'response.{content_key}' (longitud: {response_length} chars)")
                        logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO response.{content_key}")
                        return str(content_value)
                # Si no hay content específico, usar todo el objeto response
                response_length = len(str(response_obj))
                logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en 'response' completo (longitud: {response_length} chars)")
                logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO response completo")
                return str(response_obj)
            else:
                # Si response no es dict, usarlo directamente
                response_length = len(str(response_obj))
                logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en 'response' directo (longitud: {response_length} chars)")
                logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO response directo")
                return str(response_obj)
        else:
            logger.info(f"[OrchestratorService] 🔍 NO hay response o está vacío")
        
        # 🔧 FIX: Buscar en variables como fallback útil
        if "variables" in execution_results and execution_results["variables"]:
            variables = execution_results["variables"]
            logger.info(f"[OrchestratorService] 🔍 Encontradas variables: {variables}")
            # Buscar variables que puedan contener respuestas útiles
            for var_name, var_value in variables.items():
                if var_name in ["query_result", "result", "answer", "response", "content"] and var_value:
                    logger.info(f"[OrchestratorService] 🔍 Procesando variable útil: {var_name} = {var_value}")
                    if isinstance(var_value, str) and len(var_value.strip()) > 10:  # Solo strings con contenido
                        logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en variables['{var_name}'] (longitud: {len(var_value)} chars)")
                        logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO variable string")
                        return str(var_value)
                    elif isinstance(var_value, (dict, list)) and var_value:
                        # Si es un objeto complejo, convertirlo a string legible
                        try:
                            if isinstance(var_value, dict):
                                # Para dicts, buscar campos útiles
                                for key in ["content", "message", "text", "result"]:
                                    if key in var_value and var_value[key]:
                                        content = var_value[key]
                                        if isinstance(content, str) and len(content.strip()) > 10:
                                            logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en variables['{var_name}'].{key} (longitud: {len(content)} chars)")
                                            logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO variable.{key}")
                                            return str(content)
                                # 🔧 FIX: Si es query_result, formatear para que sea más corto
                                if var_name == "query_result" and "result" in var_value:
                                    result_data = var_value["result"]
                                    logger.info(f"[OrchestratorService] 🔍 PROCESANDO query_result: {result_data} (tipo: {type(result_data)})")
                                    
                                    if isinstance(result_data, list) and len(result_data) > 0:
                                        # Solo mostrar los primeros 3 valores para que sea más corto
                                        limited_result = result_data[:3]
                                        formatted_result = f"Resultados obtenidos (mostrando primeros 3): {limited_result}"
                                        if len(result_data) > 3:
                                            formatted_result += f" ... y {len(result_data) - 3} más"
                                        logger.info(f"[OrchestratorService] ✅ Formateando query_result para mostrar solo primeros 3 valores")
                                        logger.info(f"[OrchestratorService] ✅ RESULTADO FORMATEADO: '{formatted_result}'")
                                        logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO RESULTADO FORMATEADO")
                                        return formatted_result
                                    else:
                                        # Si no es lista, usar el resultado completo pero limitado
                                        result_str = str(result_data)
                                        if len(result_str) > 200:  # Limitar longitud si es muy largo
                                            result_str = result_str[:200] + "..."
                                        logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en variables['{var_name}'] formateada (longitud: {len(result_str)} chars)")
                                        final_result = f"Resultados obtenidos: {result_str}"
                                        logger.info(f"[OrchestratorService] ✅ RESULTADO FORMATEADO: '{final_result}'")
                                        logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO RESULTADO FORMATEADO")
                                        return final_result
                                # Si no hay campos útiles, usar todo el dict
                                response_str = str(var_value)
                                if len(response_str) > 20:  # Solo si tiene contenido sustancial
                                    logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en variables['{var_name}'] completo (longitud: {len(response_str)} chars)")
                                    logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO variable completo")
                                    return str(response_str)
                            else:
                                # Para lists, usar el primer elemento si es string
                                if var_value and isinstance(var_value[0], str) and len(var_value[0].strip()) > 10:
                                    logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en variables['{var_name}'][0] (longitud: {len(var_value[0])} chars)")
                                    logger.info(f"[OrchestratorService] ✅ DEVOLVIENDO variable[0]")
                                    return str(var_value[0])
                        except Exception as e:
                            logger.debug(f"[OrchestratorService] Error procesando variable {var_name}: {e}")
                            continue
        else:
            logger.info(f"[OrchestratorService] 🔍 NO hay variables o están vacías")
        
        # 🔧 FIX: Si hay steps, generar respuesta basada en steps pero SIN usar message del usuario
        if execution_results.get("steps"):
            steps = execution_results.get("steps", [])
            logger.info(f"[OrchestratorService] 📋 Encontrados {len(steps)} steps en el plan")
            logger.info(f"[OrchestratorService] 📋 Contenido de steps: {steps}")
            
            # Buscar en steps por contenido útil, evitando mensajes del usuario
            for i, step in enumerate(steps):
                logger.info(f"[OrchestratorService] 🔍 Procesando step {i}: {step}")
                if isinstance(step, dict):
                    # Buscar en campos del step que NO sean message (que puede ser del usuario)
                    for step_key in ["content", "result", "output", "data"]:
                        if step_key in step and step[step_key]:
                            step_content = step[step_key]
                            logger.info(f"[OrchestratorService] 🔍 Encontrado contenido en step[{i}].{step_key}: {step_content}")
                            if isinstance(step_content, str) and len(step_content.strip()) > 10:
                                # Verificar que no sea el mensaje del usuario
                                if not any(user_indicator in step_content.lower() for user_indicator in ["tu pregunta", "responder a", "para responder"]):
                                    logger.info(f"[OrchestratorService] ✅ Encontrada respuesta en step[{i}]['{step_key}'] (longitud: {len(step_content)} chars)")
                                    return str(step_content)
                                else:
                                    logger.info(f"[OrchestratorService] ⚠️ Contenido del step parece ser del usuario, saltando")
            
            # Si no hay contenido útil en steps, generar mensaje genérico
            logger.info(f"[OrchestratorService] 📋 Steps encontrados pero sin contenido útil, generando mensaje genérico")
            return "Consultando base de datos..."
        else:
            logger.info(f"[OrchestratorService] 🔍 NO hay steps en execution_results")
        
        # 🔧 FIX: Buscar en otros campos posibles (excluyendo message que es del usuario)
        for key in ["content", "output", "result", "answer"]:
            if key in execution_results and execution_results[key]:
                response_value = execution_results[key]
                logger.info(f"[OrchestratorService] 🔍 Encontrado campo '{key}': {response_value}")
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
        logger.warning(f"[OrchestratorService] ⚠️ Contenido completo de execution_results: {execution_results}")
        logger.warning("[OrchestratorService] ⚠️ DEVOLVIENDO MENSAJE POR DEFECTO")
        return "🤖 No se pudo generar una respuesta"

    def _safe_sqlalchemy_to_dict(self, obj: Any) -> Dict[str, Any]:
        """
        Convierte objetos SQLAlchemy a diccionarios de forma segura.
        Maneja casos donde el objeto puede no tener ciertos atributos.
        """
        try:
            if hasattr(obj, '__dict__'):
                # Objeto SQLAlchemy - extraer atributos
                result = {}
                for key, value in obj.__dict__.items():
                    # Ignorar atributos internos de SQLAlchemy
                    if not key.startswith('_'):
                        try:
                            # Convertir datetime a ISO string si es posible
                            if hasattr(value, 'isoformat'):
                                result[key] = value.isoformat()
                            else:
                                result[key] = value
                        except Exception:
                            # Si falla la conversión, usar string
                            result[key] = str(value)
                return result
            elif hasattr(obj, 'model_dump'):
                # Objeto Pydantic
                return obj.model_dump()
            elif isinstance(obj, dict):
                # Ya es un diccionario
                return obj
            else:
                # Otro tipo - convertir a string
                return {'value': str(obj)}
        except Exception as e:
            logger.warning(f"[OrchestratorService] Error convirtiendo objeto a diccionario: {e}")
            return {'error': f'Error converting object: {str(e)}'}
