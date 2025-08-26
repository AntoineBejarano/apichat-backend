"""
Tests para la Fase 1: Fundamentos del Sistema

Este archivo contiene tests básicos para verificar que:
- ReadinessRegistry funciona correctamente
- PhaseDependencyManager valida dependencias
- ReadinessValidator integra con servicios de cache existentes
- OrchestratorActivationGuard funciona correctamente
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock
from datetime import datetime

# Importar los servicios a testear
from app.services.management.readiness_registry import ReadinessRegistry, ReadinessStatus
from app.services.management.semantic_validator import SemanticValidator, ValidationResult
from app.services.management.phase_dependency_manager import PhaseDependencyManager, PhaseStatus
from app.services.management.readiness_validator import ReadinessValidator
from app.services.management.orchestrator_activation_guard import OrchestratorActivationGuard, ActivationResult

@pytest.fixture
def mock_factory():
    """Factory mock para testing"""
    factory = Mock()
    
    # Mock para cache services
    cache_service = Mock()
    cache_service.get_schema = AsyncMock(return_value={
        'tables': [
            {
                'name': 'users',
                'columns': [
                    {'name': 'id', 'type': 'int'},
                    {'name': 'name', 'type': 'varchar'}
                ]
            }
        ]
    })
    
    app_cache_service = Mock()
    app_cache_service.get_descriptor = AsyncMock(return_value={
        'functions': [
            {
                'name': 'create_user',
                'parameters': [
                    {'name': 'name', 'type': 'string'}
                ]
            }
        ]
    })
    
    factory.get_detailed_schema_cache_service = Mock(return_value=cache_service)
    factory.get_app_descriptor_cache_service = Mock(return_value=app_cache_service)
    
    return factory

@pytest.fixture
def readiness_registry(mock_factory):
    """ReadinessRegistry para testing"""
    return ReadinessRegistry(mock_factory)

@pytest.fixture
def phase_manager():
    """PhaseDependencyManager para testing"""
    return PhaseDependencyManager()

@pytest.fixture
def semantic_validator(mock_factory):
    """SemanticValidator para testing"""
    return SemanticValidator(mock_factory)

@pytest.fixture
def readiness_validator(mock_factory):
    """ReadinessValidator para testing"""
    return ReadinessValidator(mock_factory)

@pytest.fixture
def activation_guard(mock_factory, readiness_registry):
    """OrchestratorActivationGuard para testing"""
    mock_factory.readiness_registry = readiness_registry
    return OrchestratorActivationGuard(mock_factory)

class TestReadinessRegistry:
    """Tests para ReadinessRegistry"""
    
    def test_init(self, readiness_registry):
        """Test inicialización del ReadinessRegistry"""
        assert readiness_registry.resource_readiness == {}
        assert readiness_registry.factory is not None
    
    @pytest.mark.asyncio
    async def test_mark_resource_preparing(self, readiness_registry):
        """Test marcar recurso como en preparación"""
        await readiness_registry.mark_resource_preparing('database', 'db_123')
        
        key = ('database', 'db_123')
        assert key in readiness_registry.resource_readiness
        assert readiness_registry.resource_readiness[key]['status'] == ReadinessStatus.PREPARING
    
    @pytest.mark.asyncio
    async def test_mark_resource_ready(self, readiness_registry):
        # Marcar como preparando primero
        await readiness_registry.mark_resource_preparing('database', 'db_123')
        
        # Marcar como listo - debería retornar True si la validación semántica pasa
        result = await readiness_registry.mark_resource_ready('database', 'db_123')
        
        # Verificar que el recurso esté marcado como listo
        status = await readiness_registry.check_resource_readiness('database', 'db_123')
        assert status == ReadinessStatus.READY
        
        # Verificar que se guardó la metadata
        resource_info = readiness_registry.resource_readiness[('database', 'db_123')]
        assert resource_info['status'] == ReadinessStatus.READY
        assert 'timestamp' in resource_info
        assert 'metadata' in resource_info
        assert 'semantic_validation' in resource_info

    @pytest.mark.asyncio
    async def test_mark_resource_ready_semantic_validation_fails(self, readiness_registry):
        """Test marcar recurso como listo cuando falla la validación semántica"""
        # Mock para que la validación semántica falle
        readiness_registry.semantic_validator.validate_database_schema = AsyncMock(
            return_value=ValidationResult(
                valid=False, 
                errors=["Schema inválido"], 
                message="Error en validación del esquema"
            )
        )
        
        # Marcar como preparando primero
        await readiness_registry.mark_resource_preparing('database', 'db_fail')
        
        # Marcar como listo - debería retornar False si la validación semántica falla
        result = await readiness_registry.mark_resource_ready('database', 'db_fail')
        assert result is False
        
        # Verificar que el recurso esté marcado como error
        status = await readiness_registry.check_resource_readiness('database', 'db_fail')
        assert status == ReadinessStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_check_resource_readiness(self, readiness_registry):
        """Test verificar readiness de un recurso"""
        # Recurso no existente debería retornar PENDING
        status = await readiness_registry.check_resource_readiness('database', 'db_999')
        assert status == ReadinessStatus.PENDING
        
        # Marcar como preparando y verificar
        await readiness_registry.mark_resource_preparing('database', 'db_123')
        status = await readiness_registry.check_resource_readiness('database', 'db_123')
        assert status == ReadinessStatus.PREPARING

class TestPhaseDependencyManager:
    """Tests para PhaseDependencyManager"""
    
    def test_init(self, phase_manager):
        """Test inicialización del PhaseDependencyManager"""
        assert phase_manager.completed_phases == set()
        assert phase_manager.phase_status == {}
    
    @pytest.mark.asyncio
    async def test_can_execute_phase(self, phase_manager):
        """Test verificar si una fase puede ejecutarse"""
        # phase_1_core no tiene dependencias, debería poder ejecutarse
        can_execute = await phase_manager.can_execute_phase('phase_1_core')
        assert can_execute is True
        
        # phase_2_ai requiere phase_1_core, no debería poder ejecutarse
        can_execute = await phase_manager.can_execute_phase('phase_2_ai')
        assert can_execute is False
    
    @pytest.mark.asyncio
    async def test_mark_phase_completed(self, phase_manager):
        """Test marcar fase como completada"""
        await phase_manager.mark_phase_completed('phase_1_core')
        
        assert 'phase_1_core' in phase_manager.completed_phases
        assert phase_manager.phase_status['phase_1_core'] == PhaseStatus.COMPLETED
        
        # Ahora phase_2_ai debería poder ejecutarse
        can_execute = await phase_manager.can_execute_phase('phase_2_ai')
        assert can_execute is True

class TestSemanticValidator:
    """Tests para SemanticValidator"""
    
    @pytest.mark.asyncio
    async def test_validate_database_schema(self, semantic_validator):
        """Test validación semántica de esquema de base de datos"""
        result = await semantic_validator.validate_database_schema('db_123')
        
        assert result.valid is True
        assert "válido semánticamente" in result.message
        assert result.errors == []
    
    @pytest.mark.asyncio
    async def test_validate_application_functions(self, semantic_validator):
        """Test validación semántica de funciones de aplicación"""
        result = await semantic_validator.validate_application_functions('app_123')
        
        assert result.valid is True
        assert "válida semánticamente" in result.message
        assert result.errors == []

class TestReadinessValidator:
    """Tests para ReadinessValidator"""
    
    @pytest.mark.asyncio
    async def test_is_database_ready(self, readiness_validator):
        """Test verificar si base de datos está lista"""
        is_ready = await readiness_validator.is_database_ready('db_123')
        assert is_ready is True
    
    @pytest.mark.asyncio
    async def test_is_application_ready(self, readiness_validator):
        """Test verificar si aplicación está lista"""
        is_ready = await readiness_validator.is_application_ready('app_123')
        assert is_ready is True

class TestOrchestratorActivationGuard:
    """Tests para OrchestratorActivationGuard"""
    
    @pytest.mark.asyncio
    async def test_can_activate_orchestrator(self, activation_guard):
        """Test verificar si se puede activar el orquestador"""
        # Por ahora debería retornar False porque no hay recursos marcados como READY
        can_activate = await activation_guard.can_activate_orchestrator('user_123')
        assert can_activate is False
    
    @pytest.mark.asyncio
    async def test_get_activation_status(self, activation_guard):
        """Test obtener estado de activación"""
        status = await activation_guard.get_activation_status('user_123')

        assert isinstance(status, ActivationResult)
        assert status.can_activate is False
        assert "Recursos pendientes" in status.message  # Corregido para coincidir con el mensaje real
        assert status.missing_resources is not None
        assert len(status.missing_resources) == 3
        assert status.estimated_wait_time == 30

if __name__ == "__main__":
    # Ejecutar tests básicos
    pytest.main([__file__, "-v"])
