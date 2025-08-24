"""
🔄 Mode Transition Service: Transiciones dinámicas entre modos

Servicio que detecta automáticamente cuando el usuario quiere cambiar de modo
y maneja las transiciones con confirmación inteligente cuando es necesario.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from datetime import datetime
from enum import Enum

from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.agent_router_service import AgentRouterService
from app.services.cache.response_cache_service import ResponseCacheService, ResponseType

logger = logging.getLogger(__name__)


class TransitionType(Enum):
    """Tipos de transición disponibles"""
    EXPLORER_TO_GUIDED = "explorer_to_guided"    # Explorer → Guided
    GUIDED_TO_EXPLORER = "guided_to_explorer"    # Guided → Explorer
    AUTO_TO_SPECIFIC = "auto_to_specific"        # Auto → Modo específico
    SPECIFIC_TO_AUTO = "specific_to_auto"        # Modo específico → Auto


class TransitionConfidence(Enum):
    """Niveles de confianza en la transición"""
    HIGH = "high"      # >0.8: Transición automática
    MEDIUM = "medium"  # 0.5-0.8: Confirmación sugerida
    LOW = "low"        # <0.5: Confirmación requerida


class ModeTransitionService:
    """
    🔄 Servicio de transiciones dinámicas entre modos
    
    Funcionalidades:
    - Detección automática de intención de cambio
    - Confirmación inteligente basada en confianza
    - Transiciones suaves entre modos
    - Persistencia de cambios de modo
    - Fallback inteligente en transiciones fallidas
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.mode_detection_service = factory.get_mode_detection_service()
        self.agent_router_service = factory.get_agent_router_service()
        self.cache_service = factory.get_response_cache_service()
        
        # Configuración de transiciones
        self._transition_config = {
            "auto_transition_threshold": 0.8,     # Confianza para transición automática
            "suggested_confirmation_threshold": 0.5,  # Confianza para confirmación sugerida
            "max_transition_attempts": 3,         # Máximo intentos de transición
            "transition_cooldown": 30,            # Segundos entre transiciones
            "enable_smart_fallback": True,        # Fallback inteligente
            "log_all_transitions": True           # Logging completo
        }
        
        # Estado de transiciones
        self._transition_history = []
        self._last_transition_time = None
        self._transition_attempts = 0
        
        # Patrones de transición
        self._transition_patterns = self._init_transition_patterns()
        
        # Reglas de transición
        self._transition_rules = self._init_transition_rules()
        
        logger.info(f"[ModeTransitionService] 🚀 Inicializado para usuario {self.user_id}")
    
    def _init_transition_patterns(self) -> Dict[str, List[str]]:
        """Inicializa patrones de detección de transición"""
        return {
            "explorer_to_guided": [
                # Palabras que indican selección de recursos
                "seleccionar", "usar", "ejecutar", "aplicar", "conectar",
                "analizar", "procesar", "generar", "crear", "modificar",
                "eliminar", "actualizar", "insertar", "consultar", "reportar",
                # Frases específicas
                "quiero usar", "necesito ejecutar", "déjame aplicar",
                "empieza con", "comienza con", "trabaja con",
                # Comandos directos
                "haz esto", "realiza esto", "ejecuta esto", "procesa esto"
            ],
            "guided_to_explorer": [
                # Palabras que indican exploración
                "explorar", "descubrir", "ver", "mostrar", "listar",
                "qué más", "otras opciones", "cambiar", "alternativas",
                "posibilidades", "capacidades", "funciones", "recursos",
                # Frases de exploración
                "qué puedo hacer", "muéstrame opciones", "déjame ver",
                "explícame", "enséñame", "guíame", "ayúdame a entender"
            ],
            "auto_to_specific": [
                # Palabras que especifican modo
                "modo explorer", "modo exploración", "modo guided", "modo ejecución",
                "quiero explorar", "quiero ejecutar", "déjame explorar", "déjame ejecutar",
                "cambia a explorer", "cambia a guided", "ponme en modo"
            ],
            "specific_to_auto": [
                # Palabras que indican modo automático
                "modo automático", "auto", "detecta", "tú decides",
                "como quieras", "lo que prefieras", "inteligente", "smart"
            ]
        }
    
    def _init_transition_rules(self) -> Dict[str, Dict[str, Any]]:
        """Inicializa reglas de transición"""
        return {
            "explorer_to_guided": {
                "requires_confirmation": False,
                "min_confidence": 0.7,
                "fallback_mode": "explorer",
                "suggested_message": "Cambiando a modo ejecución para trabajar con los recursos seleccionados.",
                "confirmation_message": "¿Quieres cambiar a modo ejecución para trabajar con recursos específicos?"
            },
            "guided_to_explorer": {
                "requires_confirmation": False,
                "min_confidence": 0.7,
                "fallback_mode": "guided",
                "suggested_message": "Cambiando a modo exploración para descubrir más opciones.",
                "confirmation_message": "¿Quieres cambiar a modo exploración para ver más opciones?"
            },
            "auto_to_specific": {
                "requires_confirmation": True,
                "min_confidence": 0.8,
                "fallback_mode": "auto",
                "suggested_message": "Detecté que quieres un modo específico. ¿Confirmas el cambio?",
                "confirmation_message": "¿Quieres cambiar del modo automático a un modo específico?"
            },
            "specific_to_auto": {
                "requires_confirmation": False,
                "min_confidence": 0.6,
                "fallback_mode": "auto",
                "suggested_message": "Cambiando a modo automático para detectar tu intención.",
                "confirmation_message": "¿Quieres que detecte automáticamente tu intención?"
            }
        }
    
    async def detect_transition_intent(
        self, 
        user_message: str, 
        current_mode: str,
        context: Dict[str, Any],
        chat_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        🎯 Detecta si el usuario quiere cambiar de modo
        
        Args:
            user_message: Mensaje del usuario
            current_mode: Modo actual
            context: Contexto actual
            chat_id: ID del chat para logging
            
        Returns:
            Resultado de la detección de transición
        """
        try:
            start_time = datetime.utcnow()
            logger.info(f"[ModeTransitionService] 🎯 Detectando intención de transición desde modo '{current_mode}'")
            
            # 1. Análisis de patrones de transición
            pattern_matches = self._analyze_transition_patterns(user_message, current_mode)
            
            # 2. Análisis de contexto para transición
            context_analysis = await self._analyze_transition_context(context, current_mode)
            
            # 3. Cálculo de confianza de transición
            transition_confidence = self._calculate_transition_confidence(
                pattern_matches, context_analysis, current_mode
            )
            
            # 4. Decisión de transición
            transition_decision = self._make_transition_decision(
                pattern_matches, transition_confidence, current_mode, context
            )
            
            # 5. Logging de la detección
            if self._transition_config["log_all_transitions"]:
                self._log_transition_detection(
                    user_message, current_mode, transition_decision, start_time
                )
            
            logger.info(f"[ModeTransitionService] ✅ Intención de transición detectada: {transition_decision['transition_type']}")
            
            return transition_decision
            
        except Exception as e:
            logger.exception(f"[ModeTransitionService] ❌ Error detectando intención de transición: {e}")
            return self._build_fallback_transition(current_mode, str(e))
    
    def _analyze_transition_patterns(self, user_message: str, current_mode: str) -> Dict[str, float]:
        """Analiza patrones de transición en el mensaje del usuario"""
        try:
            message_lower = user_message.lower().strip()
            pattern_scores = {}
            
            # Analizar cada tipo de transición
            for transition_type, patterns in self._transition_patterns.items():
                score = 0.0
                
                for pattern in patterns:
                    if pattern.lower() in message_lower:
                        # Puntuación base por patrón encontrado
                        base_score = 0.3
                        
                        # Bonus por patrones más específicos
                        if len(pattern.split()) > 1:  # Frases completas
                            base_score += 0.2
                        
                        # Bonus por patrones de comando directo
                        if pattern in ["haz esto", "ejecuta esto", "realiza esto"]:
                            base_score += 0.3
                        
                        score += base_score
                
                # Normalizar puntuación
                pattern_scores[transition_type] = min(score, 1.0)
            
            return pattern_scores
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error analizando patrones: {e}")
            return {}
    
    async def _analyze_transition_context(self, context: Dict[str, Any], current_mode: str) -> Dict[str, Any]:
        """Analiza el contexto para determinar si es apropiado cambiar de modo"""
        try:
            context_analysis = {
                "resources_selected": False,
                "mode_consistency": 0.0,
                "user_intent_clarity": 0.0,
                "transition_appropriateness": 0.0
            }
            
            # Verificar si hay recursos seleccionados
            db_ids = context.get("db_ids", [])
            app_ids = context.get("app_ids", [])
            
            if db_ids or app_ids:
                context_analysis["resources_selected"] = True
                # Si hay recursos seleccionados, es más apropiado ir a Guided
                if current_mode == "explorer":
                    context_analysis["transition_appropriateness"] += 0.4
            
            # Verificar consistencia del modo actual
            if current_mode == "auto":
                context_analysis["mode_consistency"] = 0.5  # Auto es flexible
            elif current_mode in ["explorer", "guided"]:
                context_analysis["mode_consistency"] = 0.8  # Modos específicos son consistentes
            
            # Analizar claridad de intención del usuario
            # TODO: Implementar análisis más sofisticado
            context_analysis["user_intent_clarity"] = 0.7
            
            return context_analysis
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error analizando contexto: {e}")
            return {"error": str(e)}
    
    def _calculate_transition_confidence(
        self, 
        pattern_scores: Dict[str, float], 
        context_analysis: Dict[str, Any],
        current_mode: str
    ) -> float:
        """Calcula la confianza en la transición"""
        try:
            # Puntuación base de patrones
            max_pattern_score = max(pattern_scores.values()) if pattern_scores else 0.0
            
            # Factor de contexto
            context_factor = 0.0
            if context_analysis.get("resources_selected"):
                context_factor += 0.2
            if context_analysis.get("transition_appropriateness", 0.0) > 0.3:
                context_factor += 0.2
            
            # Factor de modo actual
            mode_factor = 0.0
            if current_mode == "auto":
                mode_factor = 0.1  # Auto es más flexible
            elif current_mode in ["explorer", "guided"]:
                mode_factor = 0.3  # Modos específicos requieren más confianza
            
            # Cálculo final
            confidence = max_pattern_score + context_factor + mode_factor
            
            return min(confidence, 1.0)
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error calculando confianza: {e}")
            return 0.0
    
    def _make_transition_decision(
        self, 
        pattern_scores: Dict[str, float], 
        confidence: float,
        current_mode: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Toma la decisión final sobre la transición"""
        try:
            # Encontrar el tipo de transición con mayor puntuación
            best_transition = max(pattern_scores.items(), key=lambda x: x[1]) if pattern_scores else (None, 0.0)
            transition_type = best_transition[0]
            pattern_score = best_transition[1]
            
            if not transition_type or pattern_score < 0.3:
                return {
                    "should_transition": False,
                    "reason": "no_transition_intent",
                    "confidence": confidence,
                    "current_mode": current_mode,
                    "suggested_mode": current_mode
                }
            
            # Obtener reglas de transición
            transition_rules = self._transition_rules.get(transition_type, {})
            
            # Verificar si se requiere confirmación
            requires_confirmation = transition_rules.get("requires_confirmation", True)
            min_confidence = transition_rules.get("min_confidence", 0.7)
            
            # Determinar nivel de confianza
            if confidence >= self._transition_config["auto_transition_threshold"]:
                confidence_level = TransitionConfidence.HIGH
            elif confidence >= self._transition_config["suggested_confirmation_threshold"]:
                confidence_level = TransitionConfidence.MEDIUM
            else:
                confidence_level = TransitionConfidence.LOW
            
            # Decidir si hacer transición automática
            should_transition = False
            if confidence >= min_confidence:
                if confidence_level == TransitionConfidence.HIGH:
                    should_transition = True
                elif confidence_level == TransitionConfidence.MEDIUM and not requires_confirmation:
                    should_transition = True
            
            # Determinar modo sugerido
            suggested_mode = self._determine_suggested_mode(transition_type, current_mode)
            
            # Construir respuesta
            result = {
                "should_transition": should_transition,
                "transition_type": transition_type,
                "confidence": confidence,
                "confidence_level": confidence_level.value,
                "current_mode": current_mode,
                "suggested_mode": suggested_mode,
                "requires_confirmation": requires_confirmation,
                "pattern_score": pattern_score,
                "transition_rules": transition_rules
            }
            
            # Agregar mensajes apropiados
            if should_transition:
                result["message"] = transition_rules.get("suggested_message", "Transición automática realizada.")
                result["action"] = "auto_transition"
            elif confidence >= min_confidence:
                result["message"] = transition_rules.get("confirmation_message", "¿Confirmas el cambio de modo?")
                result["action"] = "request_confirmation"
            else:
                result["message"] = "No se detectó intención clara de cambio de modo."
                result["action"] = "no_action"
            
            return result
            
        except Exception as e:
            logger.error(f"[ModeTransitionService] ❌ Error en decisión de transición: {e}")
            return self._build_fallback_transition(current_mode, str(e))
    
    def _determine_suggested_mode(self, transition_type: str, current_mode: str) -> str:
        """Determina el modo sugerido basado en el tipo de transición"""
        try:
            if transition_type == "explorer_to_guided":
                return "guided"
            elif transition_type == "guided_to_explorer":
                return "explorer"
            elif transition_type == "auto_to_specific":
                # Determinar basado en contexto o preferencia del usuario
                return "explorer"  # Por defecto, más seguro
            elif transition_type == "specific_to_auto":
                return "auto"
            else:
                return current_mode
                
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error determinando modo sugerido: {e}")
            return current_mode
    
    async def execute_transition(
        self, 
        from_mode: str, 
        to_mode: str, 
        context: Dict[str, Any],
        chat_id: Optional[UUID] = None,
        user_confirmation: bool = False
    ) -> Dict[str, Any]:
        """
        🔄 Ejecuta la transición de modo
        
        Args:
            from_mode: Modo actual
            to_mode: Modo objetivo
            context: Contexto de la transición
            chat_id: ID del chat
            user_confirmation: Confirmación del usuario
            
        Returns:
            Resultado de la transición
        """
        try:
            start_time = datetime.utcnow()
            
            # Verificar cooldown de transiciones
            if not self._can_transition():
                return {
                    "success": False,
                    "reason": "transition_cooldown",
                    "message": "Demasiadas transiciones recientes. Espera un momento.",
                    "from_mode": from_mode,
                    "to_mode": to_mode
                }
            
            logger.info(f"[ModeTransitionService] 🔄 Ejecutando transición: {from_mode} → {to_mode}")
            
            # 1. Validar transición
            validation_result = self._validate_transition(from_mode, to_mode, context)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "reason": "invalid_transition",
                    "message": validation_result["message"],
                    "from_mode": from_mode,
                    "to_mode": to_mode
                }
            
            # 2. Preparar transición
            transition_prep = await self._prepare_transition(from_mode, to_mode, context)
            
            # 3. Ejecutar transición
            transition_result = await self._perform_transition(
                from_mode, to_mode, context, transition_prep
            )
            
            # 4. Actualizar estado
            if transition_result["success"]:
                self._update_transition_state(from_mode, to_mode, start_time)
                
                # Cachear información de transición
                await self._cache_transition_info(from_mode, to_mode, context, chat_id)
            
            # 5. Logging
            self._log_transition_execution(
                from_mode, to_mode, transition_result, start_time, chat_id
            )
            
            logger.info(f"[ModeTransitionService] ✅ Transición completada: {from_mode} → {to_mode}")
            
            return transition_result
            
        except Exception as e:
            logger.exception(f"[ModeTransitionService] ❌ Error ejecutando transición: {e}")
            return {
                "success": False,
                "reason": "execution_error",
                "message": f"Error en la transición: {str(e)}",
                "from_mode": from_mode,
                "to_mode": to_mode
            }
    
    def _can_transition(self) -> bool:
        """Verifica si se puede realizar una transición"""
        try:
            # Verificar límite de intentos
            if self._transition_attempts >= self._transition_config["max_transition_attempts"]:
                return False
            
            # Verificar cooldown
            if self._last_transition_time:
                cooldown_seconds = self._transition_config["transition_cooldown"]
                time_since_last = (datetime.utcnow() - self._last_transition_time).total_seconds()
                if time_since_last < cooldown_seconds:
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error verificando transición: {e}")
            return False
    
    def _validate_transition(self, from_mode: str, to_mode: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida si la transición es apropiada"""
        try:
            # Transiciones válidas
            valid_transitions = [
                ("explorer", "guided"),
                ("guided", "explorer"),
                ("auto", "explorer"),
                ("auto", "guided"),
                ("explorer", "auto"),
                ("guided", "auto")
            ]
            
            if (from_mode, to_mode) not in valid_transitions:
                return {
                    "valid": False,
                    "message": f"Transición no válida: {from_mode} → {to_mode}"
                }
            
            # Validaciones específicas por tipo de transición
            if from_mode == "guided" and to_mode == "explorer":
                # Verificar que no se pierda contexto importante
                if context.get("db_ids") or context.get("app_ids"):
                    return {
                        "valid": True,
                        "message": "Transición válida con recursos seleccionados"
                    }
            
            return {"valid": True, "message": "Transición válida"}
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error validando transición: {e}")
            return {"valid": False, "message": f"Error en validación: {str(e)}"}
    
    async def _prepare_transition(self, from_mode: str, to_mode: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara la transición de modo"""
        try:
            preparation = {
                "mode_change": f"{from_mode} → {to_mode}",
                "timestamp": datetime.utcnow().isoformat(),
                "context_preserved": True,
                "resources_maintained": True
            }
            
            # Preservar contexto importante
            if context.get("db_ids") or context.get("app_ids"):
                preparation["resources_maintained"] = True
                preparation["context_preserved"] = True
            
            # Preparar mensaje de transición
            if to_mode == "guided":
                preparation["message"] = "Cambiando a modo ejecución. Los recursos seleccionados están listos para usar."
            elif to_mode == "explorer":
                preparation["message"] = "Cambiando a modo exploración. Puedes descubrir más opciones disponibles."
            elif to_mode == "auto":
                preparation["message"] = "Activando modo automático. Detectando tu intención en cada mensaje."
            
            return preparation
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error preparando transición: {e}")
            return {"error": str(e)}
    
    async def _perform_transition(
        self, 
        from_mode: str, 
        to_mode: str, 
        context: Dict[str, Any],
        preparation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ejecuta la transición real"""
        try:
            # Actualizar contexto con nuevo modo
            updated_context = context.copy()
            updated_context["mode"] = to_mode
            updated_context["previous_mode"] = from_mode
            updated_context["mode_changed_at"] = datetime.utcnow().isoformat()
            
            # Verificar que el agente del nuevo modo esté disponible
            if self.agent_router_service:
                available_agent = await self.agent_router_service.get_agent_for_mode(
                    to_mode, self.user_id
                )
                if not available_agent:
                    return {
                        "success": False,
                        "reason": "no_agent_available",
                        "message": f"No hay agente disponible para el modo '{to_mode}'",
                        "from_mode": from_mode,
                        "to_mode": to_mode
                    }
            
            return {
                "success": True,
                "from_mode": from_mode,
                "to_mode": to_mode,
                "updated_context": updated_context,
                "preparation": preparation,
                "message": preparation.get("message", "Transición completada exitosamente"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ModeTransitionService] ❌ Error ejecutando transición: {e}")
            return {
                "success": False,
                "reason": "transition_failed",
                "message": f"Error en la transición: {str(e)}",
                "from_mode": from_mode,
                "to_mode": to_mode
            }
    
    def _update_transition_state(self, from_mode: str, to_mode: str, timestamp: datetime):
        """Actualiza el estado interno de transiciones"""
        try:
            self._transition_history.append({
                "from_mode": from_mode,
                "to_mode": to_mode,
                "timestamp": timestamp,
                "success": True
            })
            
            self._last_transition_time = timestamp
            self._transition_attempts = 0
            
            # Limpiar historial si es muy largo
            if len(self._transition_history) > 100:
                self._transition_history = self._transition_history[-50:]
                
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error actualizando estado: {e}")
    
    async def _cache_transition_info(self, from_mode: str, to_mode: str, context: Dict[str, Any], chat_id: Optional[UUID]):
        """Cachea información de la transición"""
        try:
            if self.cache_service:
                transition_info = {
                    "from_mode": from_mode,
                    "to_mode": to_mode,
                    "context": context,
                    "chat_id": str(chat_id) if chat_id else None,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                cache_key = f"transition_{self.user_id}_{chat_id or 'general'}"
                await self.cache_service.cache_response(
                    cache_key, 
                    transition_info, 
                    ResponseType.TRANSITION
                )
                
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error cacheando transición: {e}")
    
    def _build_fallback_transition(self, current_mode: str, error: str) -> Dict[str, Any]:
        """Construye respuesta de fallback para transición"""
        return {
            "should_transition": False,
            "reason": "fallback",
            "confidence": 0.0,
            "current_mode": current_mode,
            "suggested_mode": current_mode,
            "message": f"No se pudo detectar transición. Error: {error}",
            "action": "fallback"
        }
    
    def _log_transition_detection(self, user_message: str, current_mode: str, decision: Dict[str, Any], start_time: datetime):
        """Log de detección de transición"""
        try:
            log_entry = {
                "timestamp": start_time.isoformat(),
                "user_message": user_message[:100] + "..." if len(user_message) > 100 else user_message,
                "current_mode": current_mode,
                "detected_transition": decision.get("transition_type"),
                "confidence": decision.get("confidence", 0.0),
                "action": decision.get("action", "unknown")
            }
            
            self._transition_history.append(log_entry)
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error en logging: {e}")
    
    def _log_transition_execution(self, from_mode: str, to_mode: str, result: Dict[str, Any], start_time: datetime, chat_id: Optional[UUID]):
        """Log de ejecución de transición"""
        try:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            log_entry = {
                "timestamp": start_time.isoformat(),
                "from_mode": from_mode,
                "to_mode": to_mode,
                "success": result.get("success", False),
                "execution_time": execution_time,
                "chat_id": str(chat_id) if chat_id else None,
                "reason": result.get("reason", "unknown")
            }
            
            self._transition_history.append(log_entry)
            
        except Exception as e:
            logger.warning(f"[ModeTransitionService] ⚠️ Error en logging de ejecución: {e}")
    
    async def get_transition_stats(self) -> Dict[str, Any]:
        """📊 Obtiene estadísticas de transiciones"""
        try:
            return {
                "user_id": str(self.user_id),
                "total_transitions": len([t for t in self._transition_history if t.get("success")]),
                "failed_transitions": len([t for t in self._transition_history if not t.get("success")]),
                "last_transition": self._last_transition_time.isoformat() if self._last_transition_time else None,
                "transition_attempts": self._transition_attempts,
                "recent_transitions": self._transition_history[-10:] if self._transition_history else [],
                "config": self._transition_config.copy()
            }
        except Exception as e:
            logger.error(f"[ModeTransitionService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def reset_transition_state(self) -> bool:
        """🔄 Resetea el estado de transiciones"""
        try:
            self._transition_history.clear()
            self._last_transition_time = None
            self._transition_attempts = 0
            
            logger.info("[ModeTransitionService] ✅ Estado de transiciones reseteado")
            return True
            
        except Exception as e:
            logger.error(f"[ModeTransitionService] ❌ Error reseteando estado: {e}")
            return False


# Función helper para dependency injection
def get_mode_transition_service(factory) -> ModeTransitionService:
    """Obtiene una instancia del Mode Transition Service"""
    return ModeTransitionService(factory)
