"""
🏭 Service Factory Refactorizado: Factory principal simplificado

Factory principal que coordina todas las sub-factories especializadas,
reemplazando el ServiceFactory monolítico de 400+ líneas.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import Request

from app.models.user_model import User
from app.core.factories.core_services_factory import CoreServicesFactory
from app.core.factories.ai_services_factory import AIServicesFactory
from app.core.factories.cache_services_factory import CacheServicesFactory
from app.core.factories.data_services_factory import DataServicesFactory
from app.core.factories.management_services_factory import ManagementServicesFactory
from app.core.factories.background_services_factory import BackgroundServicesFactory

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    🏭 Service Factory Refactorizado (100 líneas)
    
    Coordina todas las sub-factories especializadas:
    - Core Services (DB, Auth, Config)
    - AI Services (Agents, Mode Detection)
    - Cache Services (Response, Redis, Schema)
    - Data Services (Database, App, Strategy)
    - Management Services (User, Org, Agent)
    - Background Services (Jobs, Scheduler, Queue)
    """
    
    def __init__(self, request: Request, user: User):
        """
        Inicializa el Service Factory refactorizado
        
        Args:
            request: Request de FastAPI
            user: Usuario autenticado
        """
        self.request = request
        self.user = user
        
        # Inicializar todas las sub-factories
        logger.info(f"[ServiceFactory] 🚀 Inicializando sub-factories para usuario {user.id}")
        
        try:
            self.core = CoreServicesFactory(self)
            self.ai = AIServicesFactory(self)
            self.cache = CacheServicesFactory(self)
            self.data = DataServicesFactory(self)
            self.management = ManagementServicesFactory(self)
            self.background = BackgroundServicesFactory(self)
            
            logger.info(f"[ServiceFactory] ✅ Todas las sub-factories inicializadas correctamente")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error inicializando sub-factories: {e}")
            raise
    
    # ─────────────────────────────────────────────
    #   🔧 CORE SERVICES (Delegación a CoreServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_database_service(self):
        """Obtiene el servicio de base de datos"""
        return self.core.get_database_service()
    
    def get_auth_service(self):
        """Obtiene el servicio de autenticación"""
        return self.core.get_auth_service()
    
    def get_config_service(self):
        """Obtiene el servicio de configuración"""
        return self.core.get_config_service()
    
    def get_session_service(self):
        """Obtiene el servicio de sesión"""
        return self.core.get_session_service()
    
    def get_ws_emitter(self):
        """Obtiene el emisor de WebSocket"""
        return self.core.get_ws_emitter()
    
    def get_openai_service(self):
        """Obtiene el servicio de OpenAI"""
        return self.core.get_openai_service()
    
    # ─────────────────────────────────────────────
    #   🧠 AI SERVICES (Delegación a AIServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_agent_service(self):
        """Obtiene el servicio de gestión de agentes"""
        return self.ai.get_agent_service()
    
    def get_mode_detection_service(self):
        """Obtiene el servicio de detección de modo"""
        return self.ai.get_mode_detection_service()
    
    def get_mode_transition_service(self):
        """Obtiene el servicio de transiciones de modo"""
        return self.ai.get_mode_transition_service()
    
    def get_mode_transition_orchestrator(self):
        """Obtiene el orquestador de transiciones de modo"""
        return self.ai.get_mode_transition_orchestrator()
    
    def get_agent_router_service(self):
        """Obtiene el servicio de enrutamiento de agentes"""
        return self.ai.get_agent_router_service()
    
    def get_smart_ai_service(self):
        """Obtiene el servicio de Smart AI"""
        return self.ai.get_smart_ai_service()
    
    def get_intent_classifier_service(self):
        """Obtiene el servicio de clasificación de intenciones"""
        return self.ai.get_intent_classifier_service()
    
    def get_smart_rephrase_service(self):
        """Obtiene el servicio de rephrase inteligente"""
        return self.ai.get_smart_rephrase_service()
    
    def get_execution_planner_service(self):
        """Obtiene el servicio de planificación de ejecución"""
        return self.ai.get_execution_planner_service()
    
    def get_mode_detection_logger(self):
        """Obtiene el logger de detección de modo"""
        return self.ai.get_mode_detection_logger()
    
    def get_prompt_builder_service(self):
        """Obtiene el servicio de construcción de prompts"""
        return self.ai.get_prompt_builder_service()
    
    def get_resource_priority_service(self):
        """Obtiene el servicio de priorización de recursos"""
        return self.ai.get_resource_priority_service()
    
    def get_mode_indicator_service(self):
        """Obtiene el servicio de indicadores de modo"""
        return self.ai.get_mode_indicator_service()
    
    # ─────────────────────────────────────────────
    #   🚀 FASE 7: PRE-CARGA INTELIGENTE Y UX (Delegación a AIServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_intelligent_preload_service(self):
        """Obtiene el servicio de pre-carga inteligente"""
        return self.ai.get_intelligent_preload_service()
    
    def get_smart_fallback_service(self):
        """Obtiene el servicio de smart fallbacks"""
        return self.ai.get_smart_fallback_service()
    
    def get_performance_monitoring_service(self):
        """Obtiene el servicio de monitoreo de performance"""
        return self.ai.get_performance_monitoring_service()
    
    def get_user_experience_service(self):
        """Obtiene el servicio de experiencia de usuario"""
        return self.ai.get_user_experience_service()
    
    # ─────────────────────────────────────────────
    #   ⚡ CACHE SERVICES (Delegación a CacheServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_response_cache_service(self):
        """Obtiene el servicio de cache de respuestas"""
        return self.cache.get_response_cache_service()
    
    def get_response_pre_generation_service(self):
        """Obtiene el servicio de pre-generación de respuestas"""
        return self.cache.get_response_pre_generation_service()
    
    def get_instant_response_service(self):
        """Obtiene el servicio de respuestas instantáneas"""
        return self.cache.get_instant_response_service()
    
    def get_redis_schema_cache(self):
        """Obtiene el cache de Redis para esquemas"""
        return self.cache.get_redis_schema_cache()
    
    def get_detailed_schema_cache_service(self):
        """Obtiene el servicio de cache de esquemas detallados"""
        return self.cache.get_detailed_schema_cache_service()
    
    def get_schema_refresh_service(self):
        """Obtiene el servicio de refresco de esquemas"""
        return self.cache.get_schema_refresh_service()
    
    def get_schema_maintenance_service(self):
        """Obtiene el servicio de mantenimiento de esquemas"""
        return self.cache.get_schema_maintenance_service()
    
    # ─────────────────────────────────────────────
    #   🧠 FASE 8: CUSTOM SYSTEM PROMPTS INTELIGENTES
    # ─────────────────────────────────────────────
    
    def get_prompt_builder_service(self):
        """Obtiene el servicio de construcción de prompts"""
        return self.ai.get_prompt_builder_service()
    
    def get_premium_prompt_service(self):
        """Obtiene el servicio de prompts premium"""
        return self.ai.get_premium_prompt_service()
    
    def get_pattern_learning_service(self):
        """Obtiene el servicio de aprendizaje de patrones"""
        return self.ai.get_pattern_learning_service()
    
    # ─────────────────────────────────────────────
    #   📊 DATA SERVICES (Delegación a DataServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_app_service(self):
        """Obtiene el servicio de aplicaciones"""
        return self.data.get_app_service()
    
    def get_strategy_service(self):
        """Obtiene el servicio de estrategias"""
        return self.data.get_strategy_service()
    
    def get_integration_service(self):
        """Obtiene el servicio de integraciones"""
        return self.data.get_integration_service()
    
    def get_api_cache_service(self):
        """Obtiene el servicio de cache de APIs"""
        return self.data.get_api_cache_service()
    
    def get_api_generation_service(self):
        """Obtiene el servicio de generación de APIs"""
        return self.data.get_api_generation_service()
    
    # ─────────────────────────────────────────────
    #   👥 MANAGEMENT SERVICES (Delegación a ManagementServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_user_service(self):
        """Obtiene el servicio de gestión de usuarios"""
        return self.management.get_user_service()
    
    def get_organization_service(self):
        """Obtiene el servicio de gestión de organizaciones"""
        return self.management.get_organization_service()
    
    def get_permission_service(self):
        """Obtiene el servicio de gestión de permisos"""
        return self.management.get_permission_service()
    
    def get_role_service(self):
        """Obtiene el servicio de gestión de roles"""
        return self.management.get_role_service()
    
    def get_audit_service(self):
        """Obtiene el servicio de auditoría"""
        return self.management.get_audit_service()
    
    def get_schema_performance_service(self):
        """Obtiene el servicio de performance de schemas"""
        return self.management.get_schema_performance_service()
    
    # ─────────────────────────────────────────────
    #   🔄 BACKGROUND SERVICES (Delegación a BackgroundServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_background_task_service(self):
        """Obtiene el servicio de tareas en background"""
        return self.background.get_background_task_service()
    
    def get_scheduler_service(self):
        """Obtiene el servicio de programación de tareas"""
        return self.background.get_scheduler_service()
    
    def get_queue_service(self):
        """Obtiene el servicio de gestión de colas"""
        return self.background.get_queue_service()
    
    def get_worker_service(self):
        """Obtiene el servicio de workers"""
        return self.background.get_worker_service()
    
    def get_notification_service(self):
        """Obtiene el servicio de notificaciones"""
        return self.background.get_notification_service()
    
    def get_email_service(self):
        """Obtiene el servicio de email"""
        return self.background.get_email_service()
    
    # ─────────────────────────────────────────────
    #   📊 MÉTODOS DE INFORMACIÓN Y DIAGNÓSTICO
    # ─────────────────────────────────────────────
    
    def get_factory_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado completo de todas las factories
        
        Returns:
            Diccionario con información de todas las factories
        """
        try:
            return {
                "main_factory": {
                    "class": self.__class__.__name__,
                    "user_id": str(self.user.id),
                    "request_available": self.request is not None
                },
                "sub_factories": {
                    "core": self.core.get_factory_info(),
                    "ai": self.ai.get_factory_info(),
                    "cache": self.cache.get_factory_info(),
                    "data": self.data.get_factory_info(),
                    "management": self.management.get_factory_info(),
                    "background": self.background.get_factory_info()
                }
            }
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo estado: {e}")
            return {"error": str(e)}
    
    def clear_all_caches(self):
        """Limpia el cache de todas las sub-factories"""
        try:
            logger.info("[ServiceFactory] 🧹 Limpiando cache de todas las factories")
            
            self.core._clear_service_cache()
            self.ai._clear_service_cache()
            self.cache._clear_service_cache()
            self.data._clear_service_cache()
            self.management._clear_service_cache()
            self.background._clear_service_cache()
            
            logger.info("[ServiceFactory] ✅ Cache de todas las factories limpiado")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error limpiando cache: {e}")
    
    def reset_all_factories(self):
        """Resetea todas las sub-factories"""
        try:
            logger.info("[ServiceFactory] 🔄 Reseteando todas las factories")
            
            self.core._reset_factory()
            self.ai._reset_factory()
            self.cache._reset_factory()
            self.data._reset_factory()
            self.management._reset_factory()
            self.background._reset_factory()
            
            logger.info("[ServiceFactory] ✅ Todas las factories reseteadas")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error reseteando factories: {e}")
    
    def __repr__(self):
        """Representación string del ServiceFactory"""
        return f"<ServiceFactory(user_id={self.user.id}, sub_factories=6)>"
    
    def __str__(self):
        """String representation del ServiceFactory"""
        return f"ServiceFactory for user {self.user.id} with 6 sub-factories"
