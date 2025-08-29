"""
🏭 Background Services Factory: Factory para servicios en background

Maneja servicios relacionados con:
- Background Jobs
- Scheduled Tasks
- Async Processing
- Queue Management
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class BackgroundServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios en background
    
    Responsabilidades:
    - Trabajos en background
    - Tareas programadas
    - Procesamiento asíncrono
    - Gestión de colas
    """
    
    def get_background_task_service(self):
        """Obtiene el servicio de tareas en background"""
        try:
            from app.services.background.background_task_service import BackgroundTaskService
            return self._get_or_create_service(BackgroundTaskService, "background_task")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo BackgroundTaskService: {e}")
            return None
    
    def get_scheduler_service(self):
        """Obtiene el servicio de programación de tareas"""
        try:
            from app.services.background.scheduler_service import SchedulerService
            return self._get_or_create_service(SchedulerService, "scheduler")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SchedulerService: {e}")
            return None
    
    def get_queue_service(self):
        """Obtiene el servicio de gestión de colas"""
        try:
            from app.services.background.queue_service import QueueService
            return self._get_or_create_service(QueueService, "queue")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo QueueService: {e}")
            return None
    
    def get_worker_service(self):
        """Obtiene el servicio de workers"""
        try:
            from app.services.background.worker_service import WorkerService
            return self._get_or_create_service(WorkerService, "worker")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo WorkerService: {e}")
            return None
    
    def get_notification_service(self):
        """Obtiene el servicio de notificaciones"""
        try:
            from app.services.notification.notification_service import NotificationService
            return self._get_or_create_service(NotificationService, "notification")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo NotificationService: {e}")
            return None
    
    def get_email_service(self):
        """Obtiene el servicio de email"""
        try:
            from app.services.notification.email_service import EmailService
            return self._get_or_create_service(EmailService, "email")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo EmailService: {e}")
            return None
    
    def get_warmup_engine(self):
        """Obtiene el motor de warmup"""
        try:
            from app.services.background.warmup_engine import WarmupEngine
            return self._get_or_create_service(WarmupEngine, "warmup_engine")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo WarmupEngine: {e}")
            return None
    
    def get_resource_preparation_service(self):
        """Obtiene el servicio de preparación de recursos"""
        try:
            from app.services.background.resource_preparation_service import ResourcePreparationService
            return self._get_or_create_service(ResourcePreparationService, "resource_preparation")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo ResourcePreparationService: {e}")
            return None
    
    def get_schema_pipeline_service(self):
        """🔧 FASE 1: Obtiene el servicio del pipeline de schema"""
        try:
            from app.services.background.schema_pipeline_service import SchemaPipelineService
            return self._get_or_create_service(SchemaPipelineService, "schema_pipeline")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SchemaPipelineService: {e}")
            return None
    
    def get_schema_graph_service(self):
        """🔧 FASE 2: Obtiene el servicio del grafo de schema"""
        try:
            from app.services.background.schema_graph_service import SchemaGraphService
            return self._get_or_create_service(SchemaGraphService, "schema_graph")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SchemaGraphService: {e}")
            return None
    
    # 🔧 FASE 5: Servicios del Chat Inteligente
    def get_context_resolver_service(self):
        """🔧 FASE 5: Obtiene el servicio de resolución de contexto"""
        try:
            from app.services.chat.context_resolver_service import ContextResolverService
            return self._get_or_create_service(ContextResolverService, "context_resolver")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo ContextResolverService: {e}")
            return None
    
    def get_grounding_service(self):
        """🔧 FASE 5: Obtiene el servicio de grounding"""
        try:
            from app.services.chat.grounding_service import GroundingService
            return self._get_or_create_service(GroundingService, "grounding")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo GroundingService: {e}")
            return None
    
    def get_planner_service(self):
        """🔧 FASE 5: Obtiene el servicio de planificación"""
        try:
            from app.services.chat.planner_service import PlannerService
            return self._get_or_create_service(PlannerService, "planner")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo PlannerService: {e}")
            return None
    
    def get_sql_generator_service(self):
        """🔧 FASE 5: Obtiene el servicio de generación SQL"""
        try:
            from app.services.chat.sql_generator_service import SQLGeneratorService
            return self._get_or_create_service(SQLGeneratorService, "sql_generator")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SQLGeneratorService: {e}")
            return None
    
    def get_sql_validator_service(self):
        """🔧 FASE 5: Obtiene el servicio de validación SQL"""
        try:
            from app.services.chat.sql_validator_service import SQLValidatorService
            return self._get_or_create_service(SQLValidatorService, "sql_validator")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SQLValidatorService: {e}")
            return None
    
    def get_sql_executor_service(self):
        """🔧 FASE 5: Obtiene el servicio de ejecución SQL"""
        try:
            from app.services.chat.sql_executor_service import SQLExecutorService
            return self._get_or_create_service(SQLExecutorService, "sql_executor")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SQLExecutorService: {e}")
            return None
    
    def get_explanation_service(self):
        """🔧 FASE 5: Obtiene el servicio de explicación"""
        try:
            from app.services.chat.explanation_service import ExplanationService
            return self._get_or_create_service(ExplanationService, "explanation")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo ExplanationService: {e}")
            return None
    
            # 🔧 FASE 4: Vector Store Agnóstico
        def get_vector_service(self):
            """🔧 FASE 4: Obtiene el servicio de vector store agnóstico"""
            try:
                from app.services.vector.vector_service import VectorService
                return self._get_or_create_service(VectorService, "vector")
            except Exception as e:
                logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo VectorService: {e}")
                return None
        
        # 🛡️ FASE 7: Seguridad, Políticas y Observabilidad
        def get_sql_policy_service(self):
            """🛡️ FASE 7: Obtiene el servicio de políticas SQL"""
            try:
                from app.services.security.sql_policy_service import SQLPolicyService
                return self._get_or_create_service(SQLPolicyService, "sql_policy")
            except Exception as e:
                logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo SQLPolicyService: {e}")
                return None
        
        def get_structured_logger_service(self):
            """📊 FASE 7: Obtiene el servicio de logs estructurados"""
            try:
                from app.services.observability.structured_logger_service import StructuredLoggerService
                return self._get_or_create_service(StructuredLoggerService, "structured_logger")
            except Exception as e:
                logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo StructuredLoggerService: {e}")
                return None
        
        def get_user_message_service(self):
            """💬 FASE 7: Obtiene el servicio de mensajes estándar"""
            try:
                from app.services.security.user_message_service import UserMessageService
                return self._get_or_create_service(UserMessageService, "user_message")
            except Exception as e:
                logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo UserMessageService: {e}")
                return None
        
        # 📝 FASE 8: Sistema de Prompts Configurable
        def get_prompt_template_service(self):
            """📝 FASE 8: Obtiene el servicio de templates de prompts"""
            try:
                from app.services.prompts.prompt_template_service import PromptTemplateService
                return self._get_or_create_service(PromptTemplateService, "prompt_template")
            except Exception as e:
                logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo PromptTemplateService: {e}")
                return None
    
    def get_upload_trigger_service(self):
        """Obtiene el servicio de triggers automáticos tras upload"""
        try:
            from app.services.background.resource_upload_trigger import ResourceUploadTrigger
            return self._get_or_create_service(ResourceUploadTrigger, "upload_trigger")
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo ResourceUploadTrigger: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory de background"""
        try:
            return {
                "factory_type": "background_services",
                "available_services": [
                    "background_task_service",
                    "scheduler_service",
                    "queue_service",
                    "worker_service",
                    "notification_service",
                    "email_service",
                    "warmup_engine",
                    "resource_preparation_service",
                    "upload_trigger_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
