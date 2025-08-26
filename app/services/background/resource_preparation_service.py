from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

class ResourcePreparationService:
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry
        self.ws_emitter = None  # Se inicializa lazy
    
    def _get_ws_emitter(self):
        """Obtiene el WSEmitter de forma lazy"""
        if not self.ws_emitter:
            self.ws_emitter = self.factory.get_ws_emitter()
        return self.ws_emitter
    
    async def prepare_database(self, db_uuid: str, user_id: str = None) -> bool:
        """Prepara una base de datos para uso"""
        try:
            logger.info(f"[ResourcePreparationService] 🚀 Preparando base de datos {db_uuid}")
            
            # Marcar como "preparando"
            await self.readiness_registry.mark_resource_preparing('database', db_uuid)
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user_status(user_id, {
                    "type": "status",
                    "message": "🔍 Analizando tu base de datos...",
                    "resource": "database",
                    "resource_id": db_uuid,
                    "status": "preparing"
                })
            
            # Preparar usando cache service
            cache_service = self.factory.get_detailed_schema_cache_service()
            if not cache_service:
                logger.error(f"[ResourcePreparationService] Cache service no disponible para DB {db_uuid}")
                await self.readiness_registry.mark_resource_error('database', db_uuid, "Cache service no disponible")
                return False
            
            # Intentar obtener/refrescar el esquema
            schema = await cache_service.get_schema(db_uuid)
            if not schema:
                logger.warning(f"[ResourcePreparationService] No se pudo obtener esquema para DB {db_uuid}")
                await self.readiness_registry.mark_resource_error('database', db_uuid, "No se pudo obtener esquema")
                return False
            
            # Marcar como listo
            await self.readiness_registry.mark_resource_ready('database', db_uuid, {
                'prepared_at': datetime.now(),
                'schema_version': 'latest',
                'tables_count': len(schema.get('tables', []))
            })
            
            # Notificar completado
            if user_id:
                await self.notify_user_status(user_id, {
                    "type": "status",
                    "message": "✅ Base de datos lista para usar",
                    "resource": "database",
                    "resource_id": db_uuid,
                    "status": "ready"
                })
            
            logger.info(f"[ResourcePreparationService] ✅ Base de datos {db_uuid} preparada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"[ResourcePreparationService] ❌ Error preparando base de datos {db_uuid}: {e}")
            await self.readiness_registry.mark_resource_error('database', db_uuid, str(e))
            return False
    
    async def prepare_application(self, app_id: str, user_id: str = None) -> bool:
        """Prepara una aplicación para uso"""
        try:
            logger.info(f"[ResourcePreparationService] 🚀 Preparando aplicación {app_id}")
            
            # Marcar como "preparando"
            await self.readiness_registry.mark_resource_preparing('application', app_id)
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user_status(user_id, {
                    "type": "status",
                    "message": "🔍 Analizando tu aplicación...",
                    "resource": "application",
                    "resource_id": app_id,
                    "status": "preparing"
                })
            
            # Preparar usando cache service
            cache_service = self.factory.get_app_descriptor_cache_service()
            if not cache_service:
                logger.error(f"[ResourcePreparationService] Cache service no disponible para app {app_id}")
                await self.readiness_registry.mark_resource_error('application', app_id, "Cache service no disponible")
                return False
            
            # Intentar obtener/refrescar el descriptor
            descriptor = await cache_service.get_descriptor(app_id)
            if not descriptor:
                logger.warning(f"[ResourcePreparationService] No se pudo obtener descriptor para app {app_id}")
                await self.readiness_registry.mark_resource_error('application', app_id, "No se pudo obtener descriptor")
                return False
            
            # Marcar como listo
            await self.readiness_registry.mark_resource_ready('application', app_id, {
                'prepared_at': datetime.now(),
                'descriptor_version': 'latest',
                'functions_count': len(descriptor.get('functions', []))
            })
            
            # Notificar completado
            if user_id:
                await self.notify_user_status(user_id, {
                    "type": "status",
                    "message": "✅ Aplicación lista para usar",
                    "resource": "application",
                    "resource_id": app_id,
                    "status": "ready"
                })
            
            logger.info(f"[ResourcePreparationService] ✅ Aplicación {app_id} preparada exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"[ResourcePreparationService] ❌ Error preparando aplicación {app_id}: {e}")
            await self.readiness_registry.mark_resource_error('application', app_id, str(e))
            return False
    
    async def prepare_strategies(self, strategy_ids: List[str], user_id: str = None) -> bool:
        """Prepara estrategias para uso"""
        try:
            logger.info(f"[ResourcePreparationService] 🚀 Preparando {len(strategy_ids)} estrategias")
            
            # Marcar como "preparando"
            for strategy_id in strategy_ids:
                await self.readiness_registry.mark_resource_preparing('strategy', strategy_id)
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user_status(user_id, {
                    "type": "status",
                    "message": f"🔍 Procesando {len(strategy_ids)} estrategias...",
                    "resource": "strategies",
                    "resource_ids": strategy_ids,
                    "status": "preparing"
                })
            
            # Preparar usando strategy service
            strategy_service = self.factory.get_strategy_service()
            if not strategy_service:
                logger.error(f"[ResourcePreparationService] Strategy service no disponible")
                for strategy_id in strategy_ids:
                    await self.readiness_registry.mark_resource_error('strategy', strategy_id, "Strategy service no disponible")
                return False
            
            # Procesar cada estrategia
            success_count = 0
            for strategy_id in strategy_ids:
                try:
                    # Verificar que la estrategia existe
                    strategy = await strategy_service.get_strategy(strategy_id)
                    if not strategy:
                        logger.warning(f"[ResourcePreparationService] Estrategia {strategy_id} no encontrada")
                        await self.readiness_registry.mark_resource_error('strategy', strategy_id, "Estrategia no encontrada")
                        continue
                    
                    # Marcar como listo
                    await self.readiness_registry.mark_resource_ready('strategy', strategy_id, {
                        'prepared_at': datetime.now(),
                        'strategy_version': 'latest',
                        'steps_count': len(strategy.get('steps', []))
                    })
                    
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"[ResourcePreparationService] Error preparando estrategia {strategy_id}: {e}")
                    await self.readiness_registry.mark_resource_error('strategy', strategy_id, str(e))
            
            # Notificar completado
            if user_id:
                if success_count == len(strategy_ids):
                    await self.notify_user_status(user_id, {
                        "type": "status",
                        "message": f"✅ {success_count} estrategias listas para usar",
                        "resource": "strategies",
                        "status": "ready"
                    })
                else:
                    await self.notify_user_status(user_id, {
                        "type": "status",
                        "message": f"⚠️ {success_count}/{len(strategy_ids)} estrategias preparadas",
                        "resource": "strategies",
                        "status": "partial"
                    })
            
            logger.info(f"[ResourcePreparationService] ✅ {success_count}/{len(strategy_ids)} estrategias preparadas")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"[ResourcePreparationService] ❌ Error preparando estrategias: {e}")
            return False
    
    async def prepare_user_environment(self, user_id: str) -> Dict[str, bool]:
        """Prepara todo el entorno del usuario"""
        try:
            logger.info(f"[ResourcePreparationService] 🚀 Preparando entorno completo para usuario {user_id}")
            
            # Por ahora, preparar recursos genéricos
            # En el futuro, obtendríamos la lista real del usuario
            resources = {
                'database': 'default_db',
                'application': 'default_app',
                'strategies': ['default_strategy_1', 'default_strategy_2']
            }
            
            # Ejecutar preparación en paralelo
            preparation_tasks = []
            
            # Preparar base de datos
            if resources.get('database'):
                task = self.prepare_database(resources['database'], user_id)
                preparation_tasks.append(('database', task))
            
            # Preparar aplicación
            if resources.get('application'):
                task = self.prepare_application(resources['application'], user_id)
                preparation_tasks.append(('application', task))
            
            # Preparar estrategias
            if resources.get('strategies'):
                task = self.prepare_strategies(resources['strategies'], user_id)
                preparation_tasks.append(('strategies', task))
            
            # Ejecutar todas las preparaciones en paralelo
            results = {}
            if preparation_tasks:
                for resource_type, task in preparation_tasks:
                    try:
                        result = await task
                        results[resource_type] = result
                    except Exception as e:
                        logger.error(f"[ResourcePreparationService] Error en preparación de {resource_type}: {e}")
                        results[resource_type] = False
            
            # Notificar estado final
            if user_id:
                all_success = all(results.values())
                if all_success:
                    await self.notify_user_status(user_id, {
                        "type": "status",
                        "message": "🎉 Tu entorno está completamente preparado!",
                        "status": "environment_ready"
                    })
                else:
                    failed_resources = [k for k, v in results.items() if not v]
                    await self.notify_user_status(user_id, {
                        "type": "status",
                        "message": f"⚠️ Algunos recursos no se pudieron preparar: {', '.join(failed_resources)}",
                        "status": "partial_failure",
                        "failed_resources": failed_resources
                    })
            
            logger.info(f"[ResourcePreparationService] ✅ Entorno preparado para usuario {user_id}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"[ResourcePreparationService] ❌ Error preparando entorno para usuario {user_id}: {e}")
            return {}
    
    async def notify_user_status(self, user_id: str, status_message: Dict):
        """Notifica estado al usuario via WebSocket"""
        try:
            ws_emitter = self._get_ws_emitter()
            if ws_emitter:
                await ws_emitter.emit_to_user(user_id, status_message)
            else:
                logger.warning(f"[ResourcePreparationService] WSEmitter no disponible para notificar usuario {user_id}")
        except Exception as e:
            logger.error(f"[ResourcePreparationService] Error notificando estado a usuario {user_id}: {e}")
    
    async def get_preparation_status(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el estado de preparación del usuario"""
        try:
            if not self.readiness_registry:
                return {"error": "ReadinessRegistry no disponible"}
            
            # Obtener estado de todos los recursos
            resource_status = await self.readiness_registry.get_all_resource_status()
            
            # Filtrar por usuario (por ahora retornar todos)
            user_resources = {}
            for resource_key, status in resource_status.items():
                # En el futuro, filtrar por user_id
                user_resources[resource_key] = status
            
            return {
                "user_id": user_id,
                "resource_status": user_resources,
                "overall_ready": all(status['status'] == 'ready' for status in user_resources.values()),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ResourcePreparationService] Error obteniendo estado de preparación: {e}")
            return {"error": str(e)}
