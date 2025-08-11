# app/services/orchestrator_service.py
"""
OrchestratorService Refactorizado
─────────────────────────────────
Servicio principal que coordina los módulos especializados:
1. TokenBudgetManager: Control de presupuesto de tokens
2. ContextLoader: Carga de contexto paralelo
3. ResponseProcessor: Procesamiento de respuestas
4. ContextOptimizer: Optimización de contexto
5. GraphRunner: Ejecución de grafos
6. MessageHandler: Manejo de mensajes
7. AdvancedTelemetryService: Telemetría y KPIs (FASE 13)
"""
from __future__ import annotations

import logging
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
import re, difflib

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.schemas.plan_schema import PlanModel
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context, memory_profiler
from app.core.database import SessionLocal
from app.common.ws_emitter import WebSocketEmitter
from app.common.enums import Mode
from app.core.config import settings

# Importar módulos especializados
from app.services.orchestrator import (
    TokenBudgetManager,
    ContextLoader,
    ResponseProcessor,
    ContextOptimizer,
    GraphRunner,
    MessageHandler,
    IterativeRAGHandler,
    SchemaValidator,
    ResponseFormatter,
    SchemaManager,
    ChatHistoryManager,
    AppFunctionManager,
    DecisionManager
)

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
        
        # 🔒 CONTROL DE TOKENS - Inicializar módulos especializados
        self.token_budget = TokenBudgetManager()
        self.context_loader = ContextLoader(factory)
        self.response_processor = ResponseProcessor()
        self.context_optimizer = ContextOptimizer()
        self.graph_runner = GraphRunner(factory)
        self.message_handler = MessageHandler(factory)
        self.iterative_rag_handler = IterativeRAGHandler(factory)
        self.schema_validator = SchemaValidator()
        self.response_formatter = ResponseFormatter()
        
        # 🆕 NUEVOS MÓDULOS ESPECIALIZADOS
        self.schema_manager = SchemaManager(factory)
        self.chat_history_manager = ChatHistoryManager(factory)
        self.app_function_manager = AppFunctionManager(factory)
        # self.agent_manager = AgentManager(factory)  # Comentado temporalmente para tests
        # self.plan_strategy_manager = PlanStrategyManager(factory)  # Comentado temporalmente para tests
        self.decision_manager = DecisionManager()
        
        # 🆕 WEBSOCKET EMITTER para eventos en tiempo real
        self.ws_emitter: Optional[WebSocketEmitter] = factory.get_ws_emitter()
        
        # 🎯 FASE 13: SERVICIO DE TELEMETRÍA AVANZADO
        self.telemetry_service = factory.get_advanced_telemetry_service()
        self.current_telemetry_context = None
        
        logger.info(f"[OrchestratorService] Initialized for user_id={self.user_id}")
        logger.info("[OrchestratorService] ✅ Módulos especializados cargados")
        if self.ws_emitter:
            logger.info("[OrchestratorService] ✅ WebSocket emitter habilitado")
        else:
            logger.info("[OrchestratorService] ℹ️ WebSocket emitter no disponible (modo HTTP)")
        if self.telemetry_service:
            logger.info("[OrchestratorService] ✅ Servicio de telemetría habilitado")
        else:
            logger.info("[OrchestratorService] ℹ️ Servicio de telemetría no disponible")

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

        # 🎯 FASE 13: INICIAR TRACKING DE TELEMETRÍA
        start_time = time.time()
        conversation_id = str(uuid4())
        
        if self.telemetry_service:
            try:
                self.current_telemetry_context = self.telemetry_service.start_conversation_tracking(
                    conversation_id=conversation_id,
                    user_id=self.user_id,
                    chat_id=chat_id,
                    mode="explorer" if explorer else "guided",
                    user_preferences={
                        "response_format": "detailed",
                        "detail_level": "normal",
                        "risk_tolerance": "medium",
                        "language": "es"
                    }
                )
                logger.info(f"[OrchestratorService] 🎯 FASE 13: Tracking de telemetría iniciado para conversación {conversation_id}")
            except Exception as e:
                logger.warning(f"[OrchestratorService] ⚠️ Error iniciando tracking de telemetría: {e}")
                self.current_telemetry_context = None

        # 🚀 FASE 1: Emisión básica de progreso en tiempo real
        await self.emit_status_typing(True)  # Usuario está escribiendo
        await self.emit_status_progress(1, 1, "Recibiendo mensaje", 10.0)

        # 📊 Profiling de memoria
        memory_profiler.take_snapshot("orchestrator_start")

        # 🚀 FASE 7: Fast Schema Path - Intentar respuesta rápida sin LLM
        if settings.UX_FAST_PATH and db_ids and self._is_schema_lookup_intent(message.content):
            try:
                logger.info("[OrchestratorService] 🚀 Intentando Fast Schema Path...")
                await self.emit_status_progress(2, 5, "Buscando en índices léxicos...", 20.0)
                
                # Obtener SchemaExplorerService
                schema_explorer = self.factory.get_schema_explorer_service()
                
                # Intentar fast lookup
                fast_result, confidence, response_type = schema_explorer.fast_lookup(message.content, db_ids)
                
                if response_type == "fast" and fast_result:
                    logger.info(f"[OrchestratorService] ✅ Fast Schema Path exitoso (confianza: {confidence:.2f})")
                    
                    # 🎯 FASE 13: TRACKING DE PASO EXITOSO
                    if self.current_telemetry_context:
                        try:
                            self.telemetry_service.track_step_execution(
                                conversation_id=conversation_id,
                                step_number=1,
                                step_type="fast_schema_lookup",
                                duration_ms=(time.time() - start_time) * 1000,
                                success=True,
                                tokens_used=0,
                                cache_operations=1,
                                database_queries=0,
                                llm_calls=0,
                                metadata={
                                    "confidence": confidence,
                                    "tables_found": len(fast_result.get('tables', [])),
                                    "response_type": response_type
                                }
                            )
                        except Exception as e:
                            logger.warning(f"[OrchestratorService] ⚠️ Error tracking paso de telemetría: {e}")
                    
                    # Emitir resultado final directamente
                    await self.emit_result_final(
                        summary=fast_result.get('message', 'Consulta de esquema resuelta rápidamente'),
                        data=fast_result,
                        next_actions=[
                            "Pregunta algo más específico sobre las tablas encontradas",
                            "Explora los datos de una tabla en particular",
                            "Verifica la estructura de las columnas"
                        ],
                        usage_stats={
                            'response_time_ms': fast_result.get('response_time_ms', 0),
                            'confidence': confidence,
                            'tables_found': len(fast_result.get('tables', [])),
                            'mode': 'fast_schema_path'
                        }
                    )
                    
                    # Guardar mensaje del usuario
                    await self._store_user_message_async(chat_id, message)
                    
                    # Guardar respuesta del asistente
                    await self._save_assistant_message_async(
                        chat_id, 
                        fast_result.get('message', 'Consulta resuelta'),
                        None,  # No contamos tokens en fast path
                        None
                    )
                    
                    # 🎯 FASE 13: FINALIZAR TRACKING Y EMITIR SNAPSHOT
                    if self.current_telemetry_context:
                        try:
                            # Finalizar tracking de conversación
                            metrics = self.telemetry_service.end_conversation_tracking(
                                conversation_id=conversation_id
                            )
                            
                            # Emitir snapshot de telemetría
                            await self.emit_telemetry_snapshot(
                                tokens_in=0,  # Fast path no usa LLM
                                tokens_out=0,
                                latency_ms=(time.time() - start_time) * 1000,
                                cache_hit_ratio=1.0,  # Fast path es cache hit
                                steps_executed=1,
                                confirmations_required=0,
                                mode=Mode.EXPLORER if explorer else Mode.GUIDED
                            )
                            
                            logger.info(f"[OrchestratorService] 🎯 FASE 13: Telemetría finalizada y snapshot emitido para conversación {conversation_id}")
                            
                        except Exception as e:
                            logger.warning(f"[OrchestratorService] ⚠️ Error finalizando telemetría: {e}")
                    
                    return {
                        "assistant_response": fast_result.get('message', 'Consulta resuelta'),
                        "fast_path_used": True,
                        "confidence": confidence,
                        "response_type": "fast_schema_lookup"
                    }
                
                elif response_type == "ambiguous" and fast_result:
                    logger.info(f"[OrchestratorService] 🤔 Fast Schema Path ambigua (confianza: {confidence:.2f})")
                    
                    # Emitir resultado parcial para desambiguación
                    await self.emit_result_partial(
                        step=1,
                        data=fast_result,
                        preview=f"Encontré {len(fast_result.get('tables', []))} posibles coincidencias. ¿Podrías ser más específico?"
                    )
                    
                    # Continuar con el flujo normal para desambiguación
                    await self.emit_status_progress(3, 5, "Procesando consulta ambigua...", 40.0)
                
                else:
                    logger.info(f"[OrchestratorService] 📉 Fast Schema Path falló (confianza: {confidence:.2f}) - usando LLM")
                    await self.emit_status_progress(3, 5, "Usando análisis inteligente...", 40.0)
            except Exception as e:
                logger.warning(f"[OrchestratorService] ⚠️ Error en Fast Schema Path: {e} - continuando con LLM")
                await self.emit_status_progress(3, 5, "Error en búsqueda rápida, usando análisis inteligente...", 40.0)

        # 🔒 CONTROL DE TOKENS: Aplicar presupuesto antes de cargar contexto
        db_ids = self.token_budget.apply_token_budget_to_db_ids(db_ids)
        app_ids = self.token_budget.apply_token_budget_to_app_ids(app_ids)
        
        # 🔒 CONTROL DE TOKENS: Verificar token bucket antes de proceder
        if not self.token_budget.check_token_bucket():
            logger.warning("[OrchestratorService] 🔒 Token bucket limitado - usando contexto mínimo")
            return await self._handle_message_with_minimal_context(
                chat_id, db_ids, app_ids, explorer, agent_id, message
            )
        
        # ⚡ OPTIMIZACIÓN: Ejecutar operaciones en paralelo usando ContextLoader
        context_tasks = await self.context_loader.load_context_parallel(chat_id, message, db_ids, app_ids, explorer)
        
        # Actualizar el contexto con el parámetro explorer
        context_tasks["explorer"] = explorer

        # 🔧 FIX: Validar compact_schemas antes de ejecutar el grafo
        if db_ids and not self._validate_compact_schemas(context_tasks.get("compact_schemas", {}), db_ids):
            logger.error("[OrchestratorService] ❌ Sin schemas válidos para DBs solicitadas - abortando ejecución")
            return {
                "assistant_response": "❌ Error: No se pudo obtener información de las bases de datos solicitadas. Por favor, verifica la conexión.",
                "error": "missing_valid_schemas"
            }

        # 🎯 FASE 10: TokenBudget UX - Estimación y budget hints
        estimated_tokens = self.token_budget.estimate_tokens_for_context(context_tasks)
        budget_hint = self.token_budget.budget_hint(estimated_tokens)
        
        # Emitir budget hint como notice.info
        if budget_hint["current_usage"]["status"] == "warning":
            await self.emit_notice_info(
                message=f"⚠️ Presupuesto de tokens alto ({budget_hint['current_usage']['budget_usage_percent']:.1f}%). {budget_hint['suggestions'][0]}",
                level="warning",
                actions=[
                    {"label": "Modo Rápido", "action": "switch_to_fast_mode"},
                    {"label": "Modo Equilibrado", "action": "switch_to_balanced_mode"},
                    {"label": "Continuar", "action": "continue_current_mode"}
                ]
            )
        else:
            await self.emit_notice_info(
                message=f"📊 Presupuesto de tokens: {budget_hint['current_usage']['budget_usage_percent']:.1f}% - Modo recomendado: {budget_hint['recommended_mode']}",
                level="info",
                actions=[
                    {"label": f"Cambiar a {budget_hint['recommended_mode'].title()}", "action": f"switch_to_{budget_hint['recommended_mode']}_mode"},
                    {"label": "Ver opciones", "action": "show_mode_options"},
                    {"label": "Continuar", "action": "continue_current_mode"}
                ]
            )

        # 🔒 CONTROL DE TOKENS: Aplicar trimming dinámico al contexto usando TokenBudgetManager
        trimmed_context = self.token_budget.apply_intelligent_context_trimming(context_tasks)
        
        # 🎯 FASE 10: Emitir avisos de trimming cuando se recorte el contexto
        if "_trimming_info" in trimmed_context:
            trimming_info = trimmed_context["_trimming_info"]
            trimming_messages = []
            
            if trimming_info["chat_history_trimmed"]:
                trimming_messages.append("historial de chat")
            if trimming_info["db_schemas_trimmed"]:
                trimming_messages.append("esquemas de base de datos")
            if trimming_info["app_descriptors_trimmed"]:
                trimming_messages.append("descriptores de aplicaciones")
            if trimming_info["functions_trimmed"]:
                trimming_messages.append("descripciones de funciones")
            
            if trimming_messages:
                tokens_saved = trimming_info["original_tokens"] - trimming_info["trimmed_tokens"]
                await self.emit_notice_info(
                    message=f"🔒 Contexto optimizado: Se recortó {', '.join(trimming_messages)} para ahorrar ~{tokens_saved} tokens",
                    level="info",
                    actions=[
                        {"label": "Ver detalles", "action": "show_trimming_details"},
                        {"label": "Ajustar modo", "action": "adjust_mode"},
                        {"label": "Continuar", "action": "continue_optimized"}
                    ]
                )
                
                logger.info(f"[OrchestratorService] 🎯 FASE 10: Contexto optimizado - {tokens_saved} tokens ahorrados")
        
        # 🎯 Ejecutar el grafo usando GraphRunner
        try:
            # 🚀 FASE 1: Emisión de progreso antes de ejecutar el grafo
            await self.emit_status_progress(2, 3, "Seleccionando grafo de ejecución...", 30.0)
            
            execution_results = await self.graph_runner.run_graph(explorer, chat_id, message.content, trimmed_context)
            logger.info("[OrchestratorService] Graph execution completed")
            
            # 🚀 FASE 1: Emisión de progreso después de ejecutar el grafo
            await self.emit_status_progress(3, 3, "Grafo ejecutado, procesando resultados...", 60.0)
            
            # 🔄 NORMALIZAR SIEMPRE la salida del grafo a dict antes de tocarla
            execution_results = self.graph_runner.normalize_graph_output(execution_results)
            logger.info(f"[OrchestratorService] ✅ Salida del grafo normalizada a dict con claves: {list(execution_results.keys())}")
            
            # ─────────────────────────────────────────────────────────────
            # SHORT-CIRCUIT: Si la intención es de ESQUEMA, responder desde caché
            # ─────────────────────────────────────────────────────────────
            if self._is_schema_intent(execution_results, message.content):
                schema_response = self._generate_schema_response(trimmed_context, db_ids, message.content)
                execution_results["assistant_response"] = schema_response
                if "plan" in execution_results:
                    execution_results["plan"] = None
                logger.info("[OrchestratorService] ✅ Short-circuit de esquema aplicado: respuesta directa desde caché")

            # 🔒 CONTROL DE TOKENS: Forzar plan cuando hay intención de base de datos (salvo esquema)
            if self._should_force_plan(db_ids, message.content, execution_results):
                logger.info("[OrchestratorService] 🔒 Forzando generación de plan por intención de base de datos")
                if not execution_results.get("plan"):
                    # Generar plan mínimo si no se generó uno
                    execution_results["plan"] = self._generate_minimal_plan_for_db_intention(message.content, db_ids)
            
            # 🔄 Ejecutar el plan si se generó uno
            if execution_results.get("plan"):
                logger.info("[OrchestratorService] 🚀 Ejecutando plan generado")
                
                # 🚀 FASE 1: Emisión de progreso antes de ejecutar el plan
                await self.emit_status_progress(4, 5, "Ejecutando plan generado...", 80.0)
                
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
                
                # 🎯 FASE 13: TRACKING DE EJECUCIÓN DEL PLAN
                if self.current_telemetry_context:
                    try:
                        self.telemetry_service.track_step_execution(
                            conversation_id=conversation_id,
                            step_number=1,
                            step_type="plan_execution_start",
                            duration_ms=0,  # Se medirá al final
                            success=True,
                            tokens_used=0,
                            cache_operations=0,
                            database_queries=0,
                            llm_calls=0,
                            metadata={
                                "plan_actions": len(execution_results.get('plan', {}).get('actions', [])),
                                "plan_steps": len(execution_results.get('plan', {}).get('steps', [])),
                                "context_size": len(str(execution_context))
                            }
                        )
                    except Exception as e:
                        logger.warning(f"[OrchestratorService] ⚠️ Error tracking inicio de ejecución: {e}")
                
                # 🔧 FIX: Mover execution_engine.run a thread pool para evitar bloquear el loop
                loop = asyncio.get_running_loop()
                plan_start_time = time.time()
                final_results = await execution_engine.run(
                    plan=execution_results.get("plan", {}),
                    chat_id=chat_id,
                    ctx=execution_context
                )
                plan_execution_time = (time.time() - plan_start_time) * 1000
                
                # Combinar resultados
                execution_results.update(final_results)
                
                # 🎯 FASE 13: TRACKING DE EJECUCIÓN COMPLETADA
                if self.current_telemetry_context:
                    try:
                        self.telemetry_service.track_step_execution(
                            conversation_id=conversation_id,
                            step_number=2,
                            step_type="plan_execution_complete",
                            duration_ms=plan_execution_time,
                            success=True,
                            tokens_used=final_results.get("token_count", 0),
                            cache_operations=0,  # TODO: Implementar tracking de cache
                            database_queries=len(final_results.get("variables", {})),
                            llm_calls=1,  # Asumimos al menos una llamada LLM
                            metadata={
                                "execution_time_ms": plan_execution_time,
                                "variables_generated": len(final_results.get('variables', {})),
                                "success": True
                            }
                        )
                    except Exception as e:
                        logger.warning(f"[OrchestratorService] ⚠️ Error tracking ejecución completada: {e}")
                
                # 🚀 FASE 1: Emisión de progreso después de ejecutar el plan
                await self.emit_status_progress(5, 5, "Plan ejecutado, finalizando...", 100.0)
                
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
            
            # 🎯 FASE 13: TRACKING DE ERROR
            if self.current_telemetry_context:
                try:
                    self.telemetry_service.track_error(
                        conversation_id=conversation_id,
                        error_type="execution_error",
                        error_message=str(e),
                        error_code="GRAPH_EXECUTION_FAILED",
                        error_stack=str(e.__traceback__),
                        step_number=1,
                        step_type="graph_execution",
                        user_input=message.content,
                        severity="high",
                        recovered=False,
                        recovery_action="error_handler_service"
                    )
                except Exception as telemetry_error:
                    logger.warning(f"[OrchestratorService] ⚠️ Error tracking error de telemetría: {telemetry_error}")
            
            # 🎯 FASE 11: Manejo de errores con remediación automática
            try:
                error_handler = self.factory.get_error_handler_service()
                user_facing_error = await error_handler.handle_error(
                    chat_id=str(chat_id),
                    error=e,
                    context={
                        "explorer": explorer,
                        "db_ids": db_ids,
                        "app_ids": app_ids,
                        "agent_id": agent_id,
                        "user_message": message.content
                    },
                    user_id=str(self.user_id)
                )
                
                # Usar el error procesado por el ErrorHandlerService
                execution_results = {
                    "error": user_facing_error.code,
                    "error_message": user_facing_error.human_message,
                    "suggested_actions": [
                        {
                            "label": action.label,
                            "action": action.action,
                            "description": action.description
                        }
                        for action in user_facing_error.suggested_actions[:3]
                    ],
                    "error_severity": user_facing_error.severity.value,
                    "retry_after": user_facing_error.retry_after
                }
                
                logger.info(f"[OrchestratorService] 🎯 FASE 11: Error manejado con remediación - {user_facing_error.code}")
                
                # 🎯 FASE 13: TRACKING DE RECUPERACIÓN DE ERROR
                if self.current_telemetry_context:
                    try:
                        self.telemetry_service.track_error(
                            conversation_id=conversation_id,
                            error_type="error_recovery",
                            error_message="Error recuperado por ErrorHandlerService",
                            error_code=user_facing_error.code,
                            step_number=1,
                            step_type="error_recovery",
                            user_input=message.content,
                            severity="medium",
                            recovered=True,
                            recovery_action="error_handler_service"
                        )
                    except Exception as telemetry_error:
                        logger.warning(f"[OrchestratorService] ⚠️ Error tracking recuperación de telemetría: {telemetry_error}")
                
            except Exception as error_handler_error:
                logger.error(f"[OrchestratorService] ❌ Error en ErrorHandlerService: {error_handler_error}")
                # Fallback a error básico
                execution_results = {"error": str(e)}
                
                # 🎯 FASE 13: TRACKING DE ERROR NO RECUPERADO
                if self.current_telemetry_context:
                    try:
                        self.telemetry_service.track_error(
                            conversation_id=conversation_id,
                            error_type="unrecovered_error",
                            error_message="Error no recuperado por ErrorHandlerService",
                            error_code="ERROR_HANDLER_FAILED",
                            error_stack=str(error_handler_error.__traceback__),
                            step_number=1,
                            step_type="error_handler_failure",
                            user_input=message.content,
                            severity="critical",
                            recovered=False,
                            recovery_action="none"
                        )
                    except Exception as telemetry_error:
                        logger.warning(f"[OrchestratorService] ⚠️ Error tracking error no recuperado de telemetría: {telemetry_error}")

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

        # 🎯 FASE 13: FINALIZAR TRACKING Y EMITIR SNAPSHOT DE TELEMETRÍA
        if self.current_telemetry_context:
            try:
                # Calcular métricas finales
                total_latency_ms = (time.time() - start_time) * 1000
                total_tokens_in = token_count or 0
                total_tokens_out = len(assistant_response.split()) if assistant_response else 0
                total_steps = len(steps) if steps else 0
                cache_hit_ratio = 0.0  # TODO: Implementar tracking de cache
                confirmations_required = 0  # TODO: Implementar tracking de confirmaciones
                
                # Finalizar tracking de conversación
                metrics = self.telemetry_service.end_conversation_tracking(
                    conversation_id=conversation_id
                )
                
                # Emitir snapshot de telemetría
                await self.emit_telemetry_snapshot(
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    latency_ms=total_latency_ms,
                    cache_hit_ratio=cache_hit_ratio,
                    steps_executed=total_steps,
                    confirmations_required=confirmations_required,
                    mode=Mode.EXPLORER if explorer else Mode.GUIDED
                )
                
                logger.info(f"[OrchestratorService] 🎯 FASE 13: Telemetría finalizada y snapshot emitido para conversación {conversation_id}")
                logger.info(f"[OrchestratorService] 📊 Métricas: {total_latency_ms:.1f}ms, {total_tokens_in}+{total_tokens_out} tokens, {total_steps} steps")
                
            except Exception as e:
                logger.warning(f"[OrchestratorService] ⚠️ Error finalizando telemetría: {e}")

        # 🚀 FASE 1: Emisión de progreso final antes de retornar
        await self.emit_status_progress(6, 6, "Respuesta lista, enviando...", 100.0)
        
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

    def _is_schema_intent(self, execution_results: Dict[str, Any], user_message: str) -> bool:
        """
        Determina si la intención del usuario es consultar el esquema de la base de datos.
        """
        intent_str = (execution_results.get("intent") or "").lower()
        user_lower = (user_message or "").lower()
        schema_keywords = [
            "tabla", "tablas", "columnas", "columna", "esquema", "schema",
            "estructura", "describe", "ddl", "keys", "primary key", "foreign key"
        ]
        
        return (
            intent_str in ["db_schema", "schema", "describe_schema", "schema_question", "db_read_schema"]
            or any(k in user_lower for k in schema_keywords)
        )

    def _is_schema_lookup_intent(self, user_message: str) -> bool:
        """
        Determina si la intención del usuario es una consulta de esquema simple
        que puede ser resuelta rápidamente sin LLM (Fast Schema Path).
        
        Este método es más específico que _is_schema_intent y se enfoca en
        consultas que pueden ser respondidas usando índices léxicos y cache.
        """
        if not user_message:
            return False
            
        user_lower = user_message.lower().strip()
        
        # Patrones de consulta que pueden ser resueltos rápidamente
        fast_schema_patterns = [
            # Consultas de estructura básica
            "qué tablas hay", "que tablas hay", "qué tablas existen", "que tablas existen",
            "muéstrame las tablas", "muestrame las tablas", "dame las tablas", "obtén las tablas",
            "listar tablas", "listar todas las tablas", "ver tablas", "ver todas las tablas",
            
            # Consultas de columnas específicas
            "qué columnas tiene", "que columnas tiene", "qué campos tiene", "que campos tiene",
            "estructura de", "esquema de", "describe", "ddl de",
            
            # Consultas de relaciones
            "qué claves tiene", "que claves tiene", "primary key", "foreign key",
            "relaciones de", "dependencias de", "referencias de",
            
            # Consultas de búsqueda simple
            "buscar tabla", "encontrar tabla", "tabla llamada", "tabla con nombre",
            "columna llamada", "campo llamado", "atributo llamado",
            
            # Consultas de conteo y resumen
            "cuántas tablas", "cuantas tablas", "cuántas columnas", "cuantas columnas",
            "total de tablas", "total de columnas", "resumen de esquema",
            
            # Consultas de validación
            "existe la tabla", "existe la columna", "está la tabla", "está la columna",
            "hay tabla", "hay columna", "tiene tabla", "tiene columna"
        ]
        
        # Verificar patrones exactos
        for pattern in fast_schema_patterns:
            if pattern in user_lower:
                return True
        
        # Verificar palabras clave individuales que indican consulta de esquema
        schema_keywords = [
            "tabla", "tablas", "columna", "columnas", "campo", "campos",
            "esquema", "schema", "estructura", "ddl", "describe",
            "primary", "foreign", "key", "keys", "relación", "relaciones"
        ]
        
        # Contar cuántas palabras clave están presentes
        keyword_count = sum(1 for keyword in schema_keywords if keyword in user_lower)
        
        # Si hay 2 o más palabras clave de esquema, es probablemente una consulta de esquema
        if keyword_count >= 2:
            return True
        
        # Verificar si la consulta es muy corta (menos de 50 caracteres) y contiene palabras de esquema
        if len(user_message) < 50 and keyword_count >= 1:
            return True
        
        # Verificar si la consulta termina con signos de interrogación y contiene palabras de esquema
        if user_lower.endswith("?") and keyword_count >= 1:
            return True
        
        return False

    def _generate_schema_response(self, context: Dict[str, Any], db_ids: Optional[List[UUID]], user_message: str) -> str:
        """
        Genera una respuesta para consultas de esquema usando el contexto ya cargado.
        """
        table_names: List[str] = []
        db_schemas = context.get("database_schemas", {}) or {}
        
        if db_ids:
            for _dbid in db_ids:
                schema_list = db_schemas.get(_dbid)
                if isinstance(schema_list, list):
                    for t in schema_list:
                        if isinstance(t, dict) and t.get("name"):
                            table_names.append(str(t["name"]))

        # Deduplicar preservando orden
        seen = set()
        unique_tables: List[str] = []
        for n in table_names:
            if n not in seen:
                seen.add(n)
                unique_tables.append(n)

        # Sugerir tablas candidatas de forma GENÉRICA (sin dominios fijos)
        query_tokens = {t for t in re.split(r"[^a-z0-9_]+", user_message.lower()) if len(t) >= 3}
        scores = []
        for name in unique_tables:
            nl = name.lower()
            # señal 1: hay algún token de la pregunta como substring en el nombre de tabla
            hit = any(tok in nl for tok in query_tokens)
            # señal 2: similitud difusa
            ratio = difflib.SequenceMatcher(None, " ".join(sorted(query_tokens)), nl).ratio() if query_tokens else 0.0
            score = (1.0 if hit else 0.0) + ratio
            scores.append((score, name))

        scores.sort(reverse=True)
        candidates = [n for sc, n in scores[:3] if sc > 0.3]

        preview_count = min(10, len(unique_tables))
        lines: List[str] = []
        if preview_count > 0:
            lines.append(f"Estas son algunas tablas de tu base (mostrando las primeras {preview_count}):")
            for n in unique_tables[:preview_count]:
                lines.append(f"- {n}")
            if len(unique_tables) > preview_count:
                lines.append(f"... y {len(unique_tables) - preview_count} más.")
        else:
            lines.append("No pude leer nombres de tablas del caché en este momento.")

        if candidates:
            lines.append("")
            lines.append("Tablas más relacionadas con tu pregunta:")
            for c in candidates:
                lines.append(f"- {c}")
            lines.append("")
            lines.append(f"Ejemplo rápido: `SELECT * FROM {candidates[0]} LIMIT 3;`")

        return "\n".join(lines)

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
        logger.info(f"[OrchestratorService] 🔄 Delegando RAG iterativo al módulo especializado")
        
        # 🔄 REFACTORIZADO: Usar módulo especializado IterativeRAGHandler
        return await self.iterative_rag_handler.run_iterative_rag(
            chat_id=chat_id,
            message=message,
            db_ids=db_ids,
            app_ids=app_ids,
            context_loader=self.context_loader,
            graph_runner=self.graph_runner,
            explorer=explorer,
            max_iterations=max_iterations
        )

    def _validate_compact_schemas(self, compact_schemas: Dict, db_ids: List) -> bool:
        """Validar que hay compact_schemas válidos para las DBs solicitadas"""
        # 🔄 REFACTORIZADO: Usar módulo especializado SchemaValidator
        return self.schema_validator.validate_compact_schemas(compact_schemas, db_ids)

    async def _generate_final_answer(
        self, 
        question: str, 
        accumulated_results: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Genera la respuesta final basándose en todos los resultados acumulados.
        """
        logger.info("[OrchestratorService] 📝 Delegando generación de respuesta final al módulo especializado")
        
        # 🔄 REFACTORIZADO: Usar módulo especializado IterativeRAGHandler
        return await self.iterative_rag_handler._generate_final_answer(
            question, accumulated_results, context
        )

    def _format_results_for_final_answer(self, results: Dict[str, Any]) -> str:
        """Formatea los resultados acumulados para la respuesta final"""
        # 🔄 REFACTORIZADO: Usar módulo especializado ResponseFormatter
        return self.response_formatter.format_results_for_final_answer(results)

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
        """Almacenar mensaje del usuario usando ChatHistoryManager"""
        await self.chat_history_manager.store_user_message_async(chat_id, message)

    @monitor_performance("save_assistant_message")
    @profile_function("save_assistant_message")
    async def _save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ):
        """Guardar mensaje del asistente usando ChatHistoryManager"""
        await self.chat_history_manager.save_assistant_message_async(
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
        """Aplicar token budget a app IDs usando AppFunctionManager"""
        if not app_ids:
            return None
        
        # Limitar a TOP_K_APPS para control de tokens
        limited_app_ids = app_ids[:self.TOP_K_APPS]
        
        if len(limited_app_ids) < len(app_ids):
            logger.info(f"[OrchestratorService] 🔒 Token budget: apps limitados de {len(app_ids)} a {len(limited_app_ids)}")
        
        return limited_app_ids
    
    def _estimate_tokens_for_context(self, context: Dict[str, Any]) -> int:
        """Estima el número de tokens para un contexto dado usando los managers especializados"""
        try:
            total_chars = 0
            
            # 1. Historial usando ChatHistoryManager
            if "history" in context:
                history = context["history"]
                total_chars += self.chat_history_manager.estimate_history_tokens(history)
            
            # 2. Esquemas de base de datos
            if "compact_schemas" in context:
                for db_id, schema_data in context["compact_schemas"].items():
                    if isinstance(schema_data, dict) and "compact" in schema_data:
                        total_chars += len(schema_data["compact"])
            
            # 3. Descriptores de apps
            if "app_descriptors_compact" in context and context["app_descriptors_compact"]:
                total_chars += len(context["app_descriptors_compact"])
            
            # 4. Funciones y apps usando AppFunctionManager
            if "functions" in context or "apps" in context or "mcp_tools" in context:
                apps = context.get("apps", [])
                functions = context.get("functions", [])
                mcp_tools = context.get("mcp_tools", {})
                total_chars += self.app_function_manager.estimate_app_function_tokens(apps, functions, mcp_tools)
            
            # Estimación aproximada: 1 token ≈ 4 caracteres
            estimated_tokens = total_chars // 4
            logger.debug(f"[OrchestratorService] 🔍 Tokens estimados para contexto: {estimated_tokens}")
            return estimated_tokens
            
        except Exception as e:
            logger.warning(f"[OrchestratorService] ⚠️ Error estimando tokens del contexto: {e}")
            return 0
    
    def _should_use_lite_payload(self, estimated_tokens: int) -> bool:
        """Determinar si usar payload lite basado en tokens estimados"""
        return estimated_tokens > self.MAX_INPUT_TOKENS
    
    async def _build_lite_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Construir payload lite usando AppFunctionManager"""
        apps = context.get('apps', [])
        functions = context.get('functions', [])
        mcp_tools = context.get('mcp_tools', {})
        
        return self.app_function_manager.create_lite_payload(apps, functions, mcp_tools)

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
        """Optimizar esquema con resultados de búsqueda usando SchemaManager"""
        return self.schema_manager.optimize_schema_with_search_results(schema, search_results)

    @monitor_performance("load_database_schemas")
    @profile_function("load_database_schemas")
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Cargar esquemas de base de datos usando SchemaManager.
        
        Returns:
            Dict con:
            - 'schemas': Dict[UUID, List[Dict]] - Esquemas detallados (legacy)
            - 'compact_schemas': Dict[UUID, str] - Esquemas compactos para LLM
            - 'cache_status': Dict[UUID, str] - Estado del cache por DB
        """
        return await self.schema_manager.load_database_schemas_async(db_ids)
    
    def _introspect_minimal_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección mínima de esquema usando SchemaManager"""
        return self.schema_manager._introspect_minimal_schema(db_id)

    def _convert_snapshot_to_legacy(self, snapshot_tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convertir snapshot a formato legacy usando SchemaManager"""
        return self.schema_manager._convert_snapshot_to_legacy(snapshot_tables)

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
        """Cargar historial del chat usando ChatHistoryManager"""
        return await self.chat_history_manager.load_history_async(chat_id)

    @monitor_performance("load_apps")
    @profile_function("load_apps")
    async def _load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Cargar aplicaciones usando AppFunctionManager"""
        return await self.app_function_manager.load_apps_async(app_ids)

    @monitor_performance("load_functions")
    @profile_function("load_functions")
    async def _load_functions_async(self) -> List[Dict[str, Any]]:
        """Cargar funciones disponibles usando AppFunctionManager"""
        return await self.app_function_manager.load_functions_async()

    @monitor_performance("load_mcp_tools")
    @profile_function("load_mcp_tools")
    async def _load_mcp_tools_async(self) -> Dict[str, Any]:
        """Cargar herramientas MCP disponibles usando AppFunctionManager"""
        return await self.app_function_manager.load_mcp_tools_async()

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
        """Aplicar trimming inteligente usando los managers especializados"""
        trimmed_context = context.copy()
        
        # Trimming de historial usando ChatHistoryManager
        if 'chat_history' in trimmed_context:
            history = trimmed_context['chat_history']
            estimated_tokens = self.chat_history_manager.estimate_history_tokens(history)
            if estimated_tokens > self.MAX_HISTORY_CHARS:
                # Aplicar trimming inteligente
                trimmed_context['chat_history'] = self.chat_history_manager._apply_intelligent_history_trimming(history)
                logger.info(f"[OrchestratorService] 🔒 Token budget: historial optimizado de {estimated_tokens} a {self.MAX_HISTORY_CHARS} chars")
        
        # Trimming de esquemas usando SchemaManager
        if 'database_schemas' in trimmed_context:
            schemas = trimmed_context['database_schemas']
            for db_id, schema in schemas.items():
                if isinstance(schema, str) and len(schema) > self.MAX_SCHEMA_CHARS:
                    trimmed_context['database_schemas'][db_id] = schema[:self.MAX_SCHEMA_CHARS] + "... [truncado]"
                    logger.info(f"[OrchestratorService] 🔒 Token budget: schema DB {db_id} truncado a {self.MAX_SCHEMA_CHARS} chars")
        
        # Trimming de apps usando AppFunctionManager
        if 'apps' in trimmed_context:
            apps = trimmed_context['apps']
            for app in apps:
                if 'description' in app and len(app['description']) > self.MAX_APP_DESCRIPTOR_CHARS:
                    app['description'] = app['description'][:self.MAX_APP_DESCRIPTOR_CHARS] + "... [truncado]"
        
        # Trimming de funciones usando AppFunctionManager
        if 'functions' in trimmed_context:
            functions = trimmed_context['functions']
            for func in functions:
                if 'description' in func and len(func['description']) > self.MAX_FUNCTION_DESCRIPTION_CHARS:
                    func['description'] = func['description'][:self.MAX_FUNCTION_DESCRIPTION_CHARS] + "... [truncado]"
        
        return trimmed_context

    def _should_force_plan(self, db_ids: Optional[List[UUID]], user_message: str, execution_results: Dict[str, Any]) -> bool:
        """Determina si se debe forzar la generación de un plan basado en la intención del usuario"""
        # ⛔ Si la intención es de ESQUEMA, no forzar plan
        intent_str = (execution_results.get("intent") or "").lower()
        if intent_str in ["db_schema", "schema", "describe_schema", "schema_question", "db_read_schema"]:
            logger.info("[OrchestratorService] ⛔ No se fuerza plan: intención de esquema")
            return False

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
            
            # 🎯 FASE 11: Manejo de errores con remediación automática
            try:
                error_handler = self.factory.get_error_handler_service()
                user_facing_error = await error_handler.handle_error(
                    chat_id=str(chat_id),
                    error=e,
                    context={
                        "operation": "minimal_context",
                        "explorer": explorer,
                        "db_ids": db_ids,
                        "app_ids": app_ids
                    },
                    user_id=str(self.user_id)
                )
                
                return {
                    "assistant_response": f"❌ {user_facing_error.human_message}",
                    "error": user_facing_error.code,
                    "suggested_actions": [
                        {
                            "label": action.label,
                            "action": action.action,
                            "description": action.description
                        }
                        for action in user_facing_error.suggested_actions[:3]
                    ],
                    "error_severity": user_facing_error.severity.value
                }
                
            except Exception as error_handler_error:
                logger.error(f"[OrchestratorService] ❌ Error en ErrorHandlerService: {error_handler_error}")
                # Fallback a respuesta básica
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
        """Estima el número de tokens para un contexto dado usando los managers especializados"""
        try:
            total_chars = 0
            
            # 1. Historial usando ChatHistoryManager
            if "history" in context:
                history = context["history"]
                total_chars += self.chat_history_manager.estimate_history_tokens(history)
            
            # 2. Esquemas de base de datos
            if "compact_schemas" in context:
                for db_id, schema_data in context["compact_schemas"].items():
                    if isinstance(schema_data, dict) and "compact" in schema_data:
                        total_chars += len(schema_data["compact"])
            
            # 3. Descriptores de apps
            if "app_descriptors_compact" in context and context["app_descriptors_compact"]:
                total_chars += len(context["app_descriptors_compact"])
            
            # 4. Funciones y apps usando AppFunctionManager
            if "functions" in context or "apps" in context or "mcp_tools" in context:
                apps = context.get("apps", [])
                functions = context.get("functions", [])
                mcp_tools = context.get("mcp_tools", {})
                total_chars += self.app_function_manager.estimate_app_function_tokens(apps, functions, mcp_tools)
            
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

    def _store_user_message(self, chat_id: UUID, message: ChatMessage) -> None:
        """Almacenar mensaje del usuario usando ChatHistoryManager"""
        asyncio.create_task(self.chat_history_manager.store_user_message_async(chat_id, message))

    def _save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        """Guardar mensaje del asistente usando ChatHistoryManager"""
        asyncio.create_task(self.chat_history_manager.save_assistant_message_async(
            chat_id, content, token_count, executed_strategy_id
        ))

    def _load_history_with_session(self, chat_id: UUID) -> List[Any]:
        """Cargar historial con sesión usando ChatHistoryManager"""
        return self.chat_history_manager._load_history_with_session(chat_id)

    def _load_agent_prompt(self, agent_id: Optional[UUID]) -> str:
        """Cargar prompt del agente usando AgentManager"""
        if not agent_id:
            return ""
        try:
            return self.agent_manager.get_agent_prompt(agent_id)
        except Exception as e:
            logger.warning(f"[OrchestratorService] Agent prompt load failed: {e}")
            return ""

    def _check_usage_limit(self) -> None:
        """Verificar límites de uso usando UsageService"""
        try:
            self.factory.get_usage_service().check_limit()
        except Exception as e:
            logger.warning(f"[OrchestratorService] Usage limit check failed: {e}")

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

    # ===================================================
    #  MÉTODOS STUB DE EMISIÓN WEBSOCKET (FASE 0)
    # ===================================================
    
    async def emit_status_typing(self, is_typing: bool = True) -> bool:
        """Emite evento de estado de escritura (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_status_typing(is_typing)
        return False
    
    async def emit_status_progress(
        self, 
        step: int, 
        total_steps: int, 
        message: str, 
        percentage: Optional[float] = None
    ) -> bool:
        """Emite evento de progreso (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_status_progress(step, total_steps, message, percentage)
        return False
    
    async def emit_decision_request(
        self,
        decision_id: str,
        title: str,
        description: str,
        options: list,
        timeout_seconds: int = 30,
        default_action: str = "cancel"
    ) -> bool:
        """Emite solicitud de decisión (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_decision_request(
                decision_id, title, description, options, timeout_seconds, default_action
            )
        return False
    
    async def emit_result_partial(
        self,
        step: int,
        data: Dict[str, Any],
        preview: Optional[str] = None
    ) -> bool:
        """Emite resultado parcial (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_result_partial(step, data, preview)
        return False
    
    async def emit_result_final(
        self,
        summary: str,
        data: Dict[str, Any],
        next_actions: list,
        usage_stats: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emite resultado final (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_result_final(summary, data, next_actions, usage_stats)
        return False
    
    async def emit_notice_info(
        self,
        message: str,
        level: str = "info",
        actions: Optional[list] = None
    ) -> bool:
        """Emite notificación informativa (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_notice_info(message, level, actions)
        return False
    
    async def emit_error_user_facing(
        self,
        code: str,
        human_message: str,
        suggested_actions: list,
        technical_details: Optional[str] = None
    ) -> bool:
        """Emite error para el usuario (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_error_user_facing(
                code, human_message, suggested_actions, technical_details
            )
        return False
    
    async def emit_telemetry_snapshot(
        self,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cache_hit_ratio: float,
        steps_executed: int,
        confirmations_required: int,
        mode: Mode
    ) -> bool:
        """Emite snapshot de telemetría al finalizar la ejecución."""
        try:
            event = {
                "type": "telemetry.snapshot",
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "cache_hit_ratio": cache_hit_ratio,
                "steps_executed": steps_executed,
                "confirmations_required": confirmations_required,
                "mode": mode.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.ws_emitter.emit(event)
            logger.info(f"[OrchestratorService] 📊 Telemetría emitida: {latency_ms:.1f}ms, {tokens_in}+{tokens_out} tokens")
            return True
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error emitiendo telemetría: {e}")
            return False
    
    async def emit_resource_proposal(
        self,
        proposal_id: str,
        title: str,
        description: str,
        options: List[Dict[str, Any]],
        user_message: str,
        timeout_seconds: int = 60,
        default_action: str = "explore_only"
    ) -> bool:
        """Emite propuesta de recursos para modo Explorer."""
        try:
            event = {
                "type": "resource.proposal",
                "proposal_id": proposal_id,
                "title": title,
                "description": description,
                "options": options,
                "user_message": user_message,
                "timeout_seconds": timeout_seconds,
                "default_action": default_action,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.ws_emitter.emit(event)
            logger.info(f"[OrchestratorService] 🎯 Propuesta de recursos emitida: {proposal_id}")
            return True
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error emitiendo propuesta de recursos: {e}")
            return False

    async def handle_token_budget_mode_change(
        self,
        chat_id: UUID,
        new_mode: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🎯 FASE 10: Maneja cambios de modo de TokenBudget (rápido/equilibrado/preciso).
        
        Args:
            chat_id: ID del chat
            new_mode: Nuevo modo solicitado
            context: Contexto actual
            
        Returns:
            Dict con información del cambio de modo
        """
        try:
            logger.info(f"[OrchestratorService] 🎯 FASE 10: Cambiando modo a '{new_mode}' para chat {chat_id}")
            
            # Aplicar límites del nuevo modo
            if new_mode == "rápido":
                # Modo rápido: límites más estrictos
                self.token_budget.MAX_INPUT_TOKENS = 4800  # 60% del original
                self.token_budget.MAX_HISTORY_TURNS = 3
                self.token_budget.MAX_SCHEMA_CHARS = 1800
                self.token_budget.TOP_K_DBS = 1
                self.token_budget.TOP_K_APPS = 1
                
            elif new_mode == "equilibrado":
                # Modo equilibrado: límites moderados
                self.token_budget.MAX_INPUT_TOKENS = 6400  # 80% del original
                self.token_budget.MAX_HISTORY_TURNS = 4
                self.token_budget.MAX_SCHEMA_CHARS = 2400
                self.token_budget.TOP_K_DBS = 2
                self.token_budget.TOP_K_APPS = 1
                
            elif new_mode == "preciso":
                # Modo preciso: límites originales
                self.token_budget.MAX_INPUT_TOKENS = 8000  # 100% del original
                self.token_budget.MAX_HISTORY_TURNS = 6
                self.token_budget.MAX_SCHEMA_CHARS = 3000
                self.token_budget.TOP_K_DBS = 2
                self.token_budget.TOP_K_APPS = 2
                
            else:
                raise ValueError(f"Modo no válido: {new_mode}")
            
            # Re-aplicar trimming con nuevos límites
            re_trimmed_context = self.token_budget.apply_intelligent_context_trimming(context)
            
            # Emitir confirmación del cambio
            await self.emit_notice_info(
                message=f"✅ Modo cambiado a '{new_mode}'. Límites ajustados para optimizar rendimiento.",
                level="success",
                actions=[
                    {"label": "Ver límites actuales", "action": "show_current_limits"},
                    {"label": "Cambiar modo nuevamente", "action": "change_mode_again"},
                    {"label": "Continuar", "action": "continue_with_new_mode"}
                ]
            )
            
            # Calcular tokens estimados con nuevo modo
            estimated_tokens = self.token_budget.estimate_tokens_for_context(re_trimmed_context)
            budget_usage = (estimated_tokens / self.token_budget.MAX_INPUT_TOKENS) * 100
            
            logger.info(f"[OrchestratorService] 🎯 FASE 10: Modo '{new_mode}' aplicado - {budget_usage:.1f}% de uso")
            
            return {
                "mode_changed": True,
                "new_mode": new_mode,
                "estimated_tokens": estimated_tokens,
                "budget_usage_percent": budget_usage,
                "context_optimized": True,
                "trimmed_context": re_trimmed_context
            }
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cambiando modo de TokenBudget: {e}")
            await self.emit_error_user_facing(
                code="MODE_CHANGE_ERROR",
                human_message=f"No se pudo cambiar al modo '{new_mode}'. Usando configuración por defecto.",
                suggested_actions=[
                    "Intentar cambiar modo nuevamente",
                    "Continuar con modo actual",
                    "Contactar soporte si el problema persiste"
                ],
                technical_details=str(e)
            )
            
            return {
                "mode_changed": False,
                "error": str(e),
                "context_optimized": False
            }
