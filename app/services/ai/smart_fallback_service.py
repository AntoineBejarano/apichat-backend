"""
🎯 Servicio de Smart Fallbacks para el Sistema Explorer/Guided

Este servicio proporciona respuestas inteligentes cuando falla la detección de modo:
- Respuestas contextuales basadas en el mensaje
- Sugerencias inteligentes para el usuario
- Aprendizaje de preferencias del usuario
- Fallbacks ultra compactos
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum

from app.core.service_factory import ServiceFactory
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.prompt_builder_service import PromptBuilderService

logger = logging.getLogger(__name__)


class FallbackType(Enum):
    """Tipos de fallback"""
    MODE_AMBIGUOUS = "mode_ambiguous"      # No se puede determinar el modo
    DETECTION_FAILED = "detection_failed"   # Falló la detección
    RESOURCE_CONFLICT = "resource_conflict" # Conflicto entre recursos
    SYSTEM_ERROR = "system_error"          # Error del sistema
    USER_GUIDANCE = "user_guidance"        # Necesita guía del usuario


class FallbackConfidence(Enum):
    """Niveles de confianza del fallback"""
    HIGH = "high"      # 80-100% seguro
    MEDIUM = "medium"  # 50-79% seguro
    LOW = "low"        # 20-49% seguro
    UNCERTAIN = "uncertain"  # <20% seguro


class SmartFallbackService:
    """
    🚀 Servicio de Smart Fallbacks
    
    Proporciona respuestas inteligentes cuando falla la detección de modo
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.user_id = None  # Se establece al inicializar
        self.fallback_patterns: Dict[str, Dict[str, Any]] = {}
        self.user_preferences: Dict[str, Any] = {}
        self.fallback_history: List[Dict[str, Any]] = []
        
        # Configuración de fallbacks
        self.fallback_config = {
            "max_fallback_history": 100,
            "learning_enabled": True,
            "context_window": 5,  # Últimos 5 mensajes para contexto
            "confidence_thresholds": {
                "high": 0.8,
                "medium": 0.5,
                "low": 0.2
            }
        }
        
        # Patrones de fallback predefinidos
        self._initialize_fallback_patterns()
        
        logger.info("[SmartFallbackService] 🚀 Servicio inicializado")
    
    def _initialize_fallback_patterns(self):
        """Inicializa patrones de fallback predefinidos"""
        self.fallback_patterns = {
            "mode_ambiguous": {
                "patterns": [
                    r"^(show|display|list|get|find|search|explore|analyze|help|what|how|when|where|why)",
                    r"(database|table|schema|connection|api|app|strategy|resource)",
                    r"(my|the|a|an|some|all|any|every)"
                ],
                "responses": [
                    "I'm not sure if you want to explore or execute. Would you like me to show your resources or start with a plan?",
                    "I can help you explore your resources or create a plan. What would you prefer?",
                    "Let me clarify: do you want to see what's available or work with specific resources?"
                ],
                "confidence": FallbackConfidence.MEDIUM
            },
            "exploration_hint": {
                "patterns": [
                    r"(show|display|list|get|find|search|explore|browse|overview|summary)",
                    r"(what|how many|which|where are|find all)"
                ],
                "responses": [
                    "It looks like you want to explore. I'll show you your available resources.",
                    "I'll help you explore what's available. Let me show you your resources.",
                    "Exploring mode activated. Here's what you have access to:"
                ],
                "confidence": FallbackConfidence.HIGH,
                "suggested_mode": "explorer"
            },
            "execution_hint": {
                "patterns": [
                    r"(create|build|make|generate|execute|run|perform|implement|plan|analyze|optimize)",
                    r"(help me|assist|guide|walk through|step by step)"
                ],
                "responses": [
                    "It looks like you want to execute something. I'll help you create a plan.",
                    "I'll guide you through this. Let me create a plan for you.",
                    "Execution mode activated. I'll help you get started:"
                ],
                "confidence": FallbackConfidence.HIGH,
                "suggested_mode": "guided"
            },
            "resource_specific": {
                "patterns": [
                    r"(database|table|schema|connection|api|app|strategy)",
                    r"(mysql|postgresql|mongodb|redis|elasticsearch)",
                    r"(rest|graphql|soap|grpc)"
                ],
                "responses": [
                    "I see you're working with {resource_type}. Let me help you with that.",
                    "I'll focus on your {resource_type}. What would you like to do?",
                    "Working with {resource_type}. I'll guide you through this."
                ],
                "confidence": FallbackConfidence.MEDIUM,
                "resource_extraction": True
            },
            "general_help": {
                "patterns": [
                    r"(help|assist|support|guide|tutorial|how to|what can|examples)",
                    r"(new|beginner|start|begin|first time|learning)"
                ],
                "responses": [
                    "I'm here to help! I can show you your resources or help you create plans.",
                    "Let me guide you. I can explore your resources or help you execute tasks.",
                    "I'll help you get started. Would you like to explore or work on something specific?"
                ],
                "confidence": FallbackConfidence.HIGH
            }
        }
    
    async def initialize(self, user_id: str):
        """Inicializa el servicio para un usuario específico"""
        self.user_id = user_id
        logger.info(f"[SmartFallbackService] Inicializado para usuario: {user_id}")
        
        # Cargar preferencias del usuario
        await self._load_user_preferences()
        
        # Cargar historial de fallbacks
        await self._load_fallback_history()
    
    async def _load_user_preferences(self):
        """Carga preferencias del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, preferencias por defecto
            self.user_preferences = {
                "preferred_mode": "auto",
                "fallback_style": "compact",
                "learning_enabled": True,
                "context_sensitivity": "medium"
            }
            
            logger.debug(f"[SmartFallbackService] Preferencias cargadas para usuario: {self.user_id}")
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error cargando preferencias: {e}")
    
    async def _load_fallback_history(self):
        """Carga historial de fallbacks del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, historial vacío
            self.fallback_history = []
            
            logger.debug(f"[SmartFallbackService] Historial de fallbacks cargado")
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error cargando historial: {e}")
    
    async def get_smart_fallback(
        self,
        message: str,
        fallback_type: FallbackType,
        context: Optional[Dict[str, Any]] = None,
        previous_messages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        🎯 Obtiene un fallback inteligente basado en el tipo y contexto
        
        Args:
            message: Mensaje del usuario que causó el fallback
            fallback_type: Tipo de fallback que ocurrió
            context: Contexto adicional (recursos, modo anterior, etc.)
            previous_messages: Últimos mensajes para contexto
            
        Returns:
            Dict con respuesta de fallback, confianza y metadatos
        """
        try:
            start_time = datetime.now()
            context = context or {}
            previous_messages = previous_messages or []
            
            # Analizar el mensaje para determinar el mejor fallback
            analysis = self._analyze_message_for_fallback(message, context, previous_messages)
            
            # Seleccionar el fallback más apropiado
            fallback_response = self._select_best_fallback(analysis, fallback_type)
            
            # Aplicar personalización del usuario
            personalized_response = await self._personalize_fallback(fallback_response, context)
            
            # Generar sugerencias contextuales
            suggestions = await self._generate_contextual_suggestions(message, context, analysis)
            
            # Construir respuesta final
            result = {
                "fallback_type": fallback_type.value,
                "response": personalized_response["response"],
                "confidence": personalized_response["confidence"],
                "suggested_mode": personalized_response.get("suggested_mode"),
                "suggestions": suggestions,
                "context_analysis": analysis,
                "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "timestamp": datetime.now().isoformat()
            }
            
            # Registrar fallback para aprendizaje
            await self._record_fallback(message, fallback_type, result, context)
            
            logger.info(f"[SmartFallbackService] Fallback generado: {fallback_type.value} (confianza: {result['confidence']})")
            
            return result
            
        except Exception as e:
            logger.error(f"[SmartFallbackService] ❌ Error generando fallback: {e}")
            return self._get_emergency_fallback(fallback_type)
    
    def _analyze_message_for_fallback(
        self,
        message: str,
        context: Dict[str, Any],
        previous_messages: List[str]
    ) -> Dict[str, Any]:
        """Analiza el mensaje para determinar el mejor fallback"""
        analysis = {
            "message_length": len(message),
            "word_count": len(message.split()),
            "contains_questions": "?" in message,
            "contains_commands": self._detect_commands(message),
            "resource_mentions": self._extract_resource_mentions(message),
            "intent_indicators": self._detect_intent_indicators(message),
            "context_similarity": self._analyze_context_similarity(message, previous_messages),
            "complexity_score": self._calculate_complexity_score(message)
        }
        
        return analysis
    
    def _detect_commands(self, message: str) -> List[str]:
        """Detecta comandos en el mensaje"""
        commands = []
        command_patterns = [
            r"\b(show|display|list|get|find|search|explore|create|build|make|generate|execute|run|perform|implement|plan|analyze|optimize)\b",
            r"\b(help|assist|support|guide|tutorial|how to|what can|examples)\b"
        ]
        
        for pattern in command_patterns:
            matches = re.findall(pattern, message.lower())
            commands.extend(matches)
        
        return list(set(commands))
    
    def _extract_resource_mentions(self, message: str) -> List[str]:
        """Extrae menciones de recursos del mensaje"""
        resources = []
        resource_patterns = [
            r"\b(database|table|schema|connection|api|app|strategy|resource)\b",
            r"\b(mysql|postgresql|mongodb|redis|elasticsearch|sql|nosql)\b",
            r"\b(rest|graphql|soap|grpc|http|https)\b"
        ]
        
        for pattern in resource_patterns:
            matches = re.findall(pattern, message.lower())
            resources.extend(matches)
        
        return list(set(resources))
    
    def _detect_intent_indicators(self, message: str) -> Dict[str, float]:
        """Detecta indicadores de intención en el mensaje"""
        intent_scores = {
            "exploration": 0.0,
            "execution": 0.0,
            "help": 0.0,
            "analysis": 0.0
        }
        
        # Patrones de exploración
        exploration_patterns = [
            r"\b(show|display|list|get|find|search|explore|browse|overview|summary)\b",
            r"\b(what|how many|which|where are|find all)\b"
        ]
        
        # Patrones de ejecución
        execution_patterns = [
            r"\b(create|build|make|generate|execute|run|perform|implement|plan)\b",
            r"\b(help me|assist|guide|walk through|step by step)\b"
        ]
        
        # Patrones de ayuda
        help_patterns = [
            r"\b(help|assist|support|guide|tutorial|how to|what can|examples)\b",
            r"\b(new|beginner|start|begin|first time|learning)\b"
        ]
        
        # Patrones de análisis
        analysis_patterns = [
            r"\b(analyze|examine|investigate|study|review|check|verify|test)\b",
            r"\b(performance|optimization|efficiency|speed|quality|metrics)\b"
        ]
        
        # Calcular scores
        for pattern in exploration_patterns:
            if re.search(pattern, message.lower()):
                intent_scores["exploration"] += 0.3
        
        for pattern in execution_patterns:
            if re.search(pattern, message.lower()):
                intent_scores["execution"] += 0.3
        
        for pattern in help_patterns:
            if re.search(pattern, message.lower()):
                intent_scores["help"] += 0.3
        
        for pattern in analysis_patterns:
            if re.search(pattern, message.lower()):
                intent_scores["analysis"] += 0.3
        
        # Normalizar scores
        total_score = sum(intent_scores.values())
        if total_score > 0:
            for intent in intent_scores:
                intent_scores[intent] = min(intent_scores[intent] / total_score, 1.0)
        
        return intent_scores
    
    def _analyze_context_similarity(self, message: str, previous_messages: List[str]) -> float:
        """Analiza similitud con mensajes anteriores"""
        if not previous_messages:
            return 0.0
        
        # Calcular similitud simple basada en palabras comunes
        current_words = set(message.lower().split())
        similarities = []
        
        for prev_message in previous_messages[-self.fallback_config["context_window"]:]:
            prev_words = set(prev_message.lower().split())
            if current_words and prev_words:
                similarity = len(current_words.intersection(prev_words)) / len(current_words.union(prev_words))
                similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _calculate_complexity_score(self, message: str) -> float:
        """Calcula un score de complejidad del mensaje"""
        score = 0.0
        
        # Longitud del mensaje
        if len(message) > 100:
            score += 0.3
        elif len(message) > 50:
            score += 0.2
        elif len(message) > 20:
            score += 0.1
        
        # Número de palabras
        word_count = len(message.split())
        if word_count > 15:
            score += 0.3
        elif word_count > 10:
            score += 0.2
        elif word_count > 5:
            score += 0.1
        
        # Preguntas
        if "?" in message:
            score += 0.2
        
        # Comandos múltiples
        commands = self._detect_commands(message)
        if len(commands) > 2:
            score += 0.2
        elif len(commands) > 1:
            score += 0.1
        
        # Recursos múltiples
        resources = self._extract_resource_mentions(message)
        if len(resources) > 2:
            score += 0.2
        elif len(resources) > 1:
            score += 0.1
        
        return min(score, 1.0)
    
    def _select_best_fallback(
        self,
        analysis: Dict[str, Any],
        fallback_type: FallbackType
    ) -> Dict[str, Any]:
        """Selecciona el mejor fallback basado en el análisis"""
        best_fallback = None
        best_score = 0.0
        
        for pattern_name, pattern_data in self.fallback_patterns.items():
            score = self._calculate_pattern_match_score(analysis, pattern_data)
            
            if score > best_score:
                best_score = score
                best_fallback = pattern_data
        
        if not best_fallback:
            # Fallback por defecto
            best_fallback = {
                "responses": ["I'm here to help. What would you like to do?"],
                "confidence": FallbackConfidence.LOW
            }
        
        # Seleccionar respuesta aleatoria de las disponibles
        import random
        selected_response = random.choice(best_fallback["responses"])
        
        return {
            "response": selected_response,
            "confidence": best_fallback["confidence"].value if hasattr(best_fallback["confidence"], 'value') else best_fallback["confidence"],
            "suggested_mode": best_fallback.get("suggested_mode"),
            "pattern_name": pattern_name if 'pattern_name' in locals() else "default"
        }
    
    def _calculate_pattern_match_score(
        self,
        analysis: Dict[str, Any],
        pattern_data: Dict[str, Any]
    ) -> float:
        """Calcula score de coincidencia con un patrón"""
        score = 0.0
        
        # Coincidencia con patrones regex
        patterns = pattern_data.get("patterns", [])
        for pattern in patterns:
            if re.search(pattern, analysis.get("message", ""), re.IGNORECASE):
                score += 0.4
        
        # Indicadores de intención
        intent_scores = analysis.get("intent_indicators", {})
        if "exploration" in intent_scores and pattern_data.get("suggested_mode") == "explorer":
            score += intent_scores["exploration"] * 0.3
        
        if "execution" in intent_scores and pattern_data.get("suggested_mode") == "guided":
            score += intent_scores["execution"] * 0.3
        
        # Complejidad del mensaje
        complexity = analysis.get("complexity_score", 0.0)
        if complexity > 0.7 and pattern_data.get("confidence") == FallbackConfidence.HIGH:
            score += 0.2
        
        return min(score, 1.0)
    
    async def _personalize_fallback(
        self,
        fallback_response: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Personaliza el fallback basado en preferencias del usuario"""
        try:
            # Obtener servicio de prompts para personalización
            prompt_service = self.factory.get_prompt_builder_service()
            
            # Personalizar respuesta basada en preferencias del usuario
            user_style = self.user_preferences.get("fallback_style", "compact")
            
            if user_style == "detailed" and fallback_response["confidence"] == FallbackConfidence.LOW:
                # Expandir respuesta para usuarios que prefieren detalles
                fallback_response["response"] += " I can help you explore your resources or create specific plans. What would you like to focus on?"
            
            elif user_style == "compact" and fallback_response["confidence"] == FallbackConfidence.HIGH:
                # Acortar respuesta para usuarios que prefieren concisión
                if len(fallback_response["response"]) > 100:
                    fallback_response["response"] = fallback_response["response"][:100] + "..."
            
            # Aplicar contexto de recursos si está disponible
            if context.get("available_resources"):
                resource_context = context["available_resources"]
                if len(resource_context) > 0:
                    fallback_response["response"] += f" I can see you have {len(resource_context)} resources available."
            
            return fallback_response
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error personalizando fallback: {e}")
            return fallback_response
    
    async def _generate_contextual_suggestions(
        self,
        message: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Genera sugerencias contextuales para el usuario"""
        suggestions = []
        
        try:
            # Sugerencias basadas en el análisis del mensaje
            if analysis.get("contains_questions", False):
                suggestions.append("Try asking specific questions about your resources")
            
            if analysis.get("resource_mentions"):
                suggestions.append("I can help you work with those specific resources")
            
            if analysis.get("complexity_score", 0.0) > 0.7:
                suggestions.append("Consider breaking this down into smaller steps")
            
            # Sugerencias basadas en el contexto
            if context.get("previous_mode"):
                suggestions.append(f"You were in {context['previous_mode']} mode. Want to continue?")
            
            if context.get("available_resources"):
                resource_count = len(context["available_resources"])
                suggestions.append(f"You have {resource_count} resources available to work with")
            
            # Sugerencias generales
            suggestions.extend([
                "Use 'explore' to see what's available",
                "Use 'plan' to create specific actions",
                "Ask for help anytime with 'help' or '?'"
            ])
            
            # Limitar a 5 sugerencias
            return suggestions[:5]
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error generando sugerencias: {e}")
            return ["I'm here to help. What would you like to do?"]
    
    async def _record_fallback(
        self,
        message: str,
        fallback_type: FallbackType,
        result: Dict[str, Any],
        context: Dict[str, Any]
    ):
        """Registra el fallback para aprendizaje futuro"""
        try:
            fallback_record = {
                "message": message,
                "fallback_type": fallback_type.value,
                "response": result["response"],
                "confidence": result["confidence"],
                "context": context,
                "timestamp": datetime.now().isoformat(),
                "user_id": self.user_id
            }
            
            # Agregar al historial
            self.fallback_history.append(fallback_record)
            
            # Mantener solo los últimos N registros
            if len(self.fallback_history) > self.fallback_config["max_fallback_history"]:
                self.fallback_history = self.fallback_history[-self.fallback_config["max_fallback_history"]:]
            
            # TODO: Persistir en base de datos para análisis
            
            logger.debug(f"[SmartFallbackService] Fallback registrado: {fallback_type.value}")
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error registrando fallback: {e}")
    
    def _get_emergency_fallback(self, fallback_type: FallbackType) -> Dict[str, Any]:
        """Proporciona fallback de emergencia cuando todo falla"""
        emergency_fallbacks = {
            FallbackType.MODE_AMBIGUOUS: {
                "response": "I'm not sure what you want to do. Would you like me to show your resources or help you create a plan?",
                "confidence": "low",
                "suggestions": ["Show my resources", "Create a plan", "Help me get started"]
            },
            FallbackType.DETECTION_FAILED: {
                "response": "I'm having trouble understanding. Let me help you explore or work on something specific.",
                "confidence": "low",
                "suggestions": ["Explore resources", "Work on specific task", "Get help"]
            },
            FallbackType.SYSTEM_ERROR: {
                "response": "Something went wrong. I'm here to help - what would you like to do?",
                "confidence": "low",
                "suggestions": ["Try again", "Show resources", "Get help"]
            }
        }
        
        fallback = emergency_fallbacks.get(fallback_type, emergency_fallbacks[FallbackType.SYSTEM_ERROR])
        
        return {
            "fallback_type": fallback_type.value,
            "response": fallback["response"],
            "confidence": fallback["confidence"],
            "suggestions": fallback["suggestions"],
            "context_analysis": {},
            "processing_time_ms": 0,
            "timestamp": datetime.now().isoformat(),
            "emergency": True
        }
    
    async def learn_from_feedback(
        self,
        fallback_id: str,
        user_feedback: str,
        was_helpful: bool
    ):
        """Aprende del feedback del usuario sobre un fallback"""
        try:
            if not self.fallback_config["learning_enabled"]:
                return
            
            # TODO: Implementar aprendizaje basado en feedback
            # Por ahora, solo logging
            
            logger.info(f"[SmartFallbackService] Feedback recibido: {fallback_id} - {user_feedback} (útil: {was_helpful})")
            
        except Exception as e:
            logger.warning(f"[SmartFallbackService] ⚠️ Error procesando feedback: {e}")
    
    async def get_fallback_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de fallbacks"""
        try:
            if not self.fallback_history:
                return {"total_fallbacks": 0, "types": {}, "confidence_distribution": {}}
            
            # Contar por tipo
            type_counts = {}
            confidence_counts = {}
            
            for fallback in self.fallback_history:
                fallback_type = fallback["fallback_type"]
                confidence = fallback["confidence"]
                
                type_counts[fallback_type] = type_counts.get(fallback_type, 0) + 1
                confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
            
            return {
                "total_fallbacks": len(self.fallback_history),
                "types": type_counts,
                "confidence_distribution": confidence_counts,
                "recent_fallbacks": len([f for f in self.fallback_history if 
                    datetime.fromisoformat(f["timestamp"]) > datetime.now() - timedelta(hours=1)])
            }
            
        except Exception as e:
            logger.error(f"[SmartFallbackService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Limpia recursos del servicio"""
        try:
            # Limpiar historial antiguo
            cutoff_time = datetime.now() - timedelta(days=7)
            self.fallback_history = [
                f for f in self.fallback_history 
                if datetime.fromisoformat(f["timestamp"]) > cutoff_time
            ]
            
            logger.info(f"[SmartFallbackService] 🧹 Limpieza completada")
            
        except Exception as e:
            logger.error(f"[SmartFallbackService] ❌ Error en limpieza: {e}")


# Factory function para crear el servicio
async def create_smart_fallback_service(factory: ServiceFactory, user_id: str) -> SmartFallbackService:
    """Crea e inicializa el servicio de smart fallbacks"""
    service = SmartFallbackService(factory)
    await service.initialize(user_id)
    return service
