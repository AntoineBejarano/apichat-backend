"""
🏭 Cache Services Factory: Factory para servicios de cache

Maneja servicios relacionados con:
- Response Cache Service
- Redis Cache Service
- Schema Cache Service
- Pre-generation Service
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class CacheServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios de cache
    
    Responsabilidades:
    - Cache de respuestas
    - Cache de Redis
    - Cache de esquemas
    - Pre-generación de respuestas
    """
    
    def get_response_cache_service(self):
        """Obtiene el servicio de cache de respuestas"""
        try:
            from app.services.cache.response_cache_service import ResponseCacheService
            return self._get_or_create_service(ResponseCacheService, "response_cache")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo ResponseCacheService: {e}")
            return None
    
    def get_response_pre_generation_service(self):
        """Obtiene el servicio de pre-generación de respuestas"""
        try:
            from app.services.background.response_pre_generation_service import ResponsePreGenerationService
            return self._get_or_create_service(ResponsePreGenerationService, "response_pre_generation")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo ResponsePreGenerationService: {e}")
            return None
    
    def get_instant_response_service(self):
        """Obtiene el servicio de respuestas instantáneas"""
        try:
            from app.services.ai.instant_response_service import InstantResponseService
            return self._get_or_create_service(InstantResponseService, "instant_response")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo InstantResponseService: {e}")
            return None
    
    def get_redis_schema_cache(self):
        """Obtiene el cache de Redis para esquemas"""
        try:
            from app.services.cache.redis_schema_cache import RedisSchemaCache
            # 🔧 FIX: RedisSchemaCache no toma argumentos en su constructor
            return self._get_or_create_service(RedisSchemaCache, "redis_schema_cache", use_factory=False)
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo RedisSchemaCache: {e}")
            return None
    
    def get_detailed_schema_cache_service(self):
        """Obtiene el servicio de cache de esquemas detallados"""
        try:
            from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
            return self._get_or_create_service(DetailedSchemaCacheService, "detailed_schema_cache")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo DetailedSchemaCacheService: {e}")
            return None
    
    def get_schema_refresh_service(self):
        """Obtiene el servicio de refresco de esquemas"""
        try:
            from app.services.context.schema_refresh_service import SchemaRefreshService
            return self._get_or_create_service(SchemaRefreshService, "schema_refresh")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo SchemaRefreshService: {e}")
            return None
    
    def get_schema_maintenance_service(self):
        """Obtiene el servicio de mantenimiento de esquemas"""
        try:
            from app.services.context.schema_maintenance_service import SchemaMaintenanceService
            return self._get_or_create_service(SchemaMaintenanceService, "schema_maintenance")
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo SchemaMaintenanceService: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory de cache"""
        try:
            return {
                "factory_type": "cache_services",
                "available_services": [
                    "response_cache_service",
                    "response_pre_generation_service",
                    "instant_response_service",
                    "redis_schema_cache",
                    "detailed_schema_cache_service",
                    "schema_refresh_service",
                    "schema_maintenance_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[CacheServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
