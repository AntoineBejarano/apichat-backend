from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone
import asyncio

logger = logging.getLogger(__name__)

class EnvironmentPreparationOrchestrator:
    """
    Orquesta la preparación completa del entorno del usuario,
    coordinando con el registro de readiness y servicios en background.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry
        self.background_factory = factory.background
        self.warmup_engine = None
        self.resource_preparation = None
        
    def _get_warmup_engine(self):
        if not self.warmup_engine:
            self.warmup_engine = self.background_factory.get_warmup_engine()
        return self.warmup_engine
    
    def _get_resource_preparation(self):
        if not self.resource_preparation:
            self.resource_preparation = self.background_factory.get_resource_preparation_service()
        return self.resource_preparation
    
    async def prepare_user_environment(self, user_id: str, 
                                     db_uuid: str = None, 
                                     app_id: str = None, 
                                     strategy_ids: List[str] = None) -> Dict[str, Any]:
        """
        Prepara el entorno completo del usuario, iniciando warmups para todos los recursos.
        """
        try:
            logger.info(f"[EnvironmentPreparationOrchestrator] 🚀 Iniciando preparación del entorno para usuario {user_id}")
            
            # Inicializar servicios
            warmup_engine = self._get_warmup_engine()
            resource_prep = self._get_resource_preparation()
            
            if not warmup_engine or not resource_prep:
                logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Servicios de background no disponibles")
                return {"success": False, "error": "Servicios de background no disponibles"}
            
            # Marcar recursos como preparándose
            preparation_tasks = []
            
            if db_uuid:
                await self.readiness_registry.mark_resource_preparing("database", db_uuid)
                preparation_tasks.append(("database", db_uuid))
                
            if app_id:
                await self.readiness_registry.mark_resource_preparing("application", app_id)
                preparation_tasks.append(("application", app_id))
                
            if strategy_ids:
                for strategy_id in strategy_ids:
                    await self.readiness_registry.mark_resource_preparing("strategy", strategy_id)
                    preparation_tasks.append(("strategy", strategy_id))
            
            # Iniciar warmups en background
            warmup_tasks = []
            
            if db_uuid:
                warmup_tasks.append(warmup_engine.warmup_database(db_uuid, user_id))
                
            if app_id:
                warmup_tasks.append(warmup_engine.warmup_application(app_id, user_id))
                
            if strategy_ids:
                warmup_tasks.append(warmup_engine.warmup_strategies(app_id, user_id))
            
            # Ejecutar warmups en paralelo
            if warmup_tasks:
                asyncio.create_task(self._execute_warmups(warmup_tasks, user_id))
            
            logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Preparación del entorno iniciada para {len(preparation_tasks)} recursos")
            
            return {
                "success": True,
                "preparing_resources": preparation_tasks,
                "message": f"Preparación iniciada para {len(preparation_tasks)} recursos"
            }
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error preparando entorno: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_warmups(self, warmup_tasks: List, user_id: str):
        """
        Ejecuta los warmups en paralelo y maneja el estado final.
        """
        try:
            logger.info(f"[EnvironmentPreparationOrchestrator] 🔄 Ejecutando {len(warmup_tasks)} warmups")
            
            # Ejecutar warmups en paralelo
            results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
            
            # Verificar resultados
            successful_warmups = 0
            failed_warmups = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Warmup {i} falló: {result}")
                    failed_warmups += 1
                else:
                    successful_warmups += 1
            
            logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Warmups completados: {successful_warmups} exitosos, {failed_warmups} fallidos")
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error ejecutando warmups: {e}")
    
    async def get_environment_status(self, user_id: str, 
                                   db_uuid: str = None, 
                                   app_id: str = None, 
                                   strategy_ids: List[str] = None) -> Dict[str, Any]:
        """
        Obtiene el estado actual del entorno del usuario.
        """
        try:
            status = {
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resources": {}
            }
            
            if db_uuid:
                db_status = await self.readiness_registry.get_resource_status("database", db_uuid)
                status["resources"]["database"] = {
                    "uuid": db_uuid,
                    "status": db_status.value if db_status else "UNKNOWN"
                }
            
            if app_id:
                app_status = await self.readiness_registry.get_resource_status("application", app_id)
                status["resources"]["application"] = {
                    "id": app_id,
                    "status": app_status.value if app_status else "UNKNOWN"
                }
            
            if strategy_ids:
                status["resources"]["strategies"] = {}
                for strategy_id in strategy_ids:
                    strategy_status = await self.readiness_registry.get_resource_status("strategy", strategy_id)
                    status["resources"]["strategies"][strategy_id] = {
                        "status": strategy_status.value if strategy_status else "UNKNOWN"
                    }
            
            # Estado general del entorno
            all_resources = []
            if db_uuid:
                all_resources.append(("database", db_uuid))
            if app_id:
                all_resources.append(("application", app_id))
            if strategy_ids:
                for strategy_id in strategy_ids:
                    all_resources.append(("strategy", strategy_id))
            
            if all_resources:
                environment_ready = await self.readiness_registry.is_environment_ready(all_resources)
                status["environment_ready"] = environment_ready
            else:
                status["environment_ready"] = False
                status["message"] = "No hay recursos configurados"
            
            return status
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error obteniendo estado del entorno: {e}")
            return {
                "user_id": user_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def wait_for_environment_ready(self, user_id: str, 
                                       db_uuid: str = None, 
                                       app_id: str = None, 
                                       strategy_ids: List[str] = None,
                                       timeout: int = 300) -> Dict[str, Any]:
        """
        Espera hasta que el entorno esté listo o se agote el timeout.
        """
        try:
            logger.info(f"[EnvironmentPreparationOrchestrator] ⏳ Esperando que el entorno esté listo para usuario {user_id}")
            
            start_time = datetime.now(timezone.utc)
            timeout_seconds = timeout
            
            while timeout_seconds > 0:
                status = await self.get_environment_status(user_id, db_uuid, app_id, strategy_ids)
                
                if status.get("environment_ready", False):
                    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                    logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Entorno listo en {elapsed:.2f}s")
                    return {
                        "success": True,
                        "ready": True,
                        "elapsed_seconds": elapsed,
                        "status": status
                    }
                
                # Esperar antes de verificar nuevamente
                await asyncio.sleep(2)
                timeout_seconds -= 2
            
            # Timeout alcanzado
            logger.warning(f"[EnvironmentPreparationOrchestrator] ⏰ Timeout alcanzado para usuario {user_id}")
            return {
                "success": False,
                "ready": False,
                "timeout": True,
                "elapsed_seconds": timeout,
                "status": await self.get_environment_status(user_id, db_uuid, app_id, strategy_ids)
            }
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error esperando readiness del entorno: {e}")
            return {
                "success": False,
                "ready": False,
                "error": str(e)
            }
