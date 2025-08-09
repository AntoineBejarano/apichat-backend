from typing import Dict, Any, Optional, List, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, END
from app.core.service_factory import ServiceFactory
from app.schemas.plan_schema import PlanModel
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.services.intent_classifier_service import IntentType
from app.services.telemetry_service import EventType, TelemetryContextManager

import logging
import time

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Estado del GuidedGraph
# ──────────────────────────────────────────────────────
class GuidedState(TypedDict, total=False):
    chat_id: str
    message: ChatMessage

    # Recursos específicos (cuando se proporcionan)
    db_ids: Optional[List[UUID]]                # IDs de DB específicas
    app_ids: Optional[List[UUID]]               # IDs de Apps específicas
    
    # Contexto de cache (puede venir del Orchestrator)
    compact_schemas: Optional[Dict[str, str]]   # {db_id: compact_schema}
    cache_status: Optional[Dict[str, str]]      # {db_id: status}
    app_descriptors: Optional[Dict[str, str]]   # {app_id: compact_descriptor}
    
    # Contexto adicional
    functions: Optional[List[Function]]
    available_mcp_tools: Optional[Any]
    history: Optional[List[Dict[str, Any]]]
    db_dialect: Optional[str]
    
    # Clasificación de intención
    intent: Optional[IntentType]
    intent_confidence: Optional[float]
    requires_resources: Optional[bool]
    
    # Salidas
    plan: Optional[PlanModel]
    assistant_response: Optional[str]
    error: Optional[str]
    
    # Telemetría
    cache_hits: Optional[int]
    cache_misses: Optional[int]
    processing_time: Optional[float]


