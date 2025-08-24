"""
🏭 Data Services Factory: Factory para servicios de datos

Maneja servicios relacionados con:
- Database Service
- App Service
- Strategy Service
- Integration Service
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class DataServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios de datos
    
    Responsabilidades:
    - Servicios de base de datos
    - Servicios de aplicaciones
    - Servicios de estrategias
    - Servicios de integración
    """
    
    def get_database_service(self):
        """Obtiene el servicio de base de datos"""
        try:
            from app.services.data.database_service import DatabaseService
            return self._get_or_create_service(DatabaseService, "database")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo DatabaseService: {e}")
            return None
    
    def get_app_service(self):
        """Obtiene el servicio de aplicaciones"""
        try:
            from app.services.management.app_service import AppService
            return self._get_or_create_service(AppService, "app")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo AppService: {e}")
            return None
    
    def get_strategy_service(self):
        """Obtiene el servicio de estrategias"""
        try:
            from app.services.management.strategy_service import StrategyService
            return self._get_or_create_service(StrategyService, "strategy")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo StrategyService: {e}")
            return None
    
    def get_integration_service(self):
        """Obtiene el servicio de integraciones"""
        try:
            from app.services.integration.integration_service import IntegrationService
            return self._get_or_create_service(IntegrationService, "integration")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo IntegrationService: {e}")
            return None
    
    def get_api_cache_service(self):
        """Obtiene el servicio de cache de APIs"""
        try:
            from app.services.cache.api_cache_service import APICacheService
            return self._get_or_create_service(APICacheService, "api_cache")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo APICacheService: {e}")
            return None
    
    def get_api_generation_service(self):
        """Obtiene el servicio de generación de APIs"""
        try:
            from app.services.background.api_generation_service import APIGenerationService
            return self._get_or_create_service(APIGenerationService, "api_generation")
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo APIGenerationService: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory de datos"""
        try:
            return {
                "factory_type": "data_services",
                "available_services": [
                    "database_service",
                    "app_service",
                    "strategy_service",
                    "integration_service",
                    "api_cache_service",
                    "api_generation_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[DataServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
