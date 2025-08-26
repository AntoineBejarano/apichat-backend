from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class ResourceUploadTrigger:
    def __init__(self, factory):
        self.factory = factory
        self.background_factory = factory.background
        self.warmup_engine = None  # Se inicializa lazy
    
    def _get_warmup_engine(self):
        """Obtiene el WarmupEngine de forma lazy"""
        if not self.warmup_engine:
            self.warmup_engine = self.background_factory.get_warmup_engine()
        return self.warmup_engine
    
    async def on_database_uploaded(self, db_uuid: str, user_id: str):
        """Trigger automático tras upload de base de datos"""
        try:
            logger.info(f"[ResourceUploadTrigger] 🚀 Trigger automático: base de datos {db_uuid} subida por usuario {user_id}")
            
            # Lanzar warmup inmediatamente en background
            warmup_engine = self._get_warmup_engine()
            if warmup_engine:
                await warmup_engine.warmup_database(db_uuid, user_id)
            else:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para DB {db_uuid}")
            
            # Marcar como "preparando" en el frontend
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": "🚀 Tu base de datos se está preparando automáticamente...",
                "resource": "database",
                "resource_id": db_uuid,
                "status": "auto_preparing"
            })
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] ❌ Error en trigger automático para DB {db_uuid}: {e}")
    
    async def on_application_uploaded(self, app_id: str, user_id: str):
        """Trigger automático tras upload de aplicación"""
        try:
            logger.info(f"[ResourceUploadTrigger] 🚀 Trigger automático: aplicación {app_id} subida por usuario {user_id}")
            
            # Lanzar warmup inmediatamente en background
            warmup_engine = self._get_warmup_engine()
            if warmup_engine:
                await warmup_engine.warmup_application(app_id, user_id)
            else:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para app {app_id}")
            
            # Marcar como "preparando" en el frontend
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": "🚀 Tu aplicación se está preparando automáticamente...",
                "resource": "application",
                "resource_id": app_id,
                "status": "auto_preparing"
            })
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] ❌ Error en trigger automático para app {app_id}: {e}")
    
    async def on_strategies_uploaded(self, strategy_ids: List[str], user_id: str):
        """Trigger automático tras upload de estrategias"""
        try:
            logger.info(f"[ResourceUploadTrigger] 🚀 Trigger automático: {len(strategy_ids)} estrategias subidas por usuario {user_id}")
            
            # Lanzar warmup inmediatamente en background
            warmup_engine = self._get_warmup_engine()
            if warmup_engine:
                # Para estrategias, usamos el app_id como referencia
                # En el futuro, podríamos tener un mapping más específico
                app_id = "default_app"  # Placeholder
                await warmup_engine.warmup_strategies(app_id, user_id)
            else:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para estrategias")
            
            # Marcar como "preparando" en el frontend
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": f"🚀 {len(strategy_ids)} estrategias se están procesando automáticamente...",
                "resource": "strategies",
                "resource_ids": strategy_ids,
                "status": "auto_preparing"
            })
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] ❌ Error en trigger automático para estrategias: {e}")
    
    async def on_function_uploaded(self, function_id: str, app_id: str, user_id: str):
        """Trigger automático tras upload de función"""
        try:
            logger.info(f"[ResourceUploadTrigger] 🚀 Trigger automático: función {function_id} subida para app {app_id} por usuario {user_id}")
            
            # Lanzar warmup de la aplicación completa (ya que las funciones están asociadas a apps)
            warmup_engine = self._get_warmup_engine()
            if warmup_engine:
                await warmup_engine.warmup_application(app_id, user_id)
            else:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para función {function_id}")
            
            # Marcar como "preparando" en el frontend
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": "🚀 Tu función se está integrando automáticamente...",
                "resource": "function",
                "resource_id": function_id,
                "app_id": app_id,
                "status": "auto_preparing"
            })
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] ❌ Error en trigger automático para función {function_id}: {e}")
    
    async def on_bulk_upload_completed(self, uploads: List[Dict], user_id: str):
        """Trigger automático tras upload masivo de recursos"""
        try:
            logger.info(f"[ResourceUploadTrigger] 🚀 Trigger automático: {len(uploads)} recursos subidos por usuario {user_id}")
            
            # Agrupar recursos por tipo
            databases = []
            applications = []
            strategies = []
            functions = []
            
            for upload in uploads:
                resource_type = upload.get('type')
                resource_id = upload.get('id')
                
                if resource_type == 'database':
                    databases.append(resource_id)
                elif resource_type == 'application':
                    applications.append(resource_id)
                elif resource_type == 'strategy':
                    strategies.append(resource_id)
                elif resource_type == 'function':
                    functions.append(resource_id)
            
            # Lanzar warmups en paralelo
            warmup_engine = self._get_warmup_engine()
            if not warmup_engine:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para bulk upload")
                return
            
            warmup_tasks = []
            
            # Warmup de bases de datos
            for db_id in databases:
                task = warmup_engine.warmup_database(db_id, user_id)
                warmup_tasks.append(task)
            
            # Warmup de aplicaciones
            for app_id in applications:
                task = warmup_engine.warmup_application(app_id, user_id)
                warmup_tasks.append(task)
            
            # Warmup de estrategias (usar app_id como referencia)
            for app_id in applications:
                task = warmup_engine.warmup_strategies(app_id, user_id)
                warmup_tasks.append(task)
            
            # Ejecutar todos los warmups en paralelo
            if warmup_tasks:
                await asyncio.gather(*warmup_tasks, return_exceptions=True)
            
            # Notificar completado
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": f"🎉 {len(uploads)} recursos preparados automáticamente!",
                "status": "bulk_completed",
                "upload_count": len(uploads)
            })
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] ❌ Error en trigger automático para bulk upload: {e}")
    
    async def notify_user_status(self, user_id: str, status_message: Dict):
        """Notifica al usuario sobre el estado del upload"""
        try:
            ws_emitter = self.factory.get_ws_emitter()
            if ws_emitter:
                await ws_emitter.emit_to_user(user_id, status_message)
            else:
                logger.warning(f"[ResourceUploadTrigger] WSEmitter no disponible para notificar usuario {user_id}")
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] Error notificando usuario {user_id}: {e}")
    
    async def get_trigger_status(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el estado de los triggers para un usuario"""
        try:
            warmup_engine = self._get_warmup_engine()
            if not warmup_engine:
                return {"error": "WarmupEngine no disponible"}
            
            # Obtener warmups activos
            active_warmups = warmup_engine.get_active_warmups()
            
            # Filtrar por usuario (por ahora retornar todos)
            user_warmups = {}
            for warmup_key, warmup_info in active_warmups.items():
                # En el futuro, filtrar por user_id
                user_warmups[warmup_key] = warmup_info
            
            return {
                "user_id": user_id,
                "active_warmups": user_warmups,
                "warmup_count": len(user_warmups),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] Error obteniendo estado de triggers: {e}")
            return {"error": str(e)}
    
    async def cancel_all_triggers(self, user_id: str):
        """Cancela todos los triggers activos para un usuario"""
        try:
            warmup_engine = self._get_warmup_engine()
            if not warmup_engine:
                logger.warning(f"[ResourceUploadTrigger] WarmupEngine no disponible para cancelar triggers")
                return False
            
            # Obtener warmups activos
            active_warmups = warmup_engine.get_active_warmups()
            
            # Cancelar cada warmup
            cancelled_count = 0
            for warmup_key, warmup_info in active_warmups.items():
                try:
                    # Extraer tipo y ID del recurso del warmup_key
                    if '_' in warmup_key:
                        resource_type, resource_id = warmup_key.split('_', 1)
                        await warmup_engine.cancel_warmup(resource_type, resource_id)
                        cancelled_count += 1
                except Exception as e:
                    logger.error(f"[ResourceUploadTrigger] Error cancelando warmup {warmup_key}: {e}")
            
            logger.info(f"[ResourceUploadTrigger] {cancelled_count} triggers cancelados para usuario {user_id}")
            
            # Notificar al usuario
            await self.notify_user_status(user_id, {
                "type": "upload_status",
                "message": f"⏹️ {cancelled_count} preparaciones automáticas canceladas",
                "status": "triggers_cancelled",
                "cancelled_count": cancelled_count
            })
            
            return True
            
        except Exception as e:
            logger.error(f"[ResourceUploadTrigger] Error cancelando triggers para usuario {user_id}: {e}")
            return False
