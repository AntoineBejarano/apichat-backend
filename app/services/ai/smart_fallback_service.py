"""
🧠 Smart Fallback Service: Sistema de fallback ultra compacto e inteligente

Servicio que proporciona respuestas inteligentes cuando falla todo el sistema de detección
de modo, con mensajes ultra compactos y opciones binarias para el usuario.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import time
import random

logger = logging.getLogger(__name__)


class FallbackType(Enum):
    """Tipos de fallback disponibles"""
    MODE_DETECTION_FAILED = "mode_detection_failed"
    RESOURCE_CONFLICT = "resource_conflict"
    AGENT_NOT_FOUND = "agent_not_found"
    SYSTEM_ERROR = "system_error"
    AMBIGUOUS_QUERY = "ambiguous_query"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class FallbackStrategy(Enum):
    """Estrategias de fallback"""
    BINARY_CHOICE = "binary_choice"          # Opciones sí/no
    RESOURCE_LIST = "resource_list"          # Lista de recursos disponibles
    MODE_SELECTION = "mode_selection"        # Selección manual de modo
    RETRY = "retry"                          # Reintentar
    HELP = "help"                            # Mostrar ayuda


class SmartFallbackService:
    """
    🧠 Servicio de fallback inteligente ultra compacto
    
    Funcionalidades:
    - Respuestas ultra compactas cuando falla el sistema
    - Opciones binarias claras para el usuario
    - Recuperación automática del sistema
    - Sugerencias contextuales inteligentes
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Cache de fallbacks utilizados
        self._fallback_history = {}
        self._recovery_attempts = {}
        
        # Configuración de fallbacks por tipo
        self._fallback_configs = {
            FallbackType.MODE_DETECTION_FAILED: {
                "strategy": FallbackStrategy.BINARY_CHOICE,
                "message": "I'm not sure if you want to explore or execute. Would you like me to show your resources or start with a plan?",
                "options": ["Show resources", "Start with plan"],
                "recovery_timeout": 30  # segundos
            },
            FallbackType.RESOURCE_CONFLICT: {
                "strategy": FallbackStrategy.BINARY_CHOICE,
                "message": "I found multiple resources that could help. Should I prioritize databases first or show you all options?",
                "options": ["Prioritize DBs", "Show all options"],
                "recovery_timeout": 45
            },
            FallbackType.AGENT_NOT_FOUND: {
                "strategy": FallbackStrategy.MODE_SELECTION,
                "message": "I couldn't find the right agent for your request. Which mode would you prefer?",
                "options": ["Explorer", "Guided", "Auto"],
                "recovery_timeout": 60
            },
            FallbackType.SYSTEM_ERROR: {
                "strategy": FallbackStrategy.RETRY,
                "message": "Something went wrong. Would you like me to try again or switch to a simpler mode?",
                "options": ["Try again", "Simple mode"],
                "recovery_timeout": 90
            },
            FallbackType.AMBIGUOUS_QUERY: {
                "strategy": FallbackStrategy.BINARY_CHOICE,
                "message": "Your request is a bit unclear. Do you want to explore what's available or get help with something specific?",
                "options": ["Explore", "Get help"],
                "recovery_timeout": 40
            },
            FallbackType.TIMEOUT: {
                "strategy": FallbackStrategy.RETRY,
                "message": "This is taking longer than expected. Should I continue or try a different approach?",
                "options": ["Continue", "Different approach"],
                "recovery_timeout": 120
            },
            FallbackType.UNKNOWN: {
                "strategy": FallbackStrategy.BINARY_CHOICE,
                "message": "I'm not sure how to help with this request. Would you like me to show your resources or start with a plan?",
                "options": ["Show resources", "Start with plan"],
                "recovery_timeout": 30
            }
        }
        
        # Mensajes de recuperación automática
        self._recovery_messages = [
            "🔄 Recovering automatically...",
            "⚡ Switching to fallback mode...",
            "🔄 Attempting automatic recovery...",
            "⚡ Using backup strategy...",
            "🔄 System recovery in progress..."
        ]
        
        logger.info(f"[SmartFallbackService] 🚀 Inicializado para usuario {self.user_id}")
    
    async def handle_fallback(
        self, 
        fallback_type: FallbackType,
        context: Dict[str, Any],
        user_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        🎯 Maneja un fallback del sistema de forma inteligente
        
        Args:
            fallback_type: Tipo de fallback que ocurrió
            context: Contexto del fallback
            user_message: Mensaje del usuario que causó el fallback
            
        Returns:
            Respuesta de fallback con opciones de recuperación
        """
        try:
            start_time = time.time()
            logger.info(f"[SmartFallbackService] 🎯 Manejando fallback: {fallback_type.value}")
            
            # 1. Obtener configuración del fallback
            fallback_config = self._get_fallback_config(fallback_type)
            
            # 2. Generar mensaje personalizado
            personalized_message = await self._personalize_fallback_message(
                fallback_config, context, user_message
            )
            
            # 3. Crear opciones de recuperación
            recovery_options = await self._create_recovery_options(
                fallback_config, context
            )
            
            # 4. Registrar fallback para análisis
            await self._log_fallback(fallback_type, context, user_message)
            
            # 5. Intentar recuperación automática si es posible
            auto_recovery = await self._attempt_auto_recovery(fallback_type, context)
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "fallback_type": fallback_type.value,
                "message": personalized_message,
                "options": recovery_options,
                "strategy": fallback_config["strategy"].value,
                "auto_recovery": auto_recovery,
                "recovery_timeout": fallback_config["recovery_timeout"],
                "metadata": {
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "fallback_count": self._get_fallback_count(fallback_type),
                    "recovery_attempts": self._get_recovery_attempts(fallback_type)
                }
            }
            
            logger.info(f"[SmartFallbackService] ✅ Fallback manejado en {execution_time:.3f}s")
            return result
            
        except Exception as e:
            logger.exception(f"[SmartFallbackService] ❌ Error manejando fallback: {e}")
            return self._build_emergency_fallback(fallback_type, context)
    
    def _get_fallback_config(self, fallback_type: FallbackType) -> Dict[str, Any]:
        """Obtiene la configuración para un tipo de fallback"""
        return self._fallback_configs.get(fallback_type, self._fallback_configs[FallbackType.UNKNOWN])
    
    async def _personalize_fallback_message(
        self, 
        fallback_config: Dict[str, Any], 
        context: Dict[str, Any], 
        user_message: Optional[str] = None
    ) -> str:
        """Personaliza el mensaje de fallback basado en el contexto"""
        try:
            base_message = fallback_config["message"]
            
            # Personalizar basado en el idioma del usuario
            user_language = context.get("user_language", "en")
            if user_language == "es":
                base_message = self._translate_to_spanish(base_message)
            
            # Personalizar basado en el historial de fallbacks
            fallback_count = self._get_fallback_count(context.get("fallback_type", "unknown"))
            if fallback_count > 3:
                base_message += " (This has happened before - I'm working on improving this!)"
            
            # Personalizar basado en el tipo de usuario
            user_type = context.get("user_type", "regular")
            if user_type == "premium":
                base_message += " As a premium user, you can access advanced fallback options."
            
            # Personalizar basado en la hora del día
            current_hour = time.localtime().tm_hour
            if 22 <= current_hour or current_hour <= 6:
                base_message += " (Late night mode - using simplified options)"
            
            return base_message
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error personalizando mensaje: {e}")
            return fallback_config["message"]
    
    def _translate_to_spanish(self, message: str) -> str:
        """Traduce mensajes básicos al español"""
        translations = {
            "I'm not sure if you want to explore or execute. Would you like me to show your resources or start with a plan?": 
                "No estoy seguro si quieres explorar o ejecutar. ¿Te gustaría que te muestre tus recursos o que empiece con un plan?",
            "I found multiple resources that could help. Should I prioritize databases first or show you all options?":
                "Encontré múltiples recursos que podrían ayudar. ¿Debería priorizar las bases de datos primero o mostrarte todas las opciones?",
            "I couldn't find the right agent for your request. Which mode would you prefer?":
                "No pude encontrar el agente correcto para tu solicitud. ¿Qué modo prefieres?",
            "Something went wrong. Would you like me to try again or switch to a simpler mode?":
                "Algo salió mal. ¿Te gustaría que lo intente de nuevo o que cambie a un modo más simple?",
            "Your request is a bit unclear. Do you want to explore what's available or get help with something specific?":
                "Tu solicitud es un poco confusa. ¿Quieres explorar lo que está disponible o obtener ayuda con algo específico?",
            "This is taking longer than expected. Should I continue or try a different approach?":
                "Esto está tomando más tiempo del esperado. ¿Debería continuar o probar un enfoque diferente?"
        }
        
        return translations.get(message, message)
    
    async def _create_recovery_options(
        self, 
        fallback_config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Crea opciones de recuperación inteligentes"""
        try:
            base_options = fallback_config["options"]
            strategy = fallback_config["strategy"]
            
            if strategy == FallbackStrategy.BINARY_CHOICE:
                return self._create_binary_options(base_options, context)
            elif strategy == FallbackStrategy.MODE_SELECTION:
                return self._create_mode_options(context)
            elif strategy == FallbackStrategy.RESOURCE_LIST:
                return await self._create_resource_options(context)
            elif strategy == FallbackStrategy.RETRY:
                return self._create_retry_options(context)
            elif strategy == FallbackStrategy.HELP:
                return await self._create_help_options(context)
            else:
                return self._create_generic_options(base_options, context)
                
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error creando opciones: {e}")
            return self._create_generic_options(fallback_config["options"], context)
    
    def _create_binary_options(self, base_options: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones binarias claras"""
        return [
            {
                "id": f"option_{i}",
                "text": option,
                "action": option.lower().replace(" ", "_"),
                "type": "button",
                "priority": i + 1
            }
            for i, option in enumerate(base_options)
        ]
    
    def _create_mode_options(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones de selección de modo"""
        modes = [
            {"id": "explorer", "text": "🔍 Explorer", "description": "Explore your resources"},
            {"id": "guided", "text": "🎯 Guided", "description": "Get step-by-step guidance"},
            {"id": "auto", "text": "🤖 Auto", "description": "Let me choose the best approach"}
        ]
        
        return [
            {
                "id": mode["id"],
                "text": mode["text"],
                "description": mode["description"],
                "action": f"switch_to_{mode['id']}",
                "type": "mode_selection",
                "priority": i + 1
            }
            for i, mode in enumerate(modes)
        ]
    
    async def _create_resource_options(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones basadas en recursos disponibles"""
        try:
            # Obtener recursos del usuario
            user_resources = await self._get_user_resources(context)
            
            options = []
            for i, resource in enumerate(user_resources[:5]):  # Máximo 5 recursos
                options.append({
                    "id": f"resource_{resource['id']}",
                    "text": f"📊 {resource['name']}",
                    "description": resource.get('description', ''),
                    "action": f"use_resource_{resource['id']}",
                    "type": "resource",
                    "priority": i + 1
                })
            
            return options
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error obteniendo recursos: {e}")
            return self._create_generic_options(["Show databases", "Show apps", "Show strategies"], context)
    
    def _create_retry_options(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones de reintento"""
        return [
            {
                "id": "retry_same",
                "text": "🔄 Try again",
                "description": "Retry with the same approach",
                "action": "retry_same",
                "type": "retry",
                "priority": 1
            },
            {
                "id": "retry_different",
                "text": "🔄 Different approach",
                "description": "Try a different method",
                "action": "retry_different",
                "type": "retry",
                "priority": 2
            },
            {
                "id": "fallback_mode",
                "text": "🔄 Fallback mode",
                "description": "Switch to simplified mode",
                "action": "fallback_mode",
                "type": "retry",
                "priority": 3
            }
        ]
    
    async def _create_help_options(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones de ayuda"""
        return [
            {
                "id": "help_general",
                "text": "❓ General help",
                "description": "Get general usage help",
                "action": "show_help",
                "type": "help",
                "priority": 1
            },
            {
                "id": "help_examples",
                "text": "📚 Examples",
                "description": "See usage examples",
                "action": "show_examples",
                "type": "help",
                "priority": 2
            },
            {
                "id": "help_contact",
                "text": "📞 Contact support",
                "description": "Get human support",
                "action": "contact_support",
                "type": "help",
                "priority": 3
            }
        ]
    
    def _create_generic_options(self, base_options: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea opciones genéricas cuando fallan las específicas"""
        return [
            {
                "id": f"generic_{i}",
                "text": option,
                "action": f"generic_action_{i}",
                "type": "generic",
                "priority": i + 1
            }
            for i, option in enumerate(base_options)
        ]
    
    async def _get_user_resources(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Obtiene recursos del usuario para opciones de fallback"""
        try:
            # Simular obtención de recursos (en implementación real, usar servicios reales)
            return [
                {"id": "db_1", "name": "Users Database", "description": "User management database"},
                {"id": "app_1", "name": "CRM App", "description": "Customer relationship management"},
                {"id": "strategy_1", "name": "Data Analysis", "description": "Data analysis workflow"}
            ]
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error obteniendo recursos: {e}")
            return []
    
    async def _attempt_auto_recovery(self, fallback_type: FallbackType, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intenta recuperación automática del sistema"""
        try:
            recovery_key = f"{fallback_type.value}_{self.user_id}"
            attempts = self._recovery_attempts.get(recovery_key, 0)
            
            # Máximo 3 intentos de recuperación
            if attempts >= 3:
                return {
                    "possible": False,
                    "reason": "Max recovery attempts reached",
                    "message": "Maximum recovery attempts reached. Manual intervention required."
                }
            
            # Incrementar contador de intentos
            self._recovery_attempts[recovery_key] = attempts + 1
            
            # Intentar recuperación basada en el tipo de fallback
            if fallback_type == FallbackType.MODE_DETECTION_FAILED:
                return await self._recover_mode_detection(context)
            elif fallback_type == FallbackType.RESOURCE_CONFLICT:
                return await self._recover_resource_conflict(context)
            elif fallback_type == FallbackType.AGENT_NOT_FOUND:
                return await self._recover_agent_not_found(context)
            else:
                return {
                    "possible": False,
                    "reason": "No recovery strategy available",
                    "message": "No automatic recovery available for this type of fallback."
                }
                
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error en recuperación automática: {e}")
            return {
                "possible": False,
                "reason": "Recovery error",
                "message": "Error during automatic recovery attempt."
            }
    
    async def _recover_mode_detection(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recupera fallo de detección de modo"""
        try:
            # Intentar usar el último modo conocido del usuario
            last_known_mode = context.get("last_known_mode")
            if last_known_mode:
                return {
                    "possible": True,
                    "strategy": "use_last_known_mode",
                    "mode": last_known_mode,
                    "message": f"Recovering using last known mode: {last_known_mode}"
                }
            
            # Fallback al modo auto
            return {
                "possible": True,
                "strategy": "fallback_to_auto",
                "mode": "auto",
                "message": "Recovering by switching to auto mode"
            }
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error recuperando detección de modo: {e}")
            return {"possible": False, "reason": "Recovery error"}
    
    async def _recover_resource_conflict(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recupera conflicto de recursos"""
        try:
            # Usar estrategia de priorización automática
            return {
                "possible": True,
                "strategy": "auto_prioritization",
                "message": "Recovering using automatic resource prioritization"
            }
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error recuperando conflicto de recursos: {e}")
            return {"possible": False, "reason": "Recovery error"}
    
    async def _recover_agent_not_found(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recupera agente no encontrado"""
        try:
            # Usar agente genérico del sistema
            return {
                "possible": True,
                "strategy": "use_generic_agent",
                "message": "Recovering using generic system agent"
            }
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error recuperando agente: {e}")
            return {"possible": False, "reason": "Recovery error"}
    
    async def _log_fallback(self, fallback_type: FallbackType, context: Dict[str, Any], user_message: Optional[str] = None):
        """Registra el fallback para análisis posterior"""
        try:
            fallback_key = f"{fallback_type.value}_{self.user_id}"
            
            if fallback_key not in self._fallback_history:
                self._fallback_history[fallback_key] = []
            
            fallback_record = {
                "timestamp": time.time(),
                "type": fallback_type.value,
                "context": context,
                "user_message": user_message,
                "recovery_attempts": self._recovery_attempts.get(fallback_key, 0)
            }
            
            self._fallback_history[fallback_key].append(fallback_record)
            
            # Mantener solo los últimos 10 fallbacks
            if len(self._fallback_history[fallback_key]) > 10:
                self._fallback_history[fallback_key] = self._fallback_history[fallback_key][-10:]
                
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error registrando fallback: {e}")
    
    def _get_fallback_count(self, fallback_type: str) -> int:
        """Obtiene el número de fallbacks de un tipo específico"""
        fallback_key = f"{fallback_type}_{self.user_id}"
        return len(self._fallback_history.get(fallback_key, []))
    
    def _get_recovery_attempts(self, fallback_type: str) -> int:
        """Obtiene el número de intentos de recuperación"""
        fallback_key = f"{fallback_type}_{self.user_id}"
        return self._recovery_attempts.get(fallback_key, 0)
    
    async def get_fallback_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de fallbacks para análisis"""
        try:
            total_fallbacks = sum(len(history) for history in self._fallback_history.values())
            total_recovery_attempts = sum(self._recovery_attempts.values())
            
            return {
                "total_fallbacks": total_fallbacks,
                "total_recovery_attempts": total_recovery_attempts,
                "fallback_types": {
                    fallback_type: len(history) 
                    for fallback_type, history in self._fallback_history.items()
                },
                "recovery_success_rate": self._calculate_recovery_success_rate(),
                "most_common_fallback": self._get_most_common_fallback()
            }
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    def _calculate_recovery_success_rate(self) -> float:
        """Calcula la tasa de éxito de recuperación"""
        try:
            total_attempts = sum(self._recovery_attempts.values())
            if total_attempts == 0:
                return 0.0
            
            # Simular tasa de éxito (en implementación real, usar datos reales)
            successful_recoveries = total_attempts * 0.7  # 70% de éxito
            return round(successful_recoveries / total_attempts, 2)
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error calculando tasa de éxito: {e}")
            return 0.0
    
    def _get_most_common_fallback(self) -> Optional[str]:
        """Obtiene el tipo de fallback más común"""
        try:
            if not self._fallback_history:
                return None
            
            fallback_counts = {
                fallback_type: len(history) 
                for fallback_type, history in self._fallback_history.items()
            }
            
            if not fallback_counts:
                return None
            
            return max(fallback_counts, key=fallback_counts.get)
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error obteniendo fallback más común: {e}")
            return None
    
    def _build_emergency_fallback(self, fallback_type: FallbackType, context: Dict[str, Any]) -> Dict[str, Any]:
        """Construye fallback de emergencia cuando todo falla"""
        return {
            "success": False,
            "fallback_type": fallback_type.value,
            "message": "I'm having trouble understanding your request. Would you like me to show your resources or start with a plan?",
            "options": [
                {
                    "id": "emergency_show_resources",
                    "text": "Show resources",
                    "action": "show_resources",
                    "type": "emergency",
                    "priority": 1
                },
                {
                    "id": "emergency_start_plan",
                    "text": "Start with plan",
                    "action": "start_plan",
                    "type": "emergency",
                    "priority": 2
                }
            ],
            "strategy": "emergency_fallback",
            "auto_recovery": {"possible": False, "reason": "Emergency mode"},
            "recovery_timeout": 0,
            "metadata": {
                "execution_time_ms": 0,
                "fallback_count": 0,
                "recovery_attempts": 0,
                "emergency_mode": True
            }
        }
    
    async def clear_cache(self):
        """Limpia el cache de fallbacks"""
        self._fallback_history.clear()
        self._recovery_attempts.clear()
        logger.info("[SmartFallbackService] 🧹 Cache limpiado")


# Función helper para dependency injection
def get_smart_fallback_service(factory) -> SmartFallbackService:
    """Obtiene una instancia del Smart Fallback Service"""
    return SmartFallbackService(factory)
