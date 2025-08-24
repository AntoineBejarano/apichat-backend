"""
🔄 Mode Transition Orchestrator: Coordinación de transiciones con WebSocket

Orquestador que coordina las transiciones de modo, maneja confirmaciones
del usuario, y emite eventos en tiempo real a través de WebSocket.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum

from app.services.ai.mode_transition_service import ModeTransitionService
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.agent_router_service import AgentRouterService
from app.services.cache.response_cache_service import ResponseCacheService
from app.services.common.ws_emitter import WSEmitter

logger = logging.getLogger(__name__)


class TransitionEventType(Enum):
    """Tipos de eventos de transición"""
    MODE_CHANGE_REQUESTED = "mode_change_requested"      # Solicitud de cambio
    MODE_CHANGE_CONFIRMED = "mode_change_confirmed"      # Confirmado por usuario
    MODE_CHANGE_REJECTED = "mode_change_rejected"        # Rechazado por usuario
    MODE_CHANGE_EXECUTED = "mode_change_executed"        # Ejecutado automáticamente
    MODE_CHANGE_FAILED = "mode_change_failed"            # Falló la transición
    MODE_ROLLBACK = "mode_rollback"                      # Rollback a modo anterior


class ModeTransitionOrchestrator:
    """
    🎭 Orquestador de transiciones de modo con WebSocket
    
    Funcionalidades:
    - Coordinación de transiciones automáticas y manuales
    - Manejo de confirmaciones del usuario en tiempo real
    - Emisión de eventos WebSocket para UI
    - Fallback inteligente en transiciones fallidas
    - Persistencia de cambios de modo
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.mode_transition_service = factory.get_mode_transition_service()
        self.mode_detection_service = factory.get_mode_detection_service()
        self.agent_router_service = factory.get_agent_router_service()
        self.cache_service = factory.get_response_cache_service()
        self.ws_emitter = factory.get_ws_emitter()
        
        # Estado de transiciones pendientes
        self._pending_transitions = {}  # chat_id -> transition_info
        self._transition_timeouts = {}  # chat_id -> timeout_info
        
        # Configuración
        self._config = {
            "confirmation_timeout": 30,      # Segundos para confirmar transición
            "auto_rollback_on_timeout": True, # Rollback automático si no hay confirmación
            "max_pending_transitions": 5,    # Máximo transiciones pendientes por usuario
            "enable_smart_fallback": True,   # Fallback inteligente
            "log_all_events": True           # Logging completo
        }
        
        logger.info(f"[ModeTransitionOrchestrator] 🚀 Inicializado para usuario {self.user_id}")
    
    async def handle_mode_transition_request(
        self, 
        user_message: str,
        current_mode: str,
        context: Dict[str, Any],
        chat_id: Optional[UUID] = None,
        force_transition: bool = False
    ) -> Dict[str, Any]:
        """
        🎯 Maneja una solicitud de transición de modo
        
        Args:
            user_message: Mensaje del usuario
            current_mode: Modo actual
            context: Contexto actual
            chat_id: ID del chat
            force_transition: Forzar transición sin confirmación
            
        Returns:
            Resultado del manejo de la transición
        """
        try:
            start_time = datetime.utcnow()
            logger.info(f"[ModeTransitionOrchestrator] 🎯 Procesando solicitud de transición en chat {chat_id}")
            
            # 1. Detectar intención de transición
            transition_intent = await self.mode_transition_service.detect_transition_intent(
                user_message, current_mode, context, chat_id
            )
            
            if not transition_intent.get("should_transition") and not force_transition:
                return {
                    "action": "no_transition",
                    "message": transition_intent.get("message", "No se requiere transición"),
                    "current_mode": current_mode,
                    "confidence": transition_intent.get("confidence", 0.0)
                }
            
            # 2. Determinar tipo de acción
            action = self._determine_transition_action(transition_intent, force_transition)
            
            # 3. Ejecutar acción apropiada
            if action == "auto_transition":
                result = await self._execute_auto_transition(
                    current_mode, transition_intent, context, chat_id
                )
            elif action == "request_confirmation":
                result = await self._request_transition_confirmation(
                    current_mode, transition_intent, context, chat_id
                )
            else:
                result = {
                    "action": "no_action",
                    "message": "No se requiere acción",
                    "current_mode": current_mode
                }
            
            # 4. Logging y métricas
            if self._config["log_all_events"]:
                self._log_transition_request(
                    user_message, current_mode, transition_intent, result, start_time, chat_id
                )
            
            logger.info(f"[ModeTransitionOrchestrator] ✅ Solicitud de transición procesada: {result['action']}")
            
            return result
            
        except Exception as e:
            logger.exception(f"[ModeTransitionOrchestrator] ❌ Error procesando solicitud de transición: {e}")
            return self._build_error_response("request_processing_error", str(e), current_mode)
    
    def _determine_transition_action(self, transition_intent: Dict[str, Any], force_transition: bool) -> str:
        """Determina qué acción tomar basada en la intención de transición"""
        try:
            if force_transition:
                return "auto_transition"
            
            confidence_level = transition_intent.get("confidence_level", "low")
            requires_confirmation = transition_intent.get("requires_confirmation", True)
            
            if confidence_level == "high" and not requires_confirmation:
                return "auto_transition"
            elif confidence_level in ["high", "medium"] and requires_confirmation:
                return "request_confirmation"
            else:
                return "no_action"
                
        except Exception as e:
            logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error determinando acción: {e}")
            return "no_action"
    
    async def _execute_auto_transition(
        self, 
        current_mode: str, 
        transition_intent: Dict[str, Any],
        context: Dict[str, Any],
        chat_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Ejecuta transición automática"""
        try:
            suggested_mode = transition_intent.get("suggested_mode", current_mode)
            
            # Ejecutar transición
            transition_result = await self.mode_transition_service.execute_transition(
                current_mode, suggested_mode, context, chat_id
            )
            
            if transition_result["success"]:
                # Emitir evento de transición exitosa
                await self._emit_transition_event(
                    TransitionEventType.MODE_CHANGE_EXECUTED,
                    current_mode, suggested_mode, context, chat_id
                )
                
                return {
                    "action": "auto_transition",
                    "success": True,
                    "from_mode": current_mode,
                    "to_mode": suggested_mode,
                    "message": transition_result["message"],
                    "updated_context": transition_result.get("updated_context", context)
                }
            else:
                # Emitir evento de fallo
                await self._emit_transition_event(
                    TransitionEventType.MODE_CHANGE_FAILED,
                    current_mode, suggested_mode, context, chat_id,
                    error=transition_result.get("reason", "unknown")
                )
                
                return {
                    "action": "auto_transition",
                    "success": False,
                    "from_mode": current_mode,
                    "to_mode": suggested_mode,
                    "error": transition_result.get("reason", "unknown"),
                    "message": transition_result.get("message", "Error en la transición")
                }
                
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error en transición automática: {e}")
            return self._build_error_response("auto_transition_error", str(e), current_mode)
    
    async def _request_transition_confirmation(
        self, 
        current_mode: str, 
        transition_intent: Dict[str, Any],
        context: Dict[str, Any],
        chat_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Solicita confirmación del usuario para la transición"""
        try:
            suggested_mode = transition_intent.get("suggested_mode", current_mode)
            transition_type = transition_intent.get("transition_type", "unknown")
            
            # Verificar límite de transiciones pendientes
            if len(self._pending_transitions) >= self._config["max_pending_transitions"]:
                return {
                    "action": "confirmation_limited",
                    "message": "Demasiadas transiciones pendientes. Intenta más tarde.",
                    "current_mode": current_mode
                }
            
            # Crear información de transición pendiente
            transition_info = {
                "from_mode": current_mode,
                "to_mode": suggested_mode,
                "transition_type": transition_type,
                "context": context,
                "requested_at": datetime.utcnow(),
                "timeout_at": datetime.utcnow().timestamp() + self._config["confirmation_timeout"],
                "confidence": transition_intent.get("confidence", 0.0)
            }
            
            # Almacenar transición pendiente
            if chat_id:
                self._pending_transitions[str(chat_id)] = transition_info
                
                # Configurar timeout
                self._transition_timeouts[str(chat_id)] = {
                    "timeout_at": transition_info["timeout_at"],
                    "auto_rollback": self._config["auto_rollback_on_timeout"]
                }
            
            # Emitir evento de solicitud de confirmación
            await self._emit_transition_event(
                TransitionEventType.MODE_CHANGE_REQUESTED,
                current_mode, suggested_mode, context, chat_id,
                confirmation_required=True,
                timeout_seconds=self._config["confirmation_timeout"]
            )
            
            return {
                "action": "confirmation_requested",
                "from_mode": current_mode,
                "to_mode": suggested_mode,
                "message": transition_intent.get("message", "¿Confirmas el cambio de modo?"),
                "confirmation_required": True,
                "timeout_seconds": self._config["confirmation_timeout"],
                "transition_id": str(chat_id) if chat_id else "global"
            }
            
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error solicitando confirmación: {e}")
            return self._build_error_response("confirmation_request_error", str(e), current_mode)
    
    async def handle_transition_confirmation(
        self, 
        chat_id: UUID, 
        confirmed: bool, 
        user_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ✅ Maneja la confirmación del usuario para una transición
        
        Args:
            chat_id: ID del chat
            confirmed: Si el usuario confirmó la transición
            user_message: Mensaje adicional del usuario
            
        Returns:
            Resultado del manejo de la confirmación
        """
        try:
            chat_id_str = str(chat_id)
            
            if chat_id_str not in self._pending_transitions:
                return {
                    "action": "no_pending_transition",
                    "message": "No hay transición pendiente para confirmar",
                    "success": False
                }
            
            transition_info = self._pending_transitions[chat_id_str]
            from_mode = transition_info["from_mode"]
            to_mode = transition_info["to_mode"]
            context = transition_info["context"]
            
            if confirmed:
                # Ejecutar transición confirmada
                transition_result = await self.mode_transition_service.execute_transition(
                    from_mode, to_mode, context, chat_id, user_confirmation=True
                )
                
                if transition_result["success"]:
                    # Emitir evento de confirmación
                    await self._emit_transition_event(
                        TransitionEventType.MODE_CHANGE_CONFIRMED,
                        from_mode, to_mode, context, chat_id
                    )
                    
                    result = {
                        "action": "transition_confirmed",
                        "success": True,
                        "from_mode": from_mode,
                        "to_mode": to_mode,
                        "message": "Transición confirmada y ejecutada exitosamente",
                        "updated_context": transition_result.get("updated_context", context)
                    }
                else:
                    # Emitir evento de fallo
                    await self._emit_transition_event(
                        TransitionEventType.MODE_CHANGE_FAILED,
                        from_mode, to_mode, context, chat_id,
                        error=transition_result.get("reason", "unknown")
                    )
                    
                    result = {
                        "action": "transition_confirmed",
                        "success": False,
                        "from_mode": from_mode,
                        "to_mode": to_mode,
                        "error": transition_result.get("reason", "unknown"),
                        "message": "Error ejecutando transición confirmada"
                    }
            else:
                # Emitir evento de rechazo
                await self._emit_transition_event(
                    TransitionEventType.MODE_CHANGE_REJECTED,
                    from_mode, to_mode, context, chat_id
                )
                
                result = {
                    "action": "transition_rejected",
                    "success": True,
                    "from_mode": from_mode,
                    "to_mode": to_mode,
                    "message": "Transición rechazada por el usuario",
                    "current_mode": from_mode
                }
            
            # Limpiar transición pendiente
            self._cleanup_pending_transition(chat_id_str)
            
            logger.info(f"[ModeTransitionOrchestrator] ✅ Confirmación de transición procesada: {result['action']}")
            
            return result
            
        except Exception as e:
            logger.exception(f"[ModeTransitionOrchestrator] ❌ Error procesando confirmación: {e}")
            return self._build_error_response("confirmation_processing_error", str(e), "unknown")
    
    async def handle_transition_timeout(self, chat_id: UUID) -> Dict[str, Any]:
        """⏰ Maneja el timeout de una transición pendiente"""
        try:
            chat_id_str = str(chat_id)
            
            if chat_id_str not in self._pending_transitions:
                return {
                    "action": "no_timeout",
                    "message": "No hay transición pendiente para timeout",
                    "success": False
                }
            
            transition_info = self._pending_transitions[chat_id_str]
            from_mode = transition_info["from_mode"]
            to_mode = transition_info["to_mode"]
            context = transition_info["context"]
            
            # Emitir evento de timeout
            await self._emit_transition_event(
                TransitionEventType.MODE_CHANGE_FAILED,
                from_mode, to_mode, context, chat_id,
                error="timeout"
            )
            
            # Rollback automático si está habilitado
            if self._config["auto_rollback_on_timeout"]:
                rollback_result = await self._perform_auto_rollback(
                    from_mode, to_mode, context, chat_id
                )
                
                result = {
                    "action": "timeout_with_rollback",
                    "success": rollback_result["success"],
                    "from_mode": from_mode,
                    "to_mode": rollback_result.get("rollback_mode", from_mode),
                    "message": "Transición expiró. Rollback automático realizado.",
                    "rollback_result": rollback_result
                }
            else:
                result = {
                    "action": "timeout_no_rollback",
                    "success": False,
                    "from_mode": from_mode,
                    "to_mode": to_mode,
                    "message": "Transición expiró sin confirmación del usuario"
                }
            
            # Limpiar transición pendiente
            self._cleanup_pending_transition(chat_id_str)
            
            logger.info(f"[ModeTransitionOrchestrator] ⏰ Timeout de transición manejado: {result['action']}")
            
            return result
            
        except Exception as e:
            logger.exception(f"[ModeTransitionOrchestrator] ❌ Error manejando timeout: {e}")
            return self._build_error_response("timeout_handling_error", str(e), "unknown")
    
    async def _perform_auto_rollback(
        self, 
        from_mode: str, 
        attempted_mode: str, 
        context: Dict[str, Any],
        chat_id: UUID
    ) -> Dict[str, Any]:
        """Realiza rollback automático en caso de timeout"""
        try:
            # Intentar rollback al modo anterior si es posible
            # Por ahora, mantener el modo actual
            rollback_mode = from_mode
            
            # Emitir evento de rollback
            await self._emit_transition_event(
                TransitionEventType.MODE_ROLLBACK,
                attempted_mode, rollback_mode, context, chat_id
            )
            
            return {
                "success": True,
                "rollback_mode": rollback_mode,
                "message": "Rollback automático realizado"
            }
            
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error en rollback automático: {e}")
            return {
                "success": False,
                "rollback_mode": from_mode,
                "error": str(e)
            }
    
    async def _emit_transition_event(
        self, 
        event_type: TransitionEventType,
        from_mode: str, 
        to_mode: str,
        context: Dict[str, Any],
        chat_id: Optional[UUID],
        **extra_data
    ):
        """Emite evento de transición a través de WebSocket"""
        try:
            if not self.ws_emitter:
                logger.warning("[ModeTransitionOrchestrator] ⚠️ WSEmitter no disponible")
                return
            
            event_data = {
                "event_type": event_type.value,
                "user_id": str(self.user_id),
                "chat_id": str(chat_id) if chat_id else None,
                "from_mode": from_mode,
                "to_mode": to_mode,
                "timestamp": datetime.utcnow().isoformat(),
                "context_summary": self._summarize_context(context),
                **extra_data
            }
            
            # Emitir a usuario específico
            await self.ws_emitter.emit_to_user(
                self.user_id, 
                "mode_transition_event", 
                event_data
            )
            
            # Emitir a chat específico si existe
            if chat_id:
                await self.ws_emitter.emit_to_chat(
                    chat_id, 
                    "mode_transition_event", 
                    event_data
                )
            
            logger.debug(f"[ModeTransitionOrchestrator] 📡 Evento emitido: {event_type.value}")
            
        except Exception as e:
            logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error emitiendo evento: {e}")
    
    def _summarize_context(self, context: Dict[str, Any]) -> str:
        """Resume el contexto para el evento"""
        try:
            summary_parts = []
            
            if context.get("db_ids"):
                summary_parts.append(f"DBs: {len(context['db_ids'])}")
            
            if context.get("app_ids"):
                summary_parts.append(f"Apps: {len(context['app_ids'])}")
            
            if context.get("mode"):
                summary_parts.append(f"Mode: {context['mode']}")
            
            return " | ".join(summary_parts) if summary_parts else "Sin contexto específico"
            
        except Exception as e:
            logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error resumiendo contexto: {e}")
            return "Error en contexto"
    
    def _cleanup_pending_transition(self, chat_id_str: str):
        """Limpia una transición pendiente"""
        try:
            if chat_id_str in self._pending_transitions:
                del self._pending_transitions[chat_id_str]
            
            if chat_id_str in self._transition_timeouts:
                del self._transition_timeouts[chat_id_str]
                
        except Exception as e:
            logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error limpiando transición: {e}")
    
    def _build_error_response(self, error_type: str, error_message: str, current_mode: str) -> Dict[str, Any]:
        """Construye respuesta de error estandarizada"""
        return {
            "action": "error",
            "success": False,
            "error_type": error_type,
            "error_message": error_message,
            "current_mode": current_mode,
            "message": f"Error en transición: {error_message}"
        }
    
    def _log_transition_request(
        self, 
        user_message: str, 
        current_mode: str, 
        transition_intent: Dict[str, Any],
        result: Dict[str, Any],
        start_time: datetime,
        chat_id: Optional[UUID]
    ):
        """Log de solicitud de transición"""
        try:
            log_entry = {
                "timestamp": start_time.isoformat(),
                "user_message": user_message[:100] + "..." if len(user_message) > 100 else user_message,
                "current_mode": current_mode,
                "detected_transition": transition_intent.get("transition_type"),
                "confidence": transition_intent.get("confidence", 0.0),
                "action_taken": result.get("action", "unknown"),
                "chat_id": str(chat_id) if chat_id else None
            }
            
            # TODO: Implementar logging persistente
            
        except Exception as e:
            logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error en logging: {e}")
    
    async def get_pending_transitions(self) -> List[Dict[str, Any]]:
        """📋 Obtiene transiciones pendientes del usuario"""
        try:
            pending = []
            
            for chat_id_str, transition_info in self._pending_transitions.items():
                pending.append({
                    "chat_id": chat_id_str,
                    "from_mode": transition_info["from_mode"],
                    "to_mode": transition_info["to_mode"],
                    "requested_at": transition_info["requested_at"].isoformat(),
                    "timeout_at": transition_info["timeout_at"],
                    "confidence": transition_info["confidence"]
                })
            
            return pending
            
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error obteniendo transiciones pendientes: {e}")
            return []
    
    async def cleanup_expired_transitions(self) -> int:
        """🧹 Limpia transiciones expiradas"""
        try:
            current_time = datetime.utcnow().timestamp()
            expired_chats = []
            
            for chat_id_str, timeout_info in self._transition_timeouts.items():
                if current_time > timeout_info["timeout_at"]:
                    expired_chats.append(chat_id_str)
            
            # Manejar timeouts
            for chat_id_str in expired_chats:
                try:
                    chat_id = UUID(chat_id_str)
                    await self.handle_transition_timeout(chat_id)
                except Exception as e:
                    logger.warning(f"[ModeTransitionOrchestrator] ⚠️ Error manejando timeout de {chat_id_str}: {e}")
            
            return len(expired_chats)
            
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error limpiando transiciones expiradas: {e}")
            return 0
    
    async def get_orchestrator_stats(self) -> Dict[str, Any]:
        """📊 Obtiene estadísticas del orquestador"""
        try:
            return {
                "user_id": str(self.user_id),
                "pending_transitions": len(self._pending_transitions),
                "transition_timeouts": len(self._transition_timeouts),
                "config": self._config.copy(),
                "pending_details": await self.get_pending_transitions()
            }
        except Exception as e:
            logger.error(f"[ModeTransitionOrchestrator] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}


# Función helper para dependency injection
def get_mode_transition_orchestrator(factory) -> ModeTransitionOrchestrator:
    """Obtiene una instancia del Mode Transition Orchestrator"""
    return ModeTransitionOrchestrator(factory)
