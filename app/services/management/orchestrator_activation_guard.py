from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from .readiness_registry import ReadinessStatus

logger = logging.getLogger(__name__)

@dataclass
class ActivationResult:
    can_activate: bool
    message: str
    missing_resources: Optional[Dict] = None
    estimated_wait_time: Optional[int] = None
    semantic_errors: Optional[List[str]] = None

class OrchestratorActivationGuard:
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry

    async def can_activate_orchestrator(self, user_id: str) -> bool:
        try:
            critical_resources = await self.get_critical_resources(user_id)
            all_ready = True
            for resource in critical_resources:
                readiness = await self.readiness_registry.check_resource_readiness(
                    resource['type'], resource['id']
                )
                if readiness != ReadinessStatus.READY:
                    all_ready = False
            if not all_ready:
                return False
            semantic_validation = await self.validate_semantic_readiness(critical_resources)
            return semantic_validation.valid
        except Exception as e:
            logger.error(f"Error verificando activación del orquestador para usuario {user_id}: {e}")
            return False

    async def get_critical_resources(self, user_id: str) -> List[Dict[str, str]]:
        """Obtiene los recursos críticos necesarios para activar el orquestador"""
        try:
            # Aquí deberías obtener los recursos reales del usuario
            # Por ahora retornamos una lista de ejemplo
            return [
                {'type': 'database', 'id': f'db_{user_id}'},
                {'type': 'application', 'id': f'app_{user_id}'},
                {'type': 'strategies', 'id': f'strategy_{user_id}'}
            ]
        except Exception as e:
            logger.error(f"Error obteniendo recursos críticos para usuario {user_id}: {e}")
            return []

    async def validate_semantic_readiness(self, resources: List[Dict[str, str]]) -> 'ValidationResult':
        """Valida que los recursos estén semánticamente listos"""
        try:
            from .semantic_validator import SemanticValidator
            validator = SemanticValidator(self.factory)
            
            for resource in resources:
                if resource['type'] == 'database':
                    result = await validator.validate_database_schema(resource['id'])
                elif resource['type'] == 'application':
                    result = await validator.validate_application_functions(resource['id'])
                elif resource['type'] == 'strategies':
                    result = await validator.validate_strategies(resource['id'])
                else:
                    continue
                
                if not result.valid:
                    return result
            
            from .semantic_validator import ValidationResult
            return ValidationResult(valid=True, message="Todos los recursos están semánticamente validados")
        except Exception as e:
            logger.error(f"Error en validación semántica: {e}")
            from .semantic_validator import ValidationResult
            return ValidationResult(valid=False, errors=[str(e)], message="Error en validación semántica")

    async def get_activation_status(self, user_id: str) -> ActivationResult:
        """Obtiene el estado actual de activación del orquestador"""
        try:
            critical_resources = await self.get_critical_resources(user_id)
            missing_resources = []
            
            for resource in critical_resources:
                readiness = await self.readiness_registry.check_resource_readiness(
                    resource['type'], resource['id']
                )
                if readiness != ReadinessStatus.READY:
                    missing_resources.append({
                        'type': resource['type'],
                        'id': resource['id'],
                        'status': readiness.value
                    })
            
            if missing_resources:
                return ActivationResult(
                    can_activate=False,
                    message=f"Recursos pendientes: {len(missing_resources)} recursos no están listos",
                    missing_resources=missing_resources,
                    estimated_wait_time=30  # 30 segundos estimados
                )
            
            # Verificar validación semántica
            semantic_validation = await self.validate_semantic_readiness(critical_resources)
            if not semantic_validation.valid:
                return ActivationResult(
                    can_activate=False,
                    message=f"Validación semántica fallida: {semantic_validation.message}",
                    semantic_errors=semantic_validation.errors
                )
            
            return ActivationResult(
                can_activate=True,
                message="Orquestador listo para activar"
            )
            
        except Exception as e:
            logger.error(f"Error verificando estado de activación: {e}")
            return ActivationResult(
                can_activate=False,
                message=f"Error verificando estado: {str(e)}"
            )

    async def wait_for_activation(self, user_id: str, timeout_seconds: int = 60) -> bool:
        """Espera hasta que el orquestador esté listo para activar"""
        import asyncio
        
        start_time = datetime.now(timezone.utc)
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout_seconds:
            status = await self.get_activation_status(user_id)
            if status.can_activate:
                return True
            await asyncio.sleep(2)  # Esperar 2 segundos antes de verificar nuevamente
        
        return False
