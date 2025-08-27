from typing import Dict, List, Set
from enum import Enum

class PhaseStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"

# Grafo de dependencias entre fases
DEPENDENCY_GRAPH = {
    'phase_1_core': [],
    'phase_2_ai': ['phase_1_core'],
    'phase_3_execution': ['phase_2_ai'],
    'phase_4_orchestrator': ['phase_3_execution', 'phase_2_ai'],
    'phase_5_chat': ['phase_4_orchestrator']
}

# Dependencias de servicios específicos
SERVICE_DEPENDENCIES = {
    'ai_orchestrator': ['db_schema', 'app_descriptor', 'strategies'],
    'execution_engine': ['ai_services', 'function_service'],
    'chat_service': ['orchestrator', 'ws_emitter'],
    'smart_ai_service': ['intent_classifier', 'mode_detection']
}

class PhaseDependencyManager:
    def __init__(self):
        self.completed_phases: Set[str] = set()
        self.phase_status: Dict[str, PhaseStatus] = {}
        self.dependency_graph = DEPENDENCY_GRAPH
        self.service_dependencies = SERVICE_DEPENDENCIES
    
    async def can_execute_phase(self, phase: str) -> bool:
        """Verifica si una fase puede ejecutarse"""
        dependencies = self.dependency_graph.get(phase, [])
        return all(dep in self.completed_phases for dep in dependencies)
    
    async def can_execute_service(self, service_name: str) -> bool:
        """Verifica si un servicio puede ejecutarse"""
        dependencies = self.service_dependencies.get(service_name, [])
        return all(await self.is_resource_ready(dep) for dep in dependencies)
    
    async def is_resource_ready(self, resource_name: str) -> bool:
        """Verifica si un recurso específico está listo"""
        # Implementar lógica de verificación de recursos
        return resource_name in self.completed_phases
    
    async def mark_phase_completed(self, phase: str):
        """Marca una fase como completada"""
        self.completed_phases.add(phase)
        self.phase_status[phase] = PhaseStatus.COMPLETED
    
    async def mark_phase_in_progress(self, phase: str):
        """Marca una fase como en progreso"""
        self.phase_status[phase] = PhaseStatus.IN_PROGRESS
    
    async def get_phase_dependencies(self, phase: str) -> List[str]:
        """Obtiene las dependencias de una fase"""
        return self.dependency_graph.get(phase, [])
    
    async def get_service_dependencies(self, service_name: str) -> List[str]:
        """Obtiene las dependencias de un servicio"""
        return self.service_dependencies.get(service_name, [])
    
    async def get_phase_status(self) -> Dict[str, PhaseStatus]:
        """Obtiene el estado de todas las fases"""
        return self.phase_status.copy()
    
    async def get_completed_phases(self) -> Set[str]:
        """Obtiene las fases completadas"""
        return self.completed_phases.copy()
    
    async def is_phase_completed(self, phase: str) -> bool:
        """Verifica si una fase específica está completada"""
        return phase in self.completed_phases
    
    async def get_pending_phases(self) -> List[str]:
        """Obtiene las fases pendientes de ejecución"""
        pending = []
        for phase in self.dependency_graph.keys():
            if phase not in self.completed_phases:
                if await self.can_execute_phase(phase):
                    pending.append(phase)
        return pending
    
    async def get_blocked_phases(self) -> List[str]:
        """Obtiene las fases bloqueadas por dependencias"""
        blocked = []
        for phase in self.dependency_graph.keys():
            if phase not in self.completed_phases and not await self.can_execute_phase(phase):
                blocked.append(phase)
        return blocked
    
    async def reset_phase(self, phase: str):
        """Resetea una fase específica"""
        if phase in self.completed_phases:
            self.completed_phases.remove(phase)
        if phase in self.phase_status:
            del self.phase_status[phase]
    
    async def reset_all_phases(self):
        """Resetea todas las fases"""
        self.completed_phases.clear()
        self.phase_status.clear()
