"""
🏭 AI Services Factory: Factory para servicios de IA y agentes

Maneja servicios relacionados con:
- Agent Service
- Mode Detection Service
- Mode Transition Service
- Agent Router Service
- Smart AI Integration
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class AIServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios de IA y agentes
    
    Responsabilidades:
    - Gestión de agentes
    - Detección de modo
    - Transiciones de modo
    - Enrutamiento de agentes
    - Integración con Smart AI
    """
    
    def get_agent_service(self):
        """Obtiene el servicio de gestión de agentes"""
        try:
            from app.services.management.agent_service import AgentService
            return self._get_or_create_service(AgentService, "agent")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo AgentService: {e}")
            return None
    
    def get_mode_detection_service(self):
        """Obtiene el servicio de detección de modo"""
        try:
            from app.services.ai.mode_detection_service import ModeDetectionService
            return self._get_or_create_service(ModeDetectionService, "mode_detection")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ModeDetectionService: {e}")
            return None
    
    def get_mode_transition_service(self):
        """Obtiene el servicio de transiciones de modo"""
        try:
            from app.services.ai.mode_transition_service import ModeTransitionService
            return self._get_or_create_service(ModeTransitionService, "mode_transition")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ModeTransitionService: {e}")
            return None
    
    def get_mode_transition_orchestrator(self):
        """Obtiene el orquestador de transiciones de modo"""
        try:
            from app.services.ai.mode_transition_orchestrator import ModeTransitionOrchestrator
            return self._get_or_create_service(ModeTransitionOrchestrator, "mode_transition_orchestrator")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ModeTransitionOrchestrator: {e}")
            return None
    
    def get_agent_router_service(self):
        """Obtiene el servicio de enrutamiento de agentes"""
        try:
            from app.services.ai.agent_router_service import AgentRouterService
            return self._get_or_create_service(AgentRouterService, "agent_router")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo AgentRouterService: {e}")
            return None
    
    def get_smart_ai_service(self):
        """Obtiene el servicio de Smart AI"""
        try:
            from app.services.ai.smart_ai_service import SmartAIService
            return self._get_or_create_service(SmartAIService, "smart_ai")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo SmartAIService: {e}")
            return None
    
    def get_intent_classifier_service(self):
        """Obtiene el servicio de clasificación de intenciones"""
        try:
            from app.services.ai.intent_classifier_service import IntentClassifierService
            return self._get_or_create_service(IntentClassifierService, "intent_classifier")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo IntentClassifierService: {e}")
            return None
    
    def get_smart_rephrase_service(self):
        """Obtiene el servicio de rephrase inteligente"""
        try:
            from app.services.ai.smart_rephrase_service import SmartRephraseService
            return self._get_or_create_service(SmartRephraseService, "smart_rephrase")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo SmartRephraseService: {e}")
            return None
    
    def get_execution_planner_service(self):
        """Obtiene el servicio de planificación de ejecución"""
        try:
            from app.services.ai.execution_planner_service import ExecutionPlannerService
            return self._get_or_create_service(ExecutionPlannerService, "execution_planner")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ExecutionPlannerService: {e}")
            return None
    
    def get_mode_detection_logger(self):
        """Obtiene el logger de detección de modo"""
        try:
            from app.services.monitoring.mode_detection_logger import ModeDetectionLogger
            return self._get_or_create_service(ModeDetectionLogger, "mode_detection_logger")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ModeDetectionLogger: {e}")
            return None
    
    def get_prompt_builder_service(self):
        """Obtiene el servicio de construcción de prompts"""
        try:
            from app.services.ai.prompt_builder_service import PromptBuilderService
            return self._get_or_create_service(PromptBuilderService, "prompt_builder")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo PromptBuilderService: {e}")
            return None
    
    def get_resource_priority_service(self):
        """Obtiene el servicio de priorización de recursos"""
        try:
            from app.services.ai.resource_priority_service import ResourcePriorityService
            return self._get_or_create_service(ResourcePriorityService, "resource_priority")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ResourcePriorityService: {e}")
            return None
    
    def get_mode_indicator_service(self):
        """Obtiene el servicio de indicadores de modo"""
        try:
            from app.services.ai.mode_indicator_service import ModeIndicatorService
            return self._get_or_create_service(ModeIndicatorService, "mode_indicator")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ModeIndicatorService: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   🚀 FASE 7: PRE-CARGA INTELIGENTE Y UX
    # ─────────────────────────────────────────────
    
    def get_intelligent_preload_service(self):
        """Obtiene el servicio de pre-carga inteligente"""
        try:
            from app.services.background.intelligent_preload_service import IntelligentPreloadService
            return self._get_or_create_service(IntelligentPreloadService, "intelligent_preload")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo IntelligentPreloadService: {e}")
            return None
    
    def get_smart_fallback_service(self):
        """Obtiene el servicio de smart fallbacks"""
        try:
            from app.services.ai.smart_fallback_service import SmartFallbackService
            return self._get_or_create_service(SmartFallbackService, "smart_fallback")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo SmartFallbackService: {e}")
            return None
    
    def get_performance_monitoring_service(self):
        """Obtiene el servicio de monitoreo de performance"""
        try:
            from app.services.monitoring.performance_monitoring_service import PerformanceMonitoringService
            return self._get_or_create_service(PerformanceMonitoringService, "performance_monitoring")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo PerformanceMonitoringService: {e}")
            return None
    
    def get_user_experience_service(self):
        """Obtiene el servicio de experiencia de usuario"""
        try:
            from app.services.ai.user_experience_service import UserExperienceService
            return self._get_or_create_service(UserExperienceService, "user_experience")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo UserExperienceService: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   🧠 FASE 8: CUSTOM SYSTEM PROMPTS INTELIGENTES
    # ─────────────────────────────────────────────
    
    def get_premium_prompt_service(self):
        """Obtiene el servicio de prompts premium"""
        try:
            from app.services.ai.premium_prompt_service import PremiumPromptService
            return self._get_or_create_service(PremiumPromptService, "premium_prompt")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo PremiumPromptService: {e}")
            return None
    
    def get_pattern_learning_service(self):
        """Obtiene el servicio de aprendizaje de patrones"""
        try:
            from app.services.ai.pattern_learning_service import PatternLearningService
            return self._get_or_create_service(PatternLearningService, "pattern_learning")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo PatternLearningService: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   🎯 FASE 9: PRIORIZACIÓN DE RECURSOS Y FALLBACK INTELIGENTE
    # ─────────────────────────────────────────────
    
    def get_resource_priority_service(self):
        """Obtiene el servicio de priorización de recursos"""
        try:
            from app.services.ai.resource_priority_service import ResourcePriorityService
            return self._get_or_create_service(ResourcePriorityService, "resource_priority")
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo ResourcePriorityService: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory de IA"""
        try:
            return {
                "factory_type": "ai_services",
                "available_services": [
                    "agent_service",
                    "mode_detection_service",
                    "mode_transition_service", 
                    "mode_transition_orchestrator",
                    "agent_router_service",
                    "smart_ai_service",
                    "intent_classifier_service",
                    "smart_rephrase_service",
                    "execution_planner_service",
                    "mode_detection_logger",
                    "prompt_builder_service",
                    "resource_priority_service",
                    "mode_indicator_service",
                    # FASE 7: Pre-carga inteligente y UX
                    "intelligent_preload_service",
                    "smart_fallback_service",
                    "performance_monitoring_service",
                    "user_experience_service",
                    # FASE 8: Custom System Prompts Inteligentes
                    "premium_prompt_service",
                    "pattern_learning_service",
                    # FASE 9: Priorización de Recursos y Fallback Inteligente
                    "resource_priority_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[AIServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
