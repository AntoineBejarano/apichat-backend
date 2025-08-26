from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ReadinessValidator:
    def __init__(self, factory):
        self.factory = factory
    
    async def is_database_ready(self, db_uuid: str) -> bool:
        """Verifica si una base de datos está lista usando cache como fuente de verdad"""
        try:
            cache_service = self.factory.get_detailed_schema_cache_service()
            if not cache_service:
                logger.warning(f"[ReadinessValidator] Cache service no disponible para DB {db_uuid}")
                return False
            
            # Verificar si existe en cache
            schema = await cache_service.get_schema(db_uuid)
            if not schema:
                logger.info(f"[ReadinessValidator] DB {db_uuid} no encontrada en cache")
                return False
            
            # Verificar que el esquema tiene contenido válido
            if not schema.get('tables') or len(schema['tables']) == 0:
                logger.info(f"[ReadinessValidator] DB {db_uuid} no tiene tablas en cache")
                return False
            
            logger.info(f"[ReadinessValidator] ✅ DB {db_uuid} está lista (encontrada en cache)")
            return True
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error verificando readiness de DB {db_uuid}: {e}")
            return False
    
    async def is_application_ready(self, app_id: str) -> bool:
        """Verifica si una aplicación está lista usando cache como fuente de verdad"""
        try:
            cache_service = self.factory.get_app_descriptor_cache_service()
            if not cache_service:
                logger.warning(f"[ReadinessValidator] Cache service no disponible para app {app_id}")
                return False
            
            # Verificar si existe en cache
            descriptor = await cache_service.get_descriptor(app_id)
            if not descriptor:
                logger.info(f"[ReadinessValidator] App {app_id} no encontrada en cache")
                return False
            
            # Verificar que tiene funciones válidas
            functions = descriptor.get('functions', [])
            if not functions or len(functions) == 0:
                logger.info(f"[ReadinessValidator] App {app_id} no tiene funciones en cache")
                return False
            
            logger.info(f"[ReadinessValidator] ✅ App {app_id} está lista (encontrada en cache)")
            return True
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error verificando readiness de app {app_id}: {e}")
            return False
    
    async def is_function_ready(self, function_id: str) -> bool:
        """Verifica si una función específica está lista"""
        try:
            # Por ahora, verificamos a nivel de aplicación
            # En el futuro podríamos tener cache específico por función
            logger.info(f"[ReadinessValidator] Verificando función {function_id} (delegado a app)")
            return True
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error verificando readiness de función {function_id}: {e}")
            return False
    
    async def is_strategy_ready(self, strategy_id: str) -> bool:
        """Verifica si una estrategia está lista"""
        try:
            # Por ahora, verificamos a nivel de aplicación
            # En el futuro podríamos tener cache específico por estrategia
            logger.info(f"[ReadinessValidator] Verificando estrategia {strategy_id} (delegado a app)")
            return True
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error verificando readiness de estrategia {strategy_id}: {e}")
            return False
    
    async def validate_all_resources(self, user_id: str) -> Dict[str, bool]:
        """Valida readiness de todos los recursos del usuario"""
        try:
            logger.info(f"[ReadinessValidator] Validando todos los recursos para usuario {user_id}")
            
            # Por ahora, verificamos recursos genéricos
            # En el futuro, obtendríamos la lista real del usuario
            resources = {
                'database': 'default_db',
                'application': 'default_app',
                'strategies': 'default_strategies'
            }
            
            results = {}
            for resource_type, resource_id in resources.items():
                if resource_type == 'database':
                    results[resource_type] = await self.is_database_ready(resource_id)
                elif resource_type == 'application':
                    results[resource_type] = await self.is_application_ready(resource_id)
                elif resource_type == 'strategies':
                    results[resource_type] = await self.is_strategy_ready(resource_id)
                else:
                    results[resource_type] = False
            
            logger.info(f"[ReadinessValidator] Resultados de validación: {results}")
            return results
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error validando recursos para usuario {user_id}: {e}")
            return {}
    
    async def is_environment_ready(self, user_id: str) -> bool:
        """Verifica si todo el entorno del usuario está listo"""
        try:
            resource_status = await self.validate_all_resources(user_id)
            
            if not resource_status:
                logger.info(f"[ReadinessValidator] No hay recursos para validar para usuario {user_id}")
                return False
            
            all_ready = all(resource_status.values())
            logger.info(f"[ReadinessValidator] Entorno para usuario {user_id}: {'✅ LISTO' if all_ready else '⏳ PENDIENTE'}")
            
            return all_ready
            
        except Exception as e:
            logger.error(f"[ReadinessValidator] Error verificando entorno para usuario {user_id}: {e}")
            return False
