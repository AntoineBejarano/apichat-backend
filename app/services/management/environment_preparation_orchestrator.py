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
        🔧 NUEVO: Ahora espera a que los warmups terminen y verifica si funcionaron.
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
            
            # 🔧 NUEVO: Ejecutar warmups y ESPERAR a que terminen
            warmup_tasks = []
            
            if db_uuid:
                warmup_tasks.append(warmup_engine.warmup_database(db_uuid, user_id))
                
            if app_id:
                warmup_tasks.append(warmup_engine.warmup_application(app_id, user_id))
                
            if strategy_ids:
                warmup_tasks.append(warmup_engine.warmup_strategies(app_id, user_id))
            
            # 🔧 NUEVO: Ejecutar warmups y ESPERAR resultado
            if warmup_tasks:
                logger.info(f"[EnvironmentPreparationOrchestrator] 🔄 Ejecutando {len(warmup_tasks)} warmups y esperando resultado...")
                warmup_results = await asyncio.gather(*warmup_tasks, return_exceptions=True)
                
                # 🔧 NUEVO: Verificar si los warmups realmente funcionaron
                successful_warmups = 0
                failed_warmups = 0
                warmup_errors = []
                
                for i, result in enumerate(warmup_results):
                    if isinstance(result, Exception):
                        logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Warmup {i} falló: {result}")
                        failed_warmups += 1
                        warmup_errors.append(str(result))
                    else:
                        successful_warmups += 1
                
                logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Warmups completados: {successful_warmups} exitosos, {failed_warmups} fallidos")
                
                # 🔧 NUEVO: Si hay warmups fallidos, retornar error
                if failed_warmups > 0:
                    error_msg = f"Warmups fallidos: {failed_warmups}/{len(warmup_tasks)}. Errores: {', '.join(warmup_errors)}"
                    logger.error(f"[EnvironmentPreparationOrchestrator] ❌ {error_msg}")
                    return {"success": False, "error": error_msg}
                
                # 🔧 NUEVO: Verificar que los recursos estén realmente listos
                logger.info(f"[EnvironmentPreparationOrchestrator] 🔍 Verificando que los recursos estén realmente listos...")
                
                # Esperar un poco para que se registren los cambios
                await asyncio.sleep(1)
                
                # Verificar readiness de cada recurso
                for resource_type, resource_id in preparation_tasks:
                    resource_status = await self.readiness_registry.get_resource_status(resource_type, resource_id)
                    if not resource_status or resource_status.get("status") != "READY":
                        error_msg = f"Recurso {resource_type}:{resource_id} no está listo después del warmup. Estado: {resource_status.get('status', 'UNKNOWN') if resource_status else 'UNKNOWN'}"
                        logger.error(f"[EnvironmentPreparationOrchestrator] ❌ {error_msg}")
                        return {"success": False, "error": error_msg}
                
                logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Todos los recursos están realmente listos")
            
            logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Preparación del entorno completada exitosamente para {len(preparation_tasks)} recursos")
            
            return {
                "success": True,
                "preparing_resources": preparation_tasks,
                "message": f"Preparación completada para {len(preparation_tasks)} recursos",
                "warmup_results": {
                    "successful": successful_warmups if 'successful_warmups' in locals() else 0,
                    "failed": failed_warmups if 'failed_warmups' in locals() else 0
                }
            }
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error preparando entorno: {e}")
            return {"success": False, "error": str(e)}
    
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
            
            # 🔧 NUEVO: Capturar errores específicos del SemanticValidator
            validation_errors = []
            
            if db_uuid:
                db_status = await self.readiness_registry.get_resource_status("database", db_uuid)
                status["resources"]["database"] = {
                    "uuid": db_uuid,
                    "status": db_status.get("status", "UNKNOWN") if db_status else "UNKNOWN"
                }
                
                # 🔧 NUEVO: Verificar si hay errores de validación semántica
                if db_status and db_status.get("status") == "ERROR":
                    errors = db_status.get("errors", [])
                    if errors:
                        validation_errors.extend([f"DB {db_uuid}: {error}" for error in errors])
                        # 🔧 NUEVO: Detectar si es un problema de esquema corrupto
                        if any("esquema incompleto" in error.lower() or "requiere recreación" in error.lower() for error in errors):
                            status["database_corrupted"] = True
                            status["corruption_details"] = {
                                "problem": "La base de datos tiene un esquema incompleto o corrupto",
                                "solution": "Borrar y recrear la base de datos desde el endpoint",
                                "reason": "Esta DB se creó antes de implementar el sistema de esquemas en Redis"
                            }
            
            if app_id:
                app_status = await self.readiness_registry.get_resource_status("application", app_id)
                status["resources"]["application"] = {
                    "id": app_id,
                    "status": app_status.get("status", "UNKNOWN") if app_status else "UNKNOWN"
                }
                
                # 🔧 NUEVO: Verificar errores de aplicación
                if app_status and app_status.get("status") == "ERROR":
                    errors = app_status.get("errors", [])
                    if errors:
                        validation_errors.extend([f"App {app_id}: {error}" for error in errors])
            
            if strategy_ids:
                status["resources"]["strategies"] = {}
                for strategy_id in strategy_ids:
                    strategy_status = await self.readiness_registry.get_resource_status("strategy", strategy_id)
                    status["resources"]["strategies"][strategy_id] = {
                        "status": strategy_status.get("status", "UNKNOWN") if strategy_status else "UNKNOWN"
                    }
                    
                    # 🔧 NUEVO: Verificar errores de estrategias
                    if strategy_status and strategy_status.get("status") == "ERROR":
                        errors = strategy_status.get("errors", [])
                        if errors:
                            validation_errors.extend([f"Strategy {strategy_id}: {error}" for error in errors])
            
            # 🔧 NUEVO: Agregar errores de validación al status
            if validation_errors:
                status["validation_errors"] = validation_errors
                status["has_validation_errors"] = True
            
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
                
                # 🔧 NUEVO: Si hay errores de validación, el entorno NO está listo
                if validation_errors:
                    status["environment_ready"] = False
                    status["blocked_by_validation"] = True
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
            max_retries = 5  # 🔧 NUEVO: Máximo de reintentos
            retry_count = 0
            consecutive_errors = 0  # 🔧 NUEVO: Contador de errores consecutivos
            
            while timeout_seconds > 0 and retry_count < max_retries:
                try:
                    # 🔧 NUEVO: Verificar si hay errores consecutivos
                    if consecutive_errors >= 3:
                        logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Demasiados errores consecutivos ({consecutive_errors}), abortando")
                        return {
                            "success": False,
                            "ready": False,
                            "error": f"Demasiados errores consecutivos: {consecutive_errors}",
                            "aborted": True
                        }
                    
                    status = await self.get_environment_status(user_id, db_uuid, app_id, strategy_ids)
                    
                    # 🔧 NUEVO: Verificar si el status es válido
                    if not status or "error" in status:
                        consecutive_errors += 1
                        logger.warning(f"[EnvironmentPreparationOrchestrator] ⚠️ Status inválido o con error (intento {consecutive_errors}/3): {status}")
                        await asyncio.sleep(5)  # Esperar más tiempo entre reintentos
                        timeout_seconds -= 5
                        continue
                    
                    # 🔧 NUEVO: Detectar errores específicos de validación
                    if status.get("has_validation_errors", False):
                        validation_errors = status.get("validation_errors", [])
                        logger.warning(f"[EnvironmentPreparationOrchestrator] ⚠️ Errores de validación detectados: {validation_errors}")
                        
                        # 🔧 NUEVO: Si hay DB corrupta, retornar inmediatamente con información útil
                        if status.get("database_corrupted", False):
                            corruption_details = status.get("corruption_details", {})
                            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Base de datos corrupta detectada: {corruption_details}")
                            return {
                                "success": False,
                                "ready": False,
                                "database_corrupted": True,
                                "validation_errors": validation_errors,
                                "corruption_details": corruption_details,
                                "user_action_required": True,
                                "message": "Base de datos corrupta - requiere acción del usuario"
                            }
                        
                        # 🔧 NUEVO: Si hay otros errores de validación, retornar con información
                        return {
                            "success": False,
                            "ready": False,
                            "validation_errors": validation_errors,
                            "user_action_required": True,
                            "message": f"Errores de validación detectados: {len(validation_errors)} problemas"
                        }
                    
                    # 🔧 NUEVO: Resetear contador de errores si el status es válido
                    consecutive_errors = 0
                    
                    if status.get("environment_ready", False):
                        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                        logger.info(f"[EnvironmentPreparationOrchestrator] ✅ Entorno listo en {elapsed:.2f}s")
                        return {
                            "success": True,
                            "ready": True,
                            "elapsed_seconds": elapsed,
                            "status": status
                        }
                    
                    # 🔧 NUEVO: Log de progreso cada 10 segundos
                    if retry_count % 5 == 0:
                        logger.info(f"[EnvironmentPreparationOrchestrator] ⏳ Esperando... (intento {retry_count + 1}/{max_retries}, timeout restante: {timeout_seconds}s)")
                    
                    # Esperar antes de verificar nuevamente
                    await asyncio.sleep(2)
                    timeout_seconds -= 2
                    retry_count += 1
                    
                except Exception as loop_error:
                    consecutive_errors += 1
                    retry_count += 1
                    logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error en iteración {retry_count}: {loop_error}")
                    
                    # 🔧 NUEVO: Esperar más tiempo si hay errores
                    await asyncio.sleep(5)
                    timeout_seconds -= 5
                    
                    if retry_count >= max_retries:
                        logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Máximo de reintentos alcanzado ({max_retries})")
                        break
            
            # 🔧 NUEVO: Determinar razón de salida
            if retry_count >= max_retries:
                logger.warning(f"[EnvironmentPreparationOrchestrator] ⏰ Máximo de reintentos alcanzado para usuario {user_id}")
                return {
                    "success": False,
                    "ready": False,
                    "max_retries_reached": True,
                    "retry_count": retry_count,
                    "elapsed_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
                }
            else:
                logger.warning(f"[EnvironmentPreparationOrchestrator] ⏰ Timeout alcanzado para usuario {user_id}")
                return {
                    "success": False,
                    "ready": False,
                    "timeout": True,
                    "elapsed_seconds": timeout,
                    "retry_count": retry_count
                }
            
        except Exception as e:
            logger.error(f"[EnvironmentPreparationOrchestrator] ❌ Error crítico esperando readiness del entorno: {e}")
            return {
                "success": False,
                "ready": False,
                "error": str(e),
                "critical_error": True
            }
