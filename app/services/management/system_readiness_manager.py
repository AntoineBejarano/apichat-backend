from typing import Dict, List, Any, Optional, Set
import logging
from datetime import datetime, timezone
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)

class SystemStatus(Enum):
    """Estados del sistema"""
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    MAINTENANCE = "maintenance"

class SystemReadinessManager:
    """
    Gestor central para el estado de readiness del sistema y tracking en tiempo real.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry
        self.phase_manager = factory.phase_manager
        self.system_status = SystemStatus.INITIALIZING
        self.status_history = []
        self.health_checks = {}
        self.last_health_check = None
        self.health_check_interval = 30  # segundos
        
    async def initialize_system(self) -> Dict[str, Any]:
        """
        Inicializa el sistema y verifica el estado inicial.
        """
        try:
            logger.info("[SystemReadinessManager] 🚀 Inicializando sistema...")
            
            # Verificar que los servicios core estén disponibles
            if not self.readiness_registry or not self.phase_manager:
                logger.error("[SystemReadinessManager] ❌ Servicios core no disponibles")
                self.system_status = SystemStatus.ERROR
                return {"success": False, "error": "Servicios core no disponibles"}
            
            # Verificar estado de las fases
            phase_status = await self._check_phase_status()
            
            if phase_status.get("all_phases_ready", False):
                self.system_status = SystemStatus.READY
                logger.info("[SystemReadinessManager] ✅ Sistema inicializado y listo")
            else:
                self.system_status = SystemStatus.INITIALIZING
                pending_info = phase_status.get('pending_phases', ['fases pendientes'])
                logger.info(f"[SystemReadinessManager] ⏳ Sistema inicializando: {pending_info}")
            
            # Registrar estado inicial
            await self._record_status_change("Sistema inicializado", self.system_status.value)
            
            return {
                "success": True,
                "system_status": self.system_status.value,
                "phase_status": phase_status
            }
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error inicializando sistema: {e}")
            self.system_status = SystemStatus.ERROR
            return {"success": False, "error": str(e)}
    
    async def _check_phase_status(self) -> Dict[str, Any]:
        """
        Verifica el estado de todas las fases del sistema.
        """
        try:
            all_phases = ["phase_1_core", "phase_2_ai", "phase_3_execution", "phase_4_orchestrator"]
            ready_phases = []
            pending_phases = []
            
            for phase in all_phases:
                if await self.phase_manager.is_phase_completed(phase):
                    ready_phases.append(phase)
                else:
                    pending_phases.append(phase)
            
            return {
                "all_phases_ready": len(pending_phases) == 0,
                "ready_phases": ready_phases,
                "pending_phases": pending_phases,
                "total_phases": len(all_phases),
                "ready_count": len(ready_phases)
            }
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error verificando estado de fases: {e}")
            return {
                "all_phases_ready": False,
                "error": str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del sistema.
        """
        try:
            # Verificar estado de fases
            phase_status = await self._check_phase_status()
            
            # Verificar recursos activos
            active_resources = await self._get_active_resources()
            
            # Determinar estado del sistema
            if phase_status.get("all_phases_ready", False) and active_resources["total"] > 0:
                if self.system_status != SystemStatus.READY:
                    self.system_status = SystemStatus.READY
                    await self._record_status_change("Sistema listo", self.system_status.value)
            elif phase_status.get("ready_count", 0) > 0:
                if self.system_status != SystemStatus.DEGRADED:
                    self.system_status = SystemStatus.DEGRADED
                    await self._record_status_change("Sistema degradado", self.system_status.value)
            else:
                if self.system_status != SystemStatus.INITIALIZING:
                    self.system_status = SystemStatus.INITIALIZING
                    await self._record_status_change("Sistema inicializando", self.system_status.value)
            
            return {
                "system_status": self.system_status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "phase_status": phase_status,
                "active_resources": active_resources,
                "health_checks": self.health_checks,
                "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None
            }
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error obteniendo estado del sistema: {e}")
            return {
                "system_status": SystemStatus.ERROR.value,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _get_active_resources(self) -> Dict[str, Any]:
        """
        Obtiene información sobre recursos activos en el sistema.
        """
        try:
            # Obtener recursos del registro de readiness
            all_resources = await self.readiness_registry.get_all_resources()
            
            ready_resources = 0
            preparing_resources = 0
            error_resources = 0
            
            for resource_type, resources in all_resources.items():
                for resource_id, status in resources.items():
                    if status == "ready":
                        ready_resources += 1
                    elif status == "preparing":
                        preparing_resources += 1
                    elif status == "error":
                        error_resources += 1
            
            return {
                "total": ready_resources + preparing_resources + error_resources,
                "ready": ready_resources,
                "preparing": preparing_resources,
                "error": error_resources,
                "by_type": all_resources
            }
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error obteniendo recursos activos: {e}")
            return {"total": 0, "ready": 0, "preparing": 0, "error": 0}
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Realiza una verificación de salud del sistema.
        """
        try:
            logger.info("[SystemReadinessManager] 🔍 Realizando health check del sistema...")
            
            start_time = datetime.now(timezone.utc)
            
            # Verificar servicios core
            core_health = await self._check_core_services()
            
            # Verificar estado de fases
            phase_health = await self._check_phase_status()
            
            # Verificar recursos
            resource_health = await self._get_active_resources()
            
            # Calcular métricas de salud
            health_score = self._calculate_health_score(core_health, phase_health, resource_health)
            
            # Actualizar estado del sistema basado en health check
            if health_score >= 0.8:
                new_status = SystemStatus.READY
            elif health_score >= 0.5:
                new_status = SystemStatus.DEGRADED
            else:
                new_status = SystemStatus.ERROR
            
            if new_status != self.system_status:
                self.system_status = new_status
                await self._record_status_change(f"Health check: {new_status.value}", new_status.value)
            
            # Registrar health check
            health_result = {
                "timestamp": start_time.isoformat(),
                "health_score": health_score,
                "core_services": core_health,
                "phases": phase_health,
                "resources": resource_health,
                "system_status": self.system_status.value,
                "duration_ms": (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            }
            
            self.health_checks[start_time.isoformat()] = health_result
            self.last_health_check = start_time
            
            # Limpiar health checks antiguos (mantener solo los últimos 10)
            if len(self.health_checks) > 10:
                oldest_keys = sorted(self.health_checks.keys())[:-10]
                for key in oldest_keys:
                    del self.health_checks[key]
            
            logger.info(f"[SystemReadinessManager] ✅ Health check completado: score={health_score:.2f}, status={self.system_status.value}")
            
            return health_result
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error en health check: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_status": SystemStatus.ERROR.value
            }
    
    async def _check_core_services(self) -> Dict[str, Any]:
        """
        Verifica la salud de los servicios core.
        """
        try:
            services_status = {}
            
            # Verificar readiness registry
            if self.readiness_registry:
                services_status["readiness_registry"] = "available"
            else:
                services_status["readiness_registry"] = "unavailable"
            
            # Verificar phase manager
            if self.phase_manager:
                services_status["phase_manager"] = "available"
            else:
                services_status["phase_manager"] = "unavailable"
            
            # Verificar factory
            if self.factory:
                services_status["service_factory"] = "available"
            else:
                services_status["service_factory"] = "unavailable"
            
            return services_status
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error verificando servicios core: {e}")
            return {"error": str(e)}
    
    def _calculate_health_score(self, core_health: Dict, phase_health: Dict, resource_health: Dict) -> float:
        """
        Calcula un score de salud del sistema (0.0 a 1.0).
        """
        try:
            score = 0.0
            total_weight = 0.0
            
            # Core services (peso: 0.4)
            if "error" not in core_health:
                available_services = sum(1 for status in core_health.values() if status == "available")
                total_services = len(core_health)
                if total_services > 0:
                    score += (available_services / total_services) * 0.4
                    total_weight += 0.4
            
            # Phases (peso: 0.3)
            if "error" not in phase_health:
                ready_phases = phase_health.get("ready_count", 0)
                total_phases = phase_health.get("total_phases", 0)
                if total_phases > 0:
                    score += (ready_phases / total_phases) * 0.3
                    total_weight += 0.3
            
            # Resources (peso: 0.3)
            if "error" not in resource_health:
                ready_resources = resource_health.get("ready", 0)
                total_resources = resource_health.get("total", 0)
                if total_resources > 0:
                    score += (ready_resources / total_resources) * 0.3
                    total_weight += 0.3
            
            # Normalizar score
            if total_weight > 0:
                return score / total_weight
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error calculando health score: {e}")
            return 0.0
    
    async def _record_status_change(self, reason: str, new_status: str):
        """
        Registra un cambio de estado del sistema.
        """
        try:
            status_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "previous_status": self.system_status.value,
                "new_status": new_status,
                "reason": reason
            }
            
            self.status_history.append(status_record)
            
            # Mantener solo los últimos 50 cambios de estado
            if len(self.status_history) > 50:
                self.status_history = self.status_history[-50:]
            
            logger.info(f"[SystemReadinessManager] 📊 Cambio de estado: {status_record['previous_status']} → {new_status} ({reason})")
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error registrando cambio de estado: {e}")
    
    async def get_status_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Obtiene el historial de cambios de estado.
        """
        try:
            return self.status_history[-limit:] if self.status_history else []
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error obteniendo historial de estado: {e}")
            return []
    
    async def start_health_monitoring(self, interval_seconds: int = 30):
        """
        Inicia el monitoreo automático de salud del sistema.
        """
        try:
            self.health_check_interval = interval_seconds
            logger.info(f"[SystemReadinessManager] 🔄 Iniciando monitoreo de salud cada {interval_seconds}s")
            
            # Crear tarea de monitoreo en background
            asyncio.create_task(self._health_monitoring_loop())
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error iniciando monitoreo de salud: {e}")
    
    async def _health_monitoring_loop(self):
        """
        Loop principal de monitoreo de salud.
        """
        try:
            while True:
                await self.perform_health_check()
                await asyncio.sleep(self.health_check_interval)
                
        except asyncio.CancelledError:
            logger.info("[SystemReadinessManager] 🔄 Monitoreo de salud cancelado")
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error en loop de monitoreo: {e}")
    
    async def stop_health_monitoring(self):
        """
        Detiene el monitoreo automático de salud.
        """
        try:
            logger.info("[SystemReadinessManager] 🛑 Deteniendo monitoreo de salud")
            # En una implementación real, aquí se cancelarían las tareas de monitoreo
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error deteniendo monitoreo de salud: {e}")
    
    async def get_detailed_readiness_status(self, user_id: str) -> Dict[str, Any]:
        """
        Obtiene estado detallado de readiness para mostrar en frontend.
        """
        try:
            resource_status = await self._get_active_resources()
            
            # Formatear para frontend
            formatted_resources = {}
            for resource_type, resources in resource_status.get("by_type", {}).items():
                formatted_resources[resource_type] = []
                
                for resource_id, status in resources.items():
                    if status == "ready":
                        formatted_resources[resource_type].append({
                            'status': f"✅ {self._get_ready_message(resource_type)}",
                            'ready': True,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                    else:
                        formatted_resources[resource_type].append({
                            'status': f"⏳ {self._get_preparing_message(resource_type)}",
                            'ready': False,
                            'estimated_time': self._get_estimated_time(resource_type)
                        })
            
            overall_ready = all(
                all(r['ready'] for r in resources)
                for resources in formatted_resources.values()
            )
            
            return {
                'overall_ready': overall_ready,
                'resources': formatted_resources,
                'estimated_time': await self._estimate_preparation_time(user_id),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error obteniendo estado detallado de readiness: {e}")
            return {
                'overall_ready': False,
                'error': str(e),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
    
    def _get_ready_message(self, resource_type: str) -> str:
        """
        Obtiene mensaje para recursos listos.
        """
        messages = {
            'database': 'Introspectada',
            'application': 'Descriptor parseado',
            'strategies': 'Estrategias activas',
            'functions': 'Funciones validadas'
        }
        return messages.get(resource_type, 'Listo')
    
    def _get_preparing_message(self, resource_type: str) -> str:
        """
        Obtiene mensaje para recursos en preparación.
        """
        messages = {
            'database': 'Introspectando...',
            'application': 'Parseando descriptor...',
            'strategies': 'Procesando estrategias...',
            'functions': 'Validando funciones...'
        }
        return messages.get(resource_type, 'Preparando...')
    
    def _get_estimated_time(self, resource_type: str) -> int:
        """
        Obtiene tiempo estimado de preparación en segundos.
        """
        times = {
            'database': 3,
            'application': 2,
            'strategies': 5,
            'functions': 1
        }
        return times.get(resource_type, 3)
    
    async def _estimate_preparation_time(self, user_id: str) -> int:
        """
        Estima tiempo total de preparación.
        """
        try:
            resource_status = await self._get_active_resources()
            
            total_time = 0
            for resource_type, resources in resource_status.get("by_type", {}).items():
                for resource_id, status in resources.items():
                    if status != "ready":
                        total_time += self._get_estimated_time(resource_type)
            
            return total_time
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error estimando tiempo de preparación: {e}")
            return 0
    
    async def start_async_preparation(self, user_id: str):
        """
        Inicia preparación asíncrona del sistema.
        """
        try:
            logger.info(f"[SystemReadinessManager] 🚀 Iniciando preparación asíncrona para usuario {user_id}")
            
            # Obtener recursos pendientes
            pending_resources = await self.readiness_registry.get_pending_resources()
            
            # 🔧 VERIFICAR DISPONIBILIDAD DEL SERVICIO DE BACKGROUND
            if not hasattr(self.factory, 'background'):
                logger.warning(f"[SystemReadinessManager] ⚠️ Servicio de background no disponible, saltando preparación asíncrona")
                return
            
            # Lanzar preparación en background
            preparation_service = self.factory.background.get_resource_preparation_service()
            
            for resource in pending_resources:
                if resource['type'] == 'database':
                    asyncio.create_task(
                        preparation_service.prepare_database(resource['id'], user_id)
                    )
                elif resource['type'] == 'application':
                    asyncio.create_task(
                        preparation_service.prepare_application(resource['id'], user_id)
                    )
            
            logger.info(f"[SystemReadinessManager] ✅ Preparación asíncrona iniciada para usuario {user_id}")
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error iniciando preparación asíncrona: {e}")
    
    async def is_overall_ready(self, user_id: str) -> bool:
        """
        Verifica si todo el sistema está listo.
        """
        try:
            resource_status = await self._get_active_resources()
            
            for resource_type, resources in resource_status.get("by_type", {}).items():
                for resource_id, status in resources.items():
                    if status != "ready":
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"[SystemReadinessManager] ❌ Error verificando readiness general: {e}")
            return False
