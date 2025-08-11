"""
🎯 FASE 11: Servicio de manejo de errores con remediación automática.

Este servicio detecta errores, los categoriza y proporciona acciones de remediación
automática para que el usuario siempre sepa qué hacer a continuación.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta

from app.common.errors import (
    UserFacingError, 
    ErrorRegistry, 
    ErrorCategory, 
    ErrorSeverity,
    SuggestedAction,
    create_custom_error,
    get_prioritized_actions
)
from app.common.events import ErrorUserFacingEvent
from app.common.ws_emitter import WebSocketEmitter

logger = logging.getLogger(__name__)


class ErrorHandlerService:
    """
    Servicio centralizado para manejo de errores con remediación automática.
    
    Detecta errores, los categoriza y proporciona acciones sugeridas
    para que el usuario siempre tenga opciones de continuación.
    """
    
    def __init__(self, ws_emitter: WebSocketEmitter):
        self.ws_emitter = ws_emitter
        self.error_history: Dict[str, List[Dict[str, Any]]] = {}
        self.retry_counters: Dict[str, int] = {}
        self.max_retries = 3
        
    async def handle_error(
        self,
        chat_id: str,
        error: Union[Exception, UserFacingError],
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> UserFacingError:
        """
        Maneja un error y retorna un UserFacingError con acciones sugeridas.
        
        Args:
            chat_id: ID del chat donde ocurrió el error
            error: Excepción o error predefinido
            context: Contexto adicional del error
            user_id: ID del usuario afectado
            
        Returns:
            UserFacingError con acciones de remediación
        """
        try:
            # Si ya es un UserFacingError, usarlo directamente
            if isinstance(error, UserFacingError):
                user_facing_error = error
            else:
                # Categorizar la excepción y crear UserFacingError
                user_facing_error = self._categorize_exception(error, context)
            
            # Registrar el error para análisis (antes de enriquecer)
            self._log_error(user_facing_error, chat_id, user_id)
            
            # Enriquecer con contexto del chat
            user_facing_error = self._enrich_error_context(
                user_facing_error, chat_id, user_id, context
            )
            
            # Aplicar lógica de remediación automática
            user_facing_error = await self._apply_automatic_remediation(
                user_facing_error, chat_id
            )
            
            # Emitir evento WebSocket
            await self._emit_error_event(user_facing_error, chat_id)
            
            logger.info(f"[ErrorHandlerService] Error manejado: {user_facing_error.code} para chat {chat_id}")
            return user_facing_error
            
        except Exception as e:
            logger.error(f"[ErrorHandlerService] Error manejando error: {e}")
            # Fallback a error genérico
            return self._create_fallback_error(str(e))
    
    def _categorize_exception(
        self, 
        exception: Exception, 
        context: Optional[Dict[str, Any]]
    ) -> UserFacingError:
        """
        Categoriza una excepción y retorna el UserFacingError apropiado.
        """
        error_type = type(exception).__name__
        error_message = str(exception)
        
        # 🎯 FASE 11: Manejo específico de asyncio.TimeoutError
        if isinstance(exception, asyncio.TimeoutError):
            # Determinar el contexto del timeout basado en el contexto proporcionado
            if context and context.get("operation") == "minimal_context":
                return ErrorRegistry.LLM_TIMEOUT
            elif context and ("database" in str(context).lower() or "db" in str(context).lower()):
                return ErrorRegistry.DATABASE_QUERY_TIMEOUT
            else:
                return ErrorRegistry.EXECUTION_ERROR
        
        # Mapeo de excepciones comunes a errores predefinidos
        if "timeout" in error_message.lower() or "timed out" in error_message.lower():
            if "llm" in error_message.lower() or "openai" in error_message.lower():
                return ErrorRegistry.LLM_TIMEOUT
            elif "database" in error_message.lower() or "db" in error_message.lower():
                return ErrorRegistry.DATABASE_QUERY_TIMEOUT
            else:
                return ErrorRegistry.EXECUTION_ERROR
        
        elif "permission" in error_message.lower() or "access denied" in error_message.lower():
            return ErrorRegistry.INSUFFICIENT_PERMISSIONS
        
        elif "connection" in error_message.lower() or "network" in error_message.lower():
            return ErrorRegistry.NETWORK_ERROR
        
        elif "not found" in error_message.lower() or "does not exist" in error_message.lower():
            return ErrorRegistry.RESOURCE_NOT_FOUND
        
        elif "validation" in error_message.lower() or "invalid" in error_message.lower():
            return ErrorRegistry.VALIDATION_ERROR
        
        elif "rate limit" in error_message.lower() or "too many requests" in error_message.lower():
            return ErrorRegistry.LLM_RATE_LIMIT
        
        elif "cache" in error_message.lower() or "stale" in error_message.lower():
            return ErrorRegistry.CACHE_INCONSISTENT
        
        else:
            # Error genérico de ejecución
            return create_custom_error(
                code="EXECUTION_ERROR",
                category=ErrorCategory.EXECUTION_ERROR,
                severity=ErrorSeverity.MEDIUM,
                human_message=f"Ocurrió un error durante la ejecución: {error_message}",
                suggested_actions=[
                    {
                        "label": "Reintentar operación",
                        "action": "retry_operation",
                        "description": "Intentar ejecutar nuevamente",
                        "priority": 1
                    },
                    {
                        "label": "Verificar configuración",
                        "action": "check_configuration",
                        "description": "Revisar la configuración actual",
                        "priority": 2
                    },
                    {
                        "label": "Contactar soporte",
                        "action": "contact_support",
                        "description": "Reportar el problema al equipo técnico",
                        "priority": 3
                    }
                ],
                technical_details=f"Tipo: {error_type}, Mensaje: {error_message}",
                context=context
            )
    
    def _enrich_error_context(
        self,
        error: UserFacingError,
        chat_id: str,
        user_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> UserFacingError:
        """
        Enriquece el error con contexto adicional del chat y usuario.
        """
        # Crear contexto enriquecido
        enriched_context = {
            "chat_id": chat_id,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "error_count": self._get_error_count_for_chat(chat_id),
            "retry_count": self.retry_counters.get(chat_id, 0)
        }
        
        if context:
            enriched_context.update(context)
        
        # Crear nueva instancia con contexto enriquecido
        error_dict = error.model_dump()
        error_dict["context"] = enriched_context
        return UserFacingError(**error_dict)
    
    async def _apply_automatic_remediation(
        self,
        error: UserFacingError,
        chat_id: str
    ) -> UserFacingError:
        """
        Aplica remediación automática basada en el historial de errores.
        """
        error_count = self._get_error_count_for_chat(chat_id)
        retry_count = self.retry_counters.get(chat_id, 0)
        
        # Si es el primer error, mantener acciones originales
        if error_count == 1:
            return error
        
        # Si hay múltiples errores, ajustar acciones
        if error_count > 1:
            # Añadir acción de diagnóstico
            diagnostic_action = SuggestedAction(
                label="Diagnosticar problema",
                action="diagnose_issue",
                description="Analizar la causa raíz del problema",
                priority=1
            )
            
            # Añadir acción de modo seguro
            safe_mode_action = SuggestedAction(
                label="Cambiar a modo seguro",
                action="switch_to_safe_mode",
                description="Usar configuración más conservadora",
                priority=2
            )
            
            # Crear nueva lista de acciones con las prioritarias
            new_actions = [diagnostic_action, safe_mode_action]
            
            # Añadir acciones originales si no están duplicadas
            for action in error.suggested_actions:
                if not any(new_action.action == action.action for new_action in new_actions):
                    new_actions.append(action)
            
            error_dict = error.model_dump()
            error_dict["suggested_actions"] = new_actions[:3]  # Máximo 3 acciones
            return UserFacingError(**error_dict)
        
        return error
    
    def _log_error(
        self,
        error: UserFacingError,
        chat_id: str,
        user_id: Optional[str]
    ) -> None:
        """
        Registra el error para análisis y seguimiento.
        """
        if chat_id not in self.error_history:
            self.error_history[chat_id] = []
        
        error_record = {
            "timestamp": datetime.utcnow(),
            "code": error.code,
            "category": error.category.value,
            "severity": error.severity.value,
            "user_id": user_id,
            "context": error.context
        }
        
        self.error_history[chat_id].append(error_record)
        
        # Mantener solo los últimos 10 errores por chat
        if len(self.error_history[chat_id]) > 10:
            self.error_history[chat_id] = self.error_history[chat_id][-10:]
    
    async def _emit_error_event(
        self,
        error: UserFacingError,
        chat_id: str
    ) -> None:
        """
        Emite el evento de error al cliente via WebSocket.
        """
        try:
            # Convertir acciones sugeridas a formato de evento (solo las etiquetas)
            actions = []
            for action in get_prioritized_actions(error, max_actions=3):
                actions.append(action.label)
            
            # Crear evento de error
            error_event = ErrorUserFacingEvent(
                code=error.code,
                human_message=error.human_message,
                suggested_actions=actions,
                technical_details=error.technical_details,
                retry_after=error.retry_after
            )
            
            # Emitir evento
            await self.ws_emitter.emit_error_user_facing(
                chat_id=chat_id,
                error_event=error_event
            )
            
        except Exception as e:
            logger.error(f"[ErrorHandlerService] Error emitiendo evento: {e}")
    
    def _get_error_count_for_chat(self, chat_id: str) -> int:
        """Obtiene el número de errores para un chat específico."""
        return len(self.error_history.get(chat_id, []))
    
    def _create_fallback_error(self, message: str) -> UserFacingError:
        """Crea un error de fallback cuando falla el manejo de errores."""
        return create_custom_error(
            code="ERROR_HANDLER_FAILURE",
            category=ErrorCategory.EXECUTION_ERROR,
            severity=ErrorSeverity.HIGH,
            human_message="Ocurrió un error inesperado en el sistema.",
            suggested_actions=[
                {
                    "label": "Reintentar operación",
                    "action": "retry_operation",
                    "description": "Intentar la operación nuevamente",
                    "priority": 1
                },
                {
                    "label": "Contactar soporte",
                    "action": "contact_support",
                    "description": "Reportar el problema al equipo técnico",
                    "priority": 2
                }
            ],
            technical_details=f"Error en manejador: {message}"
        )
    
    async def handle_retry_action(
        self,
        chat_id: str,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Maneja una acción de reintento solicitada por el usuario.
        
        Args:
            chat_id: ID del chat
            action: Acción a ejecutar
            context: Contexto adicional
            
        Returns:
            Dict con resultado de la acción
        """
        try:
            # Incrementar contador de reintentos
            if chat_id not in self.retry_counters:
                self.retry_counters[chat_id] = 0
            self.retry_counters[chat_id] += 1
            
            retry_count = self.retry_counters[chat_id]
            
            if retry_count > self.max_retries:
                # Máximo de reintentos alcanzado
                return {
                    "success": False,
                    "message": "Se ha alcanzado el máximo de reintentos permitidos.",
                    "suggested_actions": [
                        {
                            "label": "Contactar soporte",
                            "action": "contact_support",
                            "description": "El problema persiste, contactar al equipo técnico"
                        },
                        {
                            "label": "Usar modo alternativo",
                            "action": "use_alternative_mode",
                            "description": "Cambiar a un modo de operación diferente"
                        }
                    ]
                }
            
            # Ejecutar acción específica
            if action == "retry_operation":
                return await self._execute_retry_operation(chat_id, context)
            elif action == "switch_to_fast_mode":
                return await self._execute_switch_to_fast_mode(chat_id, context)
            elif action == "use_safe_mode":
                return await self._execute_use_safe_mode(chat_id, context)
            elif action == "diagnose_issue":
                return await self._execute_diagnose_issue(chat_id, context)
            else:
                return {
                    "success": False,
                    "message": f"Acción '{action}' no reconocida.",
                    "suggested_actions": [
                        {
                            "label": "Ver acciones disponibles",
                            "action": "show_available_actions",
                            "description": "Mostrar todas las acciones disponibles"
                        }
                    ]
                }
                
        except Exception as e:
            logger.error(f"[ErrorHandlerService] Error en handle_retry_action: {e}")
            return {
                "success": False,
                "message": "Error ejecutando la acción solicitada.",
                "error": str(e)
            }
    
    async def _execute_retry_operation(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ejecuta una operación de reintento."""
        # Simular reintento exitoso
        await asyncio.sleep(1)
        
        return {
            "success": True,
            "message": "Operación reintentada exitosamente.",
            "retry_count": self.retry_counters.get(chat_id, 0)
        }
    
    async def _execute_switch_to_fast_mode(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ejecuta cambio a modo rápido."""
        return {
            "success": True,
            "message": "Cambiado a modo rápido. Las operaciones serán más veloces.",
            "mode": "fast"
        }
    
    async def _execute_use_safe_mode(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ejecuta cambio a modo seguro."""
        return {
            "success": True,
            "message": "Cambiado a modo seguro. Las operaciones serán más conservadoras.",
            "mode": "safe"
        }
    
    async def _execute_diagnose_issue(
        self,
        chat_id: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Ejecuta diagnóstico del problema."""
        error_history = self.error_history.get(chat_id, [])
        
        if not error_history:
            return {
                "success": False,
                "message": "No hay historial de errores para diagnosticar."
            }
        
        # Analizar patrones de error
        recent_errors = error_history[-5:]  # Últimos 5 errores
        error_codes = [e["code"] for e in recent_errors]
        error_categories = [e["category"] for e in recent_errors]
        
        # Detectar patrones
        most_common_code = max(set(error_codes), key=error_codes.count)
        most_common_category = max(set(error_categories), key=error_categories.count)
        
        diagnosis = {
            "success": True,
            "message": "Diagnóstico completado.",
            "patterns": {
                "most_common_error": most_common_code,
                "most_common_category": most_common_category,
                "total_errors": len(error_history),
                "recent_errors": len(recent_errors)
            },
            "recommendations": [
                "El error más común es de tipo: " + most_common_code,
                "Categoría predominante: " + most_common_category,
                f"Total de errores en este chat: {len(error_history)}"
            ]
        }
        
        return diagnosis
    
    def get_error_statistics(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene estadísticas de errores para análisis.
        
        Args:
            chat_id: ID del chat específico o None para todos
            
        Returns:
            Dict con estadísticas de errores
        """
        if chat_id:
            # Estadísticas para un chat específico
            chat_errors = self.error_history.get(chat_id, [])
            return {
                "chat_id": chat_id,
                "total_errors": len(chat_errors),
                "retry_count": self.retry_counters.get(chat_id, 0),
                "recent_errors": [
                    {
                        "timestamp": e["timestamp"].isoformat(),
                        "code": e["code"],
                        "severity": e["severity"]
                    }
                    for e in chat_errors[-5:]  # Últimos 5 errores
                ]
            }
        else:
            # Estadísticas globales
            total_errors = sum(len(errors) for errors in self.error_history.values())
            total_chats = len(self.error_history)
            
            return {
                "total_errors": total_errors,
                "total_chats_with_errors": total_chats,
                "average_errors_per_chat": total_errors / total_chats if total_chats > 0 else 0,
                "chats_by_error_count": {
                    chat_id: len(errors) 
                    for chat_id, errors in self.error_history.items()
                }
            }
