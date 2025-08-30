from typing import Dict, Any, Optional, List, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph, END
from app.core.service_factory import ServiceFactory
from app.schemas.plan_schema import UserPlanOut
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.services.context.intent_classifier_service import IntentType
from app.services.management.telemetry_service import EventType, TelemetryContextManager

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
    plan: Optional[UserPlanOut]
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
                
                # 🔧 FIX: Validar tipos de db_ids y app_ids para evitar mezclas UUID/string
                if db_ids and not all(isinstance(db_id, (str, UUID)) for db_id in db_ids):
                    logger.warning(f"[GuidedGraph] ⚠️ db_ids contiene tipos mixtos: {[type(db_id) for db_id in db_ids]}")
                    # Normalizar a strings para consistencia
                    db_ids = [str(db_id) for db_id in db_ids]
                
                if app_ids and not all(isinstance(app_id, (str, UUID)) for app_id in app_ids):
                    logger.warning(f"[GuidedGraph] ⚠️ app_ids contiene tipos mixtos: {[type(app_id) for app_id in app_ids]}")
                    # Normalizar a strings para consistencia
                    app_ids = [str(app_id) for app_id in app_ids]
                
                # Si no requiere recursos, es chat normal
                if not requires_resources or intent == IntentType.CHAT:
                    logger.info("[GuidedGraph] 💬 Modo chat normal - sin recursos específicos")
                    chat_response = await self._handle_chat_response(state)
                    return {
                        **state,
                        "assistant_response": chat_response,
                        "db_ids": db_ids,  # 🔧 Usar versiones normalizadas
                        "app_ids": app_ids
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
                return {
                    **state,
                    "db_ids": db_ids,  # 🔧 Usar versiones normalizadas
                    "app_ids": app_ids
                }
                
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
                    
                    # 🔧 FIX: Normalizar db_ids a strings para consistencia con compact_schemas
                    # compact_schemas usa string keys, así que db_ids deben ser strings también
                    normalized_db_ids = [str(db_id) for db_id in db_ids]
                    
                    # 🔧 FIX: Monitorear si ya tenemos schemas del orchestrator para evitar duplicación
                    existing_schemas = state.get("compact_schemas", {})
                    if existing_schemas:
                        logger.info(f"[GuidedGraph] 📋 Schemas ya disponibles del orchestrator: {len(existing_schemas)} DBs")
                        # Calcular tiempo ahorrado
                        time_saved = time.time() - start_time
                        logger.info(f"[GuidedGraph] ⏱️ Tiempo ahorrado por schemas pre-existentes: {time_saved:.3f}s")
                    
                    ctx.metadata.update({
                        "db_count": len(normalized_db_ids),
                        "app_count": len(app_ids),
                        "schemas_pre_existing": len(existing_schemas)
                    })
                    
                    # Warm-up DB schemas
                    final_compact_schemas = existing_schemas
                    final_cache_status = state.get("cache_status", {})
                    
                    if normalized_db_ids:
                        logger.info(f"[GuidedGraph] 🔥 Warming up {len(normalized_db_ids)} DB schemas")
                        
                        # Si no vienen del orchestrator, usar el servicio directamente
                        if not final_compact_schemas:
                            logger.info("[GuidedGraph] 🔄 No hay schemas pre-existentes, llamando al orchestrator...")
                            # 🔧 FIX: Convertir strings de vuelta a UUIDs para el servicio
                            db_ids_uuid = [UUID(db_id_str) for db_id_str in normalized_db_ids]
                            orchestrator = self.factory.get_orchestrator_service()
                            db_results = await orchestrator._load_database_schemas_async(db_ids_uuid)
                            
                            final_compact_schemas = db_results.get("compact_schemas", {})
                            final_cache_status = db_results.get("cache_status", {})
                            
                            logger.info(f"[GuidedGraph] ✅ Schemas cargados del orchestrator: {len(final_compact_schemas)} DBs")
                        else:
                            logger.info(f"[GuidedGraph] ✅ Usando schemas pre-existentes: {len(final_compact_schemas)} DBs")
                        
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
                    
                    # 🔧 FIX: Logging detallado para monitorear duplicación
                    if existing_schemas:
                        logger.info(f"[GuidedGraph] 📊 Resumen: {len(existing_schemas)} schemas pre-existentes, {cache_hits} hits, {cache_misses} misses ({processing_time:.3f}s)")
                    else:
                        logger.info(f"[GuidedGraph] 📊 Resumen: {cache_hits} hits, {cache_misses} misses, {len(app_descriptors)} apps ({processing_time:.3f}s)")
                    
                    # Actualizar telemetría con resultados
                    ctx.metadata.update({
                        "cache_hits": cache_hits,
                        "cache_misses": cache_misses,
                        "apps_loaded": len(app_descriptors),
                        "total_processing_time_s": processing_time,
                        "schemas_pre_existing": len(existing_schemas)
                    })
                    
                    return {
                        **state,
                        "db_ids": normalized_db_ids,  # 🔧 Usar versiones normalizadas
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
                            # 🔒 COMPATIBILIDAD: Verificar que sea string antes de usar .strip()
                            if compact_schema:
                                if isinstance(compact_schema, str) and compact_schema.strip():
                                    schema_parts.append(f"-- DATABASE {db_id} --")
                                    schema_parts.append(compact_schema)
                                    schema_parts.append("")
                                elif isinstance(compact_schema, dict) and compact_schema.get("compact"):
                                    # Si es un dict, extraer el campo compact
                                    compact_value = compact_schema.get("compact")
                                    if isinstance(compact_value, str) and compact_value.strip():
                                        schema_parts.append(f"-- DATABASE {db_id} --")
                                        schema_parts.append(compact_value)
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
                            # 🔒 COMPATIBILIDAD: Verificar que sea string antes de usar .strip()
                            if descriptor:
                                if isinstance(descriptor, str) and descriptor.strip():
                                    app_parts.append(f"-- APP {app_id} --")
                                    app_parts.append(descriptor)
                                    app_parts.append("")
                                elif isinstance(descriptor, dict) and descriptor.get("descriptor"):
                                    # Si es un dict, extraer el campo descriptor
                                    desc_value = descriptor.get("descriptor")
                                    if isinstance(desc_value, str) and desc_value.strip():
                                        app_parts.append(f"-- APP {app_id} --")
                                        app_parts.append(desc_value)
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
                        plan = UserPlanOut.model_validate(result)
                        
                        # 🔧 NUEVO: Validar plan antes de la ejecución
                        validation_result = self._validate_plan_for_chat_safety(plan)
                        if not validation_result["is_safe"]:
                            logger.warning(f"[GuidedGraph] ⚠️ Plan no seguro para chat: {validation_result['issues']}")
                            # 🔧 NUEVO: Intentar corregir automáticamente o rechazar
                            if validation_result["can_auto_fix"]:
                                logger.info("[GuidedGraph] 🔧 Aplicando correcciones automáticas al plan")
                                plan = self._apply_chat_safety_fixes(plan, validation_result["issues"])
                            else:
                                logger.error("[GuidedGraph] ❌ Plan rechazado por problemas de seguridad para chat")
                                return {
                                    **state,
                                    "error": "El plan generado no es seguro para chat. Reintentando...",
                                    "assistant_response": "Disculpa, el plan generado no es apropiado para chat. Déjame intentarlo de nuevo."
                                }
                        
                        # 🔧 NUEVO: Validar placeholders también
                        placeholder_validation = self._validate_plan_placeholders(plan, result.get("assistant_response", ""))
                        if not placeholder_validation["is_valid"]:
                            logger.warning(f"[GuidedGraph] ⚠️ Plan con placeholders inválidos: {placeholder_validation['issues']}")
                            if placeholder_validation["can_auto_fix"]:
                                logger.info("[GuidedGraph] 🔧 Aplicando correcciones automáticas a placeholders")
                                plan = self._apply_plan_fixes(plan, placeholder_validation["issues"])
                            else:
                                logger.error("[GuidedGraph] ❌ Plan rechazado por placeholders inválidos")
                                return {
                                    **state,
                                    "error": "El plan generado contiene variables no válidas. Reintentando...",
                                    "assistant_response": "Disculpa, hubo un problema con el plan. Déjame intentarlo de nuevo."
                                }
                        
                        ctx.metadata.update({
                            "result_type": "plan",
                            "action_count": len(plan.actions),
                            "placeholders_validated": True
                        })
                        logger.info(f"[GuidedGraph] ✅ Plan generado y validado: {len(plan.actions)} acciones")
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
                available_mcp_tools=None,
                history=state.get("history", []),
                db_ids=None,
                use_enriched_context=False,
                app_descriptors_compact=None
            )
            
            # Extraer respuesta del resultado
            if isinstance(result, dict):
                return result.get("assistant_response", "¿En qué más puedo ayudarte?")
            else:
                return str(result) if result else "¿En qué más puedo ayudarte?"
            
        except Exception as e:
            logger.exception("[GuidedGraph] ❌ Error en respuesta de chat")
            return "Disculpa, ha ocurrido un error. ¿Podrías intentar de nuevo?"

    # ──────────────────────────────────────────────────────
    #   NUEVO: Validación y corrección de placeholders del plan
    # ──────────────────────────────────────────────────────
    def _validate_plan_placeholders(self, plan: UserPlanOut, template: str) -> Dict[str, Any]:
        """
        Valida que todos los placeholders en el template correspondan a variables
        generadas por las acciones del plan.
        """
        if not template:
            return {"is_valid": True, "issues": [], "can_auto_fix": True}

        import re
        
        # Extraer todos los placeholders del template
        placeholders = re.findall(r'\{\{([^}]+)\}\}', template)
        logger.info(f"[GuidedGraph] 🔍 Validando {len(placeholders)} placeholders del plan")
        
        # Obtener variables disponibles del plan
        available_vars = set()
        for action in plan.actions:
            if action.store_as:
                available_vars.add(action.store_as)
                # También incluir variantes automáticas
                available_vars.add(f"{action.store_as}_list")
                available_vars.add(f"{action.store_as}_pretty")
                available_vars.add(f"{action.store_as}_formatted")
        
        issues = []
        can_auto_fix = True
        
        for placeholder in placeholders:
            placeholder = placeholder.strip()
            
            if placeholder in available_vars:
                logger.debug(f"[GuidedGraph] ✅ Placeholder '{placeholder}' válido")
                continue
            
            # Si termina en _formatted, verificar si existe la base
            if placeholder.endswith('_formatted'):
                base_var = placeholder[:-10]
                if base_var in available_vars:
                    logger.debug(f"[GuidedGraph] ✅ Placeholder '{placeholder}' será auto-generado para '{base_var}'")
                    continue
                else:
                    issues.append(f"'{placeholder}' requiere '{base_var}' que no está en store_as")
                    can_auto_fix = False
            else:
                issues.append(f"'{placeholder}' no está disponible en store_as")
                can_auto_fix = False
        
        is_valid = len(issues) == 0
        
        if issues:
            logger.warning(f"[GuidedGraph] ⚠️ Placeholders inválidos detectados: {issues}")
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "can_auto_fix": can_auto_fix,
            "available_vars": list(available_vars),
            "placeholders_checked": placeholders
        }

    def _apply_plan_fixes(self, plan: UserPlanOut, issues: List[str]) -> UserPlanOut:
        """
        Aplica correcciones automáticas al plan para resolver placeholders inválidos.
        Por ahora, solo registra los problemas para debugging.
        """
        logger.info(f"[GuidedGraph] 🔧 Aplicando correcciones automáticas para {len(issues)} issues")
        
        # 🔧 FUTURO: Aquí se podrían implementar correcciones automáticas
        # Por ejemplo, agregar acciones de formateo faltantes
        
        for issue in issues:
            logger.info(f"[GuidedGraph] 🔧 Issue a corregir: {issue}")
        
        return plan

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

    def _validate_plan_for_chat_safety(self, plan: UserPlanOut) -> Dict[str, Any]:
        """
        Valida que el plan sea seguro para chat antes de ejecutarlo.
        Verifica que no genere respuestas inapropiadas o volcados masivos de datos.
        """
        issues = []
        warnings = []
        can_auto_fix = True
        
        logger.info(f"[GuidedGraph] 🔒 Validando seguridad del plan para chat: {len(plan.actions)} acciones")
        
        for action in plan.actions:
            if action.type == "db_query":
                # Validar SQL
                sql = action.sql.upper() if action.sql else ""
                
                # 🔒 CRÍTICO: Bloquear SELECT * 
                if "SELECT *" in sql:
                    issues.append("SELECT * detectado - usar columnas específicas")
                    can_auto_fix = False
                
                # ⚠️ ADVERTENCIA: Verificar LIMIT
                if "LIMIT" not in sql:
                    warnings.append("Agregar LIMIT a query para evitar volcados masivos")
                    can_auto_fix = True  # Se puede corregir automáticamente
                
                # 🔒 CRÍTICO: Verificar store_as
                if not action.store_as:
                    issues.append("db_query sin store_as - no se puede formatear")
                    can_auto_fix = False
                
                # ⚠️ ADVERTENCIA: Verificar que no sea una query masiva
                if "WHERE" not in sql and "LIMIT" not in sql:
                    warnings.append("Query sin filtros ni límites - riesgo de volcado masivo")
                    can_auto_fix = True
        
        # Validar assistant_response
        if "{{" in plan.assistant_response and "}}" in plan.assistant_response:
            # Verificar que todos los placeholders tengan acciones correspondientes
            import re
            placeholders = re.findall(r'\{\{(\w+)\}\}', plan.assistant_response)
            for placeholder in placeholders:
                if not any(action.store_as == placeholder for action in plan.actions):
                    issues.append(f"Placeholder {{{{{placeholder}}}}} sin acción correspondiente")
                    can_auto_fix = False
        
        # 🔒 CRÍTICO: Verificar que no haya respuestas directas con datos crudos
        if any(keyword in plan.assistant_response.lower() for keyword in ["[(30, 'ayuso'", "[(1,", "[(2,", "[(3,"]):
            issues.append("Respuesta contiene datos crudos de base de datos")
            can_auto_fix = False
        
        is_safe = len(issues) == 0
        
        if issues:
            logger.warning(f"[GuidedGraph] ⚠️ Plan no seguro para chat: {issues}")
        if warnings:
            logger.info(f"[GuidedGraph] 💡 Advertencias del plan: {warnings}")
        
        return {
            "is_safe": is_safe,
            "issues": issues,
            "warnings": warnings,
            "can_auto_fix": can_auto_fix,
            "action_count": len(plan.actions)
        }

    def _apply_chat_safety_fixes(self, plan: UserPlanOut, issues: List[str]) -> UserPlanOut:
        """
        Aplica correcciones automáticas al plan para resolver problemas de seguridad para chat.
        """
        logger.info(f"[GuidedGraph] 🔧 Aplicando correcciones de seguridad para chat: {len(issues)} issues")
        
        for issue in issues:
            logger.info(f"[GuidedGraph] 🔧 Issue a corregir: {issue}")
            
            # 🔧 CORRECCIÓN: Agregar LIMIT a queries sin límite
            if "LIMIT" in issue.lower():
                for action in plan.actions:
                    if action.type == "db_query" and action.sql and "LIMIT" not in action.sql.upper():
                        # Agregar LIMIT 20 al final de la query
                        if action.sql.strip().endswith(';'):
                            action.sql = action.sql[:-1] + " LIMIT 20;"
                        else:
                            action.sql = action.sql + " LIMIT 20"
                        logger.info(f"[GuidedGraph] 🔧 Agregado LIMIT 20 a query: {action.sql}")
        
        return plan