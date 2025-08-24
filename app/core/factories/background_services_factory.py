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
                    "email_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[BackgroundServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