class GuidedGraph:
    def __init__(self, factory: ServiceFactory, max_schema_chars: int = 80000, max_app_chars: int = 40000):
        self.factory = factory
        self.max_schema_chars = max_schema_chars
        self.max_app_chars = max_app_chars

    async def run(self, context: GuidedState) -> GuidedState:
        builder = StateGraph(GuidedState)

        async def classify_intent(state: GuidedState) -> GuidedState:
            """Clasifica la intención del usuario"""
            telemetry = self.factory.get_telemetry_service()
            user_id = self.factory.user.id
            
            with TelemetryContextManager(telemetry, EventType.INTENT_CLASSIFICATION, user_id) as ctx:
                try:
                    message = state.get("message")
                    if not message:
                        ctx.success = False
                        ctx.error_message = "No se proporcionó mensaje"
                        return {
                            **state,
                            "error": "No se proporcionó mensaje",
                            "assistant_response": "Error: No se proporcionó mensaje."
                        }
                    
                    # Clasificar intención
                    classifier = self.factory.get_intent_classifier_service()
                    classification = classifier.classify(message.content)
                    
                    # Telemetría específica de clasificación
                    ctx.metadata.update({
                        "intent": classification["intent"].value,
                        "confidence": classification["confidence"],
                        "message_length": len(message.content)
                    })
                    
                    logger.info(f"[GuidedGraph] 🎯 Intención: {classification['intent'].value} (conf: {classification['confidence']:.2f})")
                    
                    return {
                        **state,
                        "intent": classification["intent"],
                        "intent_confidence": classification["confidence"],
                        "requires_resources": classification["requires_resources"]
                    }
                    
                except Exception as e:
                    logger.exception("[GuidedGraph] ❌ Error clasificando intención")
                    ctx.success = False
                    ctx.error_message = str(e)
                    return {
                        **state,
                        "error": str(e),
                        "assistant_response": "Error interno al procesar tu mensaje."
                    }

        async def check_resources(state: GuidedState) -> GuidedState:
            """Verifica si se tienen los recursos necesarios o si es chat normal"""
            try:
                db_ids = state.get("db_ids", [])
                app_ids = state.get("app_ids", [])
                intent = state.get("intent")
                requires_resources = state.get("requires_resources", False)
                
                # Si no requiere recursos, es chat normal
                if not requires_resources or intent == IntentType.CHAT:
                    logger.info("[GuidedGraph] 💬 Modo chat normal - sin recursos específicos")
                    return {
                        **state,
                        "assistant_response": await self._handle_chat_response(state)
                    }
                
                # Si requiere recursos pero no se proporcionaron, pedir aclaración
                if requires_resources and not db_ids and not app_ids:
                    logger.info("[GuidedGraph] ❓ Requiere recursos pero no se especificaron")
                    classifier = self.factory.get_intent_classifier_service()
                    clarification = classifier.get_clarification_message(intent)
                    return {
                        **state,
                        "assistant_response": clarification
                    }
                
                # Tiene recursos específicos, continuar con warm-up
                logger.info(f"[GuidedGraph] 🎯 Recursos específicos: {len(db_ids)} DBs, {len(app_ids)} apps")
                return state
                
            except Exception as e:
                logger.exception("[GuidedGraph] ❌ Error verificando recursos")
                return {
                    **state,
                    "error": str(e),
                    "assistant_response": "Error interno al verificar recursos."
                }

        async def ensure_warm_resources(state: GuidedState) -> GuidedState:
            """Asegura que los recursos (DB schemas + App descriptors) estén warm"""
            telemetry = self.factory.get_telemetry_service()
            user_id = self.factory.user.id
            
            with TelemetryContextManager(telemetry, EventType.SCHEMA_WARM_UP, user_id) as ctx:
                try:
                    start_time = time.time()
                    
                    db_ids = state.get("db_ids", [])
                    app_ids = state.get("app_ids", [])
                    
                    ctx.metadata.update({
                        "db_count": len(db_ids),
                        "app_count": len(app_ids)
                    })
                    
                    # Warm-up DB schemas
                    final_compact_schemas = state.get("compact_schemas", {})
                    final_cache_status = state.get("cache_status", {})
                    
                    if db_ids:
                        logger.info(f"[GuidedGraph] 🔥 Warming up {len(db_ids)} DB schemas")
                        
                        # Si no vienen del orchestrator, usar el servicio directamente
                        if not final_compact_schemas:
                            orchestrator = self.factory.get_orchestrator_service()
                            db_results = await orchestrator._load_database_schemas_async(db_ids)
                            
                            final_compact_schemas = db_results.get("compact_schemas", {})
                            final_cache_status = db_results.get("cache_status", {})
                        
                        # Registrar eventos de cache para cada DB
                        for db_id, status in final_cache_status.items():
                            operation = "hit" if status == "cache_hit" else "miss"
                            telemetry.track_cache_operation(
                                user_id=user_id,
                                operation=operation,
                                resource_type="db_schema",
                                resource_id=str(db_id)
                            )
                    
                    # Warm-up App descriptors
                    app_descriptors = {}
                    if app_ids:
                        logger.info(f"[GuidedGraph] 🔥 Warming up {len(app_ids)} App descriptors")
                        app_cache_service = self.factory.get_app_descriptor_cache_service()
                        app_descriptors = app_cache_service.get_app_descriptors_compact(app_ids, self.max_app_chars)
                        
                        # Registrar eventos para apps
                        for app_id in app_ids:
                            telemetry.track_event(
                                event_type=EventType.APP_DESCRIPTOR_LOAD,
                                user_id=user_id,
                                success=str(app_id) in app_descriptors,
                                metadata={"app_id": str(app_id)}
                            )
                    
                    # Calcular estadísticas
                    cache_hits = sum(1 for status in final_cache_status.values() if status == "cache_hit")
                    cache_misses = len(final_cache_status) - cache_hits
                    processing_time = time.time() - start_time
                    
                    # Actualizar telemetría con resultados
                    ctx.metadata.update({
                        "cache_hits": cache_hits,
                        "cache_misses": cache_misses,
                        "apps_loaded": len(app_descriptors),
                        "total_processing_time_s": processing_time
                    })
                    
                    logger.info(f"[GuidedGraph] ✅ Warm-up completado: {cache_hits} hits, {cache_misses} misses, {len(app_descriptors)} apps ({processing_time:.2f}s)")
                    
                    return {
                        **state,
                        "compact_schemas": final_compact_schemas,
                        "cache_status": final_cache_status,
                        "app_descriptors": app_descriptors,
                        "cache_hits": cache_hits,
                        "cache_misses": cache_misses,
                        "processing_time": processing_time
                    }
                    
                except Exception as e:
                    logger.exception("[GuidedGraph] ❌ Error en warm-up de recursos")
                    ctx.success = False
                    ctx.error_message = str(e)
                    return {
                        **state,
                        "error": str(e),
                        "assistant_response": "Error interno al preparar recursos."
                    }

        async def plan_or_reply(state: GuidedState) -> GuidedState:
            """Genera plan o respuesta con contexto completo"""
            telemetry = self.factory.get_telemetry_service()
            user_id = self.factory.user.id
            
            with TelemetryContextManager(telemetry, EventType.PLAN_GENERATION, user_id) as ctx:
                try:
                    message = state.get("message")
                    if not message:
                        ctx.success = False
                        ctx.error_message = "No se proporcionó mensaje"
                        return {
                            **state,
                            "error": "No se proporcionó mensaje",
                            "assistant_response": "Error: No se proporcionó mensaje."
                        }

                    # Construir contexto para el LLM
                    compact_schemas = state.get("compact_schemas", {})
                    app_descriptors = state.get("app_descriptors", {})
                    
                    ctx.metadata.update({
                        "has_db_schemas": bool(compact_schemas),
                        "has_app_descriptors": bool(app_descriptors),
                        "db_count": len(compact_schemas),
                        "app_count": len(app_descriptors)
                    })
                    
                    # Construir DB schema combinado
                    db_schema = None
                    if compact_schemas:
                        schema_parts = []
                        for db_id, compact_schema in compact_schemas.items():
                            if compact_schema and compact_schema.strip():
                                schema_parts.append(f"-- DATABASE {db_id} --")
                                schema_parts.append(compact_schema)
                                schema_parts.append("")
                        
                        if schema_parts:
                            db_schema = "\n".join(schema_parts)
                            
                            # Aplicar límite de caracteres
                            if len(db_schema) > self.max_schema_chars:
                                logger.warning(f"[GuidedGraph] ⚠️ DB Schema muy grande ({len(db_schema)} chars), truncando a {self.max_schema_chars}")
                                db_schema = db_schema[:self.max_schema_chars] + "\n-- [SCHEMA TRUNCATED DUE TO SIZE] --"
                            
                            logger.info(f"[GuidedGraph] ✅ DB Schema listo: {len(compact_schemas)} DBs, {len(db_schema)} chars")

                    # Construir App descriptors combinado
                    app_descriptors_compact = None
                    if app_descriptors:
                        app_parts = []
                        for app_id, descriptor in app_descriptors.items():
                            if descriptor and descriptor.strip():
                                app_parts.append(f"-- APP {app_id} --")
                                app_parts.append(descriptor)
                                app_parts.append("")
                        
                        if app_parts:
                            app_descriptors_compact = "\n".join(app_parts)
                            logger.info(f"[GuidedGraph] ✅ App Descriptors listos: {len(app_descriptors)} apps, {len(app_descriptors_compact)} chars")

                    # Preparar IDs como UUIDs
                    db_ids_uuid = []
                    if compact_schemas:
                        for db_id in compact_schemas.keys():
                            try:
                                db_ids_uuid.append(db_id if isinstance(db_id, UUID) else UUID(str(db_id)))
                            except ValueError:
                                logger.warning(f"[GuidedGraph] ⚠️ ID de DB inválido: {db_id}")

                    # Llamar al planner
                    logger.info(f"[GuidedGraph] 🤖 Consultando AI con contexto completo")
                    result = await self.factory.get_openai_service().plan_actions(
                        chat_id=state["chat_id"],
                        user_message=message,
                        db_schema=db_schema,
                        app_descriptors_compact=app_descriptors_compact,  # NUEVO: Descriptores de apps
                        available_functions=state.get("functions", []),
                        available_mcp_tools=state.get("available_mcp_tools"),
                        history=state.get("history", []),
                        db_ids=db_ids_uuid,
                        use_enriched_context=False
                    )

                    # Procesar resultado
                    if result.get("actions"):
                        plan = PlanModel.model_validate(result)
                        ctx.metadata.update({
                            "result_type": "plan",
                            "action_count": len(plan.actions)
                        })
                        logger.info(f"[GuidedGraph] ✅ Plan generado: {len(plan.actions)} acciones")
                        return {**state, "plan": plan}

                    if result.get("assistant_response"):
                        ctx.metadata.update({
                            "result_type": "assistant_response",
                            "response_length": len(result["assistant_response"])
                        })
                        logger.info("[GuidedGraph] ✅ Respuesta directa generada")
                        return {
                            **state,
                            "assistant_response": result["assistant_response"]
                        }

                    # Fallback
                    ctx.metadata["result_type"] = "fallback"
                    logger.warning("[GuidedGraph] ⚠️ Sin respuesta del modelo")
                    return {
                        **state,
                        "assistant_response": "Disculpa, no he podido procesar tu solicitud."
                    }

                except Exception as e:
                    logger.exception("[GuidedGraph] ❌ Error generando plan/respuesta")
                    ctx.success = False
                    ctx.error_message = str(e)
                    return {
                        **state,
                        "error": str(e),
                        "assistant_response": "Ha ocurrido un error interno. Inténtalo de nuevo."
                    }

        # Definir flujo condicional
        def should_continue_to_resources(state: GuidedState) -> str:
            """Decide si continuar con recursos o terminar en chat"""
            if state.get("assistant_response"):
                return "END"
            return "ensure_warm_resources"
        
        def should_plan(state: GuidedState) -> str:
            """Decide si planificar o terminar"""
            if state.get("assistant_response") or state.get("error"):
                return "END"
            return "plan_or_reply"
        
        # Construir grafo
        builder.add_node("classify_intent", classify_intent)
        builder.add_node("check_resources", check_resources)
        builder.add_node("ensure_warm_resources", ensure_warm_resources)
        builder.add_node("plan_or_reply", plan_or_reply)
        
        # Definir flujo
        builder.set_entry_point("classify_intent")
        builder.add_edge("classify_intent", "check_resources")
        builder.add_conditional_edges(
            "check_resources",
            should_continue_to_resources,
            {"ensure_warm_resources": "ensure_warm_resources", "END": END}
        )
        builder.add_conditional_edges(
            "ensure_warm_resources",
            should_plan,
            {"plan_or_reply": "plan_or_reply", "END": END}
        )
        builder.set_finish_point("plan_or_reply")

        graph = builder.compile()
        return await graph.ainvoke(context)

    # ──────────────────────────────────────────────────────
    #   Helpers
    # ──────────────────────────────────────────────────────
    async def _handle_chat_response(self, state: GuidedState) -> str:
        """Maneja respuestas de chat normal sin recursos específicos"""
        try:
            message = state.get("message")
            if not message:
                return "¿En qué puedo ayudarte?"
            
            # Para chat normal, usar OpenAI sin contexto específico
            result = await self.factory.get_openai_service().plan_actions(
                chat_id=state["chat_id"],
                user_message=message,
                db_schema=None,
                available_functions=[],
                history=state.get("history", []),
                use_enriched_context=False
            )
            
            return result.get("assistant_response", "¿En qué más puedo ayudarte?")
            
        except Exception as e:
            logger.exception("[GuidedGraph] ❌ Error en respuesta de chat")
            return "Disculpa, ha ocurrido un error. ¿Podrías intentar de nuevo?"

    def _validate_resources(self, state: GuidedState) -> bool:
        """Valida que los recursos requeridos estén disponibles y válidos"""
        try:
            db_ids = state.get("db_ids", [])
            app_ids = state.get("app_ids", [])
            compact_schemas = state.get("compact_schemas", {})
            app_descriptors = state.get("app_descriptors", {})
            
            # Verificar que las DBs solicitadas tengan schemas válidos
            for db_id in db_ids:
                db_key = str(db_id)
                if db_key not in compact_schemas or not compact_schemas[db_key]:
                    logger.warning(f"[GuidedGraph] ⚠️ DB {db_id} sin schema válido")
                    return False
            
            # Verificar que las Apps solicitadas tengan descriptores válidos
            for app_id in app_ids:
                app_key = str(app_id)
                if app_key not in app_descriptors or not app_descriptors[app_key]:
                    logger.warning(f"[GuidedGraph] ⚠️ App {app_id} sin descriptor válido")
                    return False
            
            return True
            
        except Exception as e:
            logger.exception(f"[GuidedGraph] ❌ Error validando recursos: {e}")
            return False