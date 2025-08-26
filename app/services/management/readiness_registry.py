from datetime import datetime
from typing import Optional, Dict, Any, Union, List, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ReadinessStatus(Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    ERROR = "error"
    VALIDATING = "validating"

class ReadinessRegistry:
    def __init__(self, factory):
        # Key: (resource_type, resource_id) -> ReadinessStatus
        self.resource_readiness = {}
        self.factory = factory
        # Importar SemanticValidator de forma lazy para evitar dependencias circulares
        self._semantic_validator = None
    
    @property
    def semantic_validator(self):
        """Lazy loading del SemanticValidator"""
        if self._semantic_validator is None:
            from app.services.management.semantic_validator import SemanticValidator
            self._semantic_validator = SemanticValidator(self.factory)
        return self._semantic_validator
    
    async def check_resource_readiness(self, resource_type: str, resource_id: str) -> ReadinessStatus:
        """Verifica readiness de un recurso específico"""
        key = (resource_type, resource_id)
        status = self.resource_readiness.get(key)
        
        if isinstance(status, dict):
            return status.get('status', ReadinessStatus.PENDING)
        return status or ReadinessStatus.PENDING
    
    async def mark_resource_ready(self, resource_type: str, resource_id: str, metadata: Dict = None) -> bool:
        """Marca un recurso como listo SOLO si pasa validación semántica"""
        try:
            # 1. Validar semánticamente antes de marcar como listo
            validation_result = await self._validate_resource_semantically(resource_type, resource_id)
            
            if not validation_result.valid:
                logger.error(f"Recurso {resource_type}:{resource_id} no pasa validación semántica: {validation_result.errors}")
                await self.mark_resource_error(resource_type, resource_id, validation_result.errors)
                return False
            
            # 2. Marcar como listo solo si pasa validación
            key = (resource_type, resource_id)
            self.resource_readiness[key] = {
                'status': ReadinessStatus.READY,
                'timestamp': datetime.now(),
                'metadata': metadata or {},
                'semantic_validation': validation_result.message,
                'validation_timestamp': datetime.now()
            }
            
            logger.info(f"Recurso {resource_type}:{resource_id} marcado como listo y validado semánticamente")
            return True
            
        except Exception as e:
            logger.error(f"Error marcando recurso {resource_type}:{resource_id} como listo: {e}")
            await self.mark_resource_error(resource_type, resource_id, [str(e)])
            return False
    
    async def mark_resource_preparing(self, resource_type: str, resource_id: str):
        """Marca un recurso como en preparación"""
        key = (resource_type, resource_id)
        self.resource_readiness[key] = {
            'status': ReadinessStatus.PREPARING,
            'timestamp': datetime.now()
        }
    
    async def mark_resource_validating(self, resource_type: str, resource_id: str):
        """Marca un recurso como en validación semántica"""
        key = (resource_type, resource_id)
        self.resource_readiness[key] = {
            'status': ReadinessStatus.VALIDATING,
            'timestamp': datetime.now()
        }
    
    async def mark_resource_error(self, resource_type: str, resource_id: str, errors: List[str]):
        """Marca un recurso como con error"""
        key = (resource_type, resource_id)
        self.resource_readiness[key] = {
            'status': ReadinessStatus.ERROR,
            'timestamp': datetime.now(),
            'errors': errors
        }
    
    async def get_pending_resources(self) -> List[Dict]:
        """Obtiene recursos pendientes de preparación"""
        pending = []
        for (resource_type, resource_id), status_data in self.resource_readiness.items():
            if isinstance(status_data, dict):
                status = status_data.get('status')
            else:
                status = status_data
                
            if status in [ReadinessStatus.PENDING, ReadinessStatus.ERROR]:
                pending.append({
                    'type': resource_type,
                    'id': resource_id,
                    'status': status,
                    'errors': status_data.get('errors') if isinstance(status_data, dict) else None
                })
        return pending
    
    async def get_resource_status(self, resource_type: str, resource_id: str) -> Dict:
        """Obtiene estado detallado de un recurso específico"""
        key = (resource_type, resource_id)
        status_data = self.resource_readiness.get(key)
        
        if not status_data:
            return {
                'ready': False,
                'status': 'PENDING',
                'message': f'Recurso {resource_type}:{resource_id} no encontrado'
            }
        
        if isinstance(status_data, dict):
            status = status_data.get('status')
            metadata = status_data.get('metadata', {})
            errors = status_data.get('errors', [])
        else:
            status = status_data
            metadata = {}
            errors = []
        
        return {
            'ready': status == ReadinessStatus.READY,
            'status': status.value if hasattr(status, 'value') else str(status),
            'resource_type': resource_type,
            'resource_id': resource_id,
            'metadata': metadata,
            'errors': errors,
            'last_updated': status_data.get('timestamp', 'N/A') if isinstance(status_data, dict) else 'N/A'
        }
    
    async def get_shared_resources(self) -> List[Tuple[str, str]]:
        """Obtiene recursos que pueden ser compartidos entre usuarios"""
        # Implementar lógica para identificar recursos compartibles
        shared = []
        for (resource_type, resource_id), status_data in self.resource_readiness.items():
            if isinstance(status_data, dict):
                status = status_data.get('status')
            else:
                status = status_data
                
            if status == ReadinessStatus.READY:
                shared.append((resource_type, resource_id))
        return shared
    
    async def _validate_resource_semantically(self, resource_type: str, resource_id: str) -> 'ValidationResult':
        """Valida semánticamente un recurso antes de marcarlo como listo"""
        try:
            if resource_type == 'database':
                return await self.semantic_validator.validate_database_schema(resource_id)
            elif resource_type == 'application':
                return await self.semantic_validator.validate_application_functions(resource_id)
            elif resource_type == 'strategies':
                return await self.semantic_validator.validate_strategies(resource_id)
            else:
                # Para tipos de recurso que no requieren validación semántica
                from app.services.management.semantic_validator import ValidationResult
                return ValidationResult(valid=True, message=f"Tipo de recurso {resource_type} no requiere validación semántica")
                
        except Exception as e:
            logger.error(f"Error en validación semántica de {resource_type}:{resource_id}: {e}")
            from app.services.management.semantic_validator import ValidationResult
            return ValidationResult(valid=False, errors=[str(e)], message="Error en validación semántica")
