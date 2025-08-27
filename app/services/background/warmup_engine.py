from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

class WarmupEngine:
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry
        self.ws_emitter = None  # Se inicializa lazy
        self.active_warmups = {}  # Track de warmups activos
    
    def _get_ws_emitter(self):
        """Obtiene el WSEmitter de forma lazy"""
        if not self.ws_emitter:
            self.ws_emitter = self.factory.get_ws_emitter()
        return self.ws_emitter
    
    async def warmup_database(self, db_uuid: str, user_id: str = None):
        """Pre-calienta base de datos con notificaciones"""
        try:
            logger.info(f"[WarmupEngine] 🔥 Pre-calientando base de datos {db_uuid}")
            
            # Verificar si ya está en warmup
            warmup_key = f"database_{db_uuid}"
            if warmup_key in self.active_warmups:
                logger.info(f"[WarmupEngine] Base de datos {db_uuid} ya está en warmup")
                return
            
            # Marcar como en warmup
            self.active_warmups[warmup_key] = {
                'started_at': datetime.now(),
                'status': 'warming_up'
            }
            
            # Marcar como "preparando" en el registry
            await self.readiness_registry.mark_resource_preparing('database', db_uuid)
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "🔥 Pre-calientando base de datos...",
                    "resource": "database",
                    "resource_id": db_uuid,
                    "status": "warming_up"
                })
            
            # Ejecutar warmup en background
            warmup_task = asyncio.create_task(
                self._execute_database_warmup(db_uuid, user_id)
            )
            
            # Guardar referencia a la tarea
            self.active_warmups[warmup_key]['task'] = warmup_task
            
        except Exception as e:
            logger.error(f"[WarmupEngine] Error iniciando warmup de base de datos {db_uuid}: {e}")
            await self.readiness_registry.mark_resource_error('database', db_uuid, str(e))
    
    async def _execute_database_warmup(self, db_uuid: str, user_id: str = None):
        """Ejecuta el warmup real de la base de datos"""
        try:
            # Simular tiempo de warmup (en el futuro sería real)
            await asyncio.sleep(2)
            
            # Verificar que el cache service esté disponible
            cache_service = self.factory.get_detailed_schema_cache_service()
            if not cache_service:
                raise Exception("Cache service no disponible")
            
            # Intentar obtener/refrescar el esquema
            schema = await cache_service.get_schema_cache(user_id, db_uuid)
            if not schema:
                raise Exception("No se pudo obtener esquema")
            
            # Marcar como listo
            await self.readiness_registry.mark_resource_ready('database', db_uuid, {
                'warmed_up_at': datetime.now(),
                'warmup_type': 'automatic',
                'schema_version': 'latest',
                'tables_count': len(schema.tables) if hasattr(schema, 'tables') else 0
            })
            
            # Notificar completado
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "✅ Base de datos pre-calientada",
                    "resource": "database",
                    "resource_id": db_uuid,
                    "status": "warmed_up"
                })
            
            # Limpiar warmup activo
            warmup_key = f"database_{db_uuid}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'completed'
                self.active_warmups[warmup_key]['completed_at'] = datetime.now()
                del self.active_warmups[warmup_key]
            
            logger.info(f"[WarmupEngine] ✅ Base de datos {db_uuid} pre-calientada exitosamente")
            
        except Exception as e:
            logger.error(f"[WarmupEngine] ❌ Error en warmup de base de datos {db_uuid}: {e}")
            await self.readiness_registry.mark_resource_error('database', db_uuid, str(e))
            
            # Notificar error al usuario
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "❌ Error pre-calientando base de datos",
                    "resource": "database",
                    "resource_id": db_uuid,
                    "status": "error",
                    "error": str(e)
                })
            
            # Limpiar warmup activo
            warmup_key = f"database_{db_uuid}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'error'
                self.active_warmups[warmup_key]['error'] = str(e)
    
    async def warmup_application(self, app_id: str, user_id: str = None):
        """Pre-calienta aplicación con notificaciones"""
        try:
            logger.info(f"[WarmupEngine] 🔥 Pre-calientando aplicación {app_id}")
            
            # Verificar si ya está en warmup
            warmup_key = f"application_{app_id}"
            if warmup_key in self.active_warmups:
                logger.info(f"[WarmupEngine] Aplicación {app_id} ya está en warmup")
                return
            
            # Marcar como en warmup
            self.active_warmups[warmup_key] = {
                'started_at': datetime.now(),
                'status': 'warming_up'
            }
            
            # Marcar como "preparando" en el registry
            await self.readiness_registry.mark_resource_preparing('application', app_id)
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "🔥 Pre-calientando aplicación...",
                    "resource": "application",
                    "resource_id": app_id,
                    "status": "warming_up"
                })
            
            # Ejecutar warmup en background
            warmup_task = asyncio.create_task(
                self._execute_application_warmup(app_id, user_id)
            )
            
            # Guardar referencia a la tarea
            self.active_warmups[warmup_key]['task'] = warmup_task
            
        except Exception as e:
            logger.error(f"[WarmupEngine] Error iniciando warmup de aplicación {app_id}: {e}")
            await self.readiness_registry.mark_resource_error('application', app_id, str(e))
    
    async def _execute_application_warmup(self, app_id: str, user_id: str = None):
        """Ejecuta el warmup real de la aplicación"""
        try:
            # Simular tiempo de warmup (en el futuro sería real)
            await asyncio.sleep(1.5)
            
            # Verificar que el cache service esté disponible
            cache_service = self.factory.get_app_descriptor_cache_service()
            if not cache_service:
                raise Exception("Cache service no disponible")
            
            # Intentar obtener/refrescar el descriptor
            descriptor = await cache_service.get_descriptor(app_id)
            if not descriptor:
                raise Exception("No se pudo obtener descriptor")
            
            # Marcar como listo
            await self.readiness_registry.mark_resource_ready('application', app_id, {
                'warmed_up_at': datetime.now(),
                'warmup_type': 'automatic',
                'descriptor_version': 'latest',
                'functions_count': len(descriptor.get('functions', []))
            })
            
            # Notificar completado
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "✅ Aplicación pre-calientada",
                    "resource": "application",
                    "resource_id": app_id,
                    "status": "warmed_up"
                })
            
            # Limpiar warmup activo
            warmup_key = f"application_{app_id}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'completed'
                self.active_warmups[warmup_key]['completed_at'] = datetime.now()
                del self.active_warmups[warmup_key]
            
            logger.info(f"[WarmupEngine] ✅ Aplicación {app_id} pre-calientada exitosamente")
            
        except Exception as e:
            logger.error(f"[WarmupEngine] ❌ Error en warmup de aplicación {app_id}: {e}")
            await self.readiness_registry.mark_resource_error('application', app_id, str(e))
            
            # Notificar error al usuario
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "❌ Error pre-calientando aplicación",
                    "resource": "application",
                    "resource_id": app_id,
                    "status": "error",
                    "error": str(e)
                })
            
            # Limpiar warmup activo
            warmup_key = f"application_{app_id}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'error'
                self.active_warmups[warmup_key]['error'] = str(e)
    
    async def warmup_strategies(self, app_id: str, user_id: str = None):
        """Genera estrategias sugeridas"""
        try:
            logger.info(f"[WarmupEngine] 🔥 Generando estrategias sugeridas para app {app_id}")
            
            # Verificar si ya está en warmup
            warmup_key = f"strategies_{app_id}"
            if warmup_key in self.active_warmups:
                logger.info(f"[WarmupEngine] Estrategias para app {app_id} ya están en warmup")
                return
            
            # Marcar como en warmup
            self.active_warmups[warmup_key] = {
                'started_at': datetime.now(),
                'status': 'warming_up'
            }
            
            # Notificar al usuario si está disponible
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "🔥 Generando estrategias sugeridas...",
                    "resource": "strategies",
                    "resource_id": app_id,
                    "status": "warming_up"
                })
            
            # Ejecutar warmup en background
            warmup_task = asyncio.create_task(
                self._execute_strategies_warmup(app_id, user_id)
            )
            
            # Guardar referencia a la tarea
            self.active_warmups[warmup_key]['task'] = warmup_task
            
        except Exception as e:
            logger.error(f"[WarmupEngine] Error iniciando warmup de estrategias para app {app_id}: {e}")
    
    async def _execute_strategies_warmup(self, app_id: str, user_id: str = None):
        """Ejecuta el warmup real de las estrategias"""
        try:
            # Simular tiempo de generación (en el futuro sería real)
            await asyncio.sleep(1)
            
            # Por ahora, solo marcar como completado
            # En el futuro, se generarían estrategias reales
            logger.info(f"[WarmupEngine] Estrategias sugeridas generadas para app {app_id}")
            
            # Notificar completado
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "✅ Estrategias generadas automáticamente",
                    "resource": "strategies",
                    "resource_id": app_id,
                    "status": "generated"
                })
            
            # Limpiar warmup activo
            warmup_key = f"strategies_{app_id}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'completed'
                self.active_warmups[warmup_key]['completed_at'] = datetime.now()
                del self.active_warmups[warmup_key]
            
        except Exception as e:
            logger.error(f"[WarmupEngine] ❌ Error en warmup de estrategias para app {app_id}: {e}")
            
            # Notificar error al usuario
            if user_id:
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "❌ Error generando estrategias",
                    "resource": "strategies",
                    "resource_id": app_id,
                    "status": "error",
                    "error": str(e)
                })
            
            # Limpiar warmup activo
            warmup_key = f"strategies_{app_id}"
            if warmup_key in self.active_warmups:
                self.active_warmups[warmup_key]['status'] = 'error'
                self.active_warmups[warmup_key]['error'] = str(e)
    
    async def warmup_user_environment(self, user_id: str):
        """Pre-calienta todo el entorno del usuario"""
        try:
            logger.info(f"[WarmupEngine] 🔥 Pre-calientando entorno completo para usuario {user_id}")
            
            # Por ahora, ejecutar warmup en recursos genéricos
            # En el futuro, obtendríamos la lista real del usuario
            resources = {
                'database': 'default_db',
                'application': 'default_app',
                'strategies': 'default_app'  # Usar app_id para estrategias
            }
            
            # Ejecutar warmups en paralelo
            warmup_tasks = []
            
            # Warmup de base de datos
            if resources.get('database'):
                task = self.warmup_database(resources['database'], user_id)
                warmup_tasks.append(task)
            
            # Warmup de aplicación
            if resources.get('application'):
                task = self.warmup_application(resources['application'], user_id)
                warmup_tasks.append(task)
            
            # Warmup de estrategias
            if resources.get('strategies'):
                task = self.warmup_strategies(resources['strategies'], user_id)
                warmup_tasks.append(task)
            
            # Ejecutar todos los warmups en paralelo
            if warmup_tasks:
                await asyncio.gather(*warmup_tasks, return_exceptions=True)
                
                # Notificar completado
                await self.notify_user(user_id, {
                    "type": "warmup_status",
                    "message": "🎉 Tu entorno está completamente pre-calientado!",
                    "status": "environment_ready"
                })
                
        except Exception as e:
            logger.error(f"[WarmupEngine] ❌ Error warming up entorno para usuario {user_id}: {e}")
    
    async def notify_user(self, user_id: str, message: Dict):
        """Notifica al usuario sobre el estado del warmup"""
        try:
            ws_emitter = self._get_ws_emitter()
            if ws_emitter:
                # Extraer el tipo del mensaje como evento
                event_type = message.get("type", "warmup_status")
                await ws_emitter.emit_to_user(user_id, event_type, message)
            else:
                logger.warning(f"[WarmupEngine] WSEmitter no disponible para notificar usuario {user_id}")
        except Exception as e:
            logger.error(f"[WarmupEngine] Error notificando usuario {user_id}: {e}")
    
    def get_active_warmups(self) -> Dict[str, Dict]:
        """Obtiene el estado de todos los warmups activos"""
        return self.active_warmups.copy()
    
    def is_resource_warming_up(self, resource_type: str, resource_id: str) -> bool:
        """Verifica si un recurso específico está en warmup"""
        warmup_key = f"{resource_type}_{resource_id}"
        return warmup_key in self.active_warmups
    
    async def cancel_warmup(self, resource_type: str, resource_id: str):
        """Cancela un warmup activo"""
        try:
            warmup_key = f"{resource_type}_{resource_id}"
            if warmup_key in self.active_warmups:
                warmup_info = self.active_warmups[warmup_key]
                
                # Cancelar tarea si existe
                if 'task' in warmup_info:
                    warmup_info['task'].cancel()
                
                # Limpiar
                del self.active_warmups[warmup_key]
                
                logger.info(f"[WarmupEngine] Warmup cancelado para {resource_type} {resource_id}")
                
        except Exception as e:
            logger.error(f"[WarmupEngine] Error cancelando warmup para {resource_type} {resource_id}: {e}")
