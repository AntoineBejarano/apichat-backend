"""
🏭 Core Services Factory: Factory para servicios core del sistema

Maneja servicios fundamentales como:
- Database Service
- Authentication Service  
- Configuration Service
- Session Service
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class CoreServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios core del sistema
    
    Responsabilidades:
    - Servicios de base de datos
    - Servicios de autenticación
    - Servicios de configuración
    - Servicios de sesión
    """
    
    def get_database_service(self):
        """Obtiene el servicio de base de datos"""
        try:
            from app.services.data.database_service import DatabaseService
            return self._get_or_create_service(DatabaseService, "database")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo DatabaseService: {e}")
            return None
    
    def get_auth_service(self):
        """Obtiene el servicio de autenticación"""
        try:
            from app.services.auth.auth_service import AuthService
            return self._get_or_create_service(AuthService, "auth")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo AuthService: {e}")
            return None
    
    def get_config_service(self):
        """Obtiene el servicio de configuración"""
        try:
            from app.services.config.config_service import ConfigService
            return self._get_or_create_service(ConfigService, "config")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo ConfigService: {e}")
            return None
    
    def get_session_service(self):
        """Obtiene el servicio de sesión"""
        try:
            from app.services.auth.session_service import SessionService
            return self._get_or_create_service(SessionService, "session")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo SessionService: {e}")
            return None
    
    def get_ws_emitter(self):
        """Obtiene el emisor de WebSocket"""
        try:
            from app.services.common.ws_emitter import WSEmitter
            return self._get_or_create_service(WSEmitter, "ws_emitter")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo WSEmitter: {e}")
            return None
    
    def get_openai_service(self):
        """Obtiene el servicio de OpenAI"""
        try:
            from app.services.ai.openai_service import OpenAIService
            return self._get_or_create_service(OpenAIService, "openai")
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo OpenAIService: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory core"""
        try:
            return {
                "factory_type": "core_services",
                "available_services": [
                    "database_service",
                    "auth_service", 
                    "config_service",
                    "session_service",
                    "ws_emitter",
                    "openai_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[CoreServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
