"""
🧪 Tests para FASE 2: REFACTORIZAR SERVICEFACTORY

Tests que validan:
- ServiceFactory.__init__ es ligero
- Métodos prepare_phase_X funcionan correctamente
- SystemPreparationManager coordina fases
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from app.core.service_factory import ServiceFactory
from app.core.system_preparation_manager import SystemPreparationManager


@pytest.fixture
def mock_request():
    """Mock de Request de FastAPI"""
    request = Mock()
    request.headers = {}
    request.cookies = {}
    request.query_params = {}
    return request


@pytest.fixture
def mock_user():
    """Mock de User"""
    user = Mock()
    user.id = "user_123"
    user.email = "test@example.com"
    return user


@pytest.fixture
def service_factory(mock_request, mock_user):
    """ServiceFactory con mocks"""
    return ServiceFactory(mock_request, mock_user)


@pytest.fixture
def system_preparation_manager(service_factory):
    """SystemPreparationManager con factory mockeado"""
    return SystemPreparationManager(service_factory)


class TestServiceFactory:
    """Tests para ServiceFactory refactorizado"""
    
    def test_init_is_lightweight(self, mock_request, mock_user):
        """Test que __init__ es ligero y no inicializa sub-factories"""
        factory = ServiceFactory(mock_request, mock_user)
        
        # Verificar que solo se inicializan atributos básicos
        assert factory.request == mock_request
        assert factory.user == mock_user
        assert factory.db is not None
        
        # Verificar que NO se inicializan sub-factories
        assert not hasattr(factory, 'core')
        assert not hasattr(factory, 'ai')
        assert not hasattr(factory, 'cache')
        assert not hasattr(factory, 'data')
        assert not hasattr(factory, 'management')
        assert not hasattr(factory, 'background')
        
        # Verificar flags de fases
        assert factory._phase_1_core_ready is False
        assert factory._phase_2_ai_ready is False
        assert factory._phase_3_execution_ready is False
        assert factory._phase_4_orchestrator_ready is False
        
        # Verificar atributos de gestión
        assert factory.readiness_registry is None
        assert factory.phase_manager is None
    
    @pytest.mark.asyncio
    async def test_prepare_phase_1_core(self, service_factory):
        """Test preparación de Fase 1 (Core)"""
        # Mock de imports usando patch.object para métodos internos
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación
            await service_factory.prepare_phase_1_core()
            
            # Verificar que se inicializó correctamente
            assert service_factory._phase_1_core_ready is True
            assert hasattr(service_factory, 'core')
            assert service_factory.readiness_registry is not None
            assert service_factory.phase_manager is not None
            
            # Verificar que se llamaron los métodos del phase manager
            mock_phase_manager_instance.mark_phase_in_progress.assert_called_once_with('phase_1_core')
            mock_phase_manager_instance.mark_phase_completed.assert_called_once_with('phase_1_core')
    
    @pytest.mark.asyncio
    async def test_prepare_phase_2_ai(self, service_factory):
        """Test preparación de Fase 2 (AI)"""
        # Mock de imports y preparar Fase 1
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch.object(service_factory, '_initialize_ai_services') as mock_init_ai, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_init_ai.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación
            await service_factory.prepare_phase_2_ai()
            
            # Verificar que se completaron ambas fases
            assert service_factory._phase_1_core_ready is True
            assert service_factory._phase_2_ai_ready is True
            assert hasattr(service_factory, 'ai')
            
            # Verificar que se llamaron los métodos del phase manager
            mock_phase_manager_instance.mark_phase_in_progress.assert_called_with('phase_2_ai')
            mock_phase_manager_instance.mark_phase_completed.assert_called_with('phase_2_ai')
    
    @pytest.mark.asyncio
    async def test_prepare_phase_3_execution(self, service_factory):
        """Test preparación de Fase 3 (Execution)"""
        # Mock de imports y preparar fases anteriores
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch.object(service_factory, '_initialize_ai_services') as mock_init_ai, \
             patch.object(service_factory, '_initialize_execution_services') as mock_init_exec, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_init_ai.return_value = Mock()
            mock_init_exec.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación
            await service_factory.prepare_phase_3_execution()
            
            # Verificar que se completaron las 3 fases
            assert service_factory._phase_1_core_ready is True
            assert service_factory._phase_2_ai_ready is True
            assert service_factory._phase_3_execution_ready is True
            assert service_factory.execution_services is True
            
            # Verificar que se llamaron los métodos del phase manager
            mock_phase_manager_instance.mark_phase_in_progress.assert_called_with('phase_3_execution')
            mock_phase_manager_instance.mark_phase_completed.assert_called_with('phase_3_execution')
    
    @pytest.mark.asyncio
    async def test_prepare_phase_4_orchestrator(self, service_factory):
        """Test preparación de Fase 4 (Orchestrator)"""
        # Mock de imports y preparar fases anteriores
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch.object(service_factory, '_initialize_ai_services') as mock_init_ai, \
             patch.object(service_factory, '_initialize_execution_services') as mock_init_exec, \
             patch.object(service_factory, '_initialize_orchestrator_services') as mock_init_orch, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_init_ai.return_value = Mock()
            mock_init_exec.return_value = Mock()
            mock_init_orch.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación
            await service_factory.prepare_phase_4_orchestrator()
            
            # Verificar que se completaron todas las fases
            assert service_factory._phase_1_core_ready is True
            assert service_factory._phase_2_ai_ready is True
            assert service_factory._phase_3_execution_ready is True
            assert service_factory._phase_4_orchestrator_ready is True
            
            # Verificar que se inicializaron todas las sub-factories
            assert hasattr(service_factory, 'cache')
            assert hasattr(service_factory, 'data')
            assert hasattr(service_factory, 'management')
            assert hasattr(service_factory, 'background')
            
            # Verificar que se llamaron los métodos del phase manager
            mock_phase_manager_instance.mark_phase_in_progress.assert_called_with('phase_4_orchestrator')
            mock_phase_manager_instance.mark_phase_completed.assert_called_with('phase_4_orchestrator')
    
    @pytest.mark.asyncio
    async def test_prepare_for_chat(self, service_factory):
        """Test preparación para chat (Fases 1-3)"""
        # Mock de imports
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch.object(service_factory, '_initialize_ai_services') as mock_init_ai, \
             patch.object(service_factory, '_initialize_execution_services') as mock_init_exec, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_init_ai.return_value = Mock()
            mock_init_exec.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación para chat
            result = await service_factory.prepare_for_chat()
            
            # Verificar resultado
            assert result is True
            
            # Verificar que se completaron las fases necesarias para chat
            assert service_factory._phase_1_core_ready is True
            assert service_factory._phase_2_ai_ready is True
            assert service_factory._phase_3_execution_ready is True
            assert service_factory._phase_4_orchestrator_ready is False  # No se preparó
    
    @pytest.mark.asyncio
    async def test_prepare_for_orchestrator(self, service_factory):
        """Test preparación para orquestador (todas las fases)"""
        # Mock de imports
        with patch.object(service_factory, '_initialize_core_services') as mock_init_core, \
             patch.object(service_factory, '_initialize_ai_services') as mock_init_ai, \
             patch.object(service_factory, '_initialize_execution_services') as mock_init_exec, \
             patch.object(service_factory, '_initialize_orchestrator_services') as mock_init_orch, \
             patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_init_core.return_value = Mock()
            mock_init_ai.return_value = Mock()
            mock_init_exec.return_value = Mock()
            mock_init_orch.return_value = Mock()
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Ejecutar preparación para orquestador
            result = await service_factory.prepare_for_orchestrator()
            
            # Verificar resultado
            assert result is True
            
            # Verificar que se completaron todas las fases
            assert service_factory._phase_1_core_ready is True
            assert service_factory._phase_2_ai_ready is True
            assert service_factory._phase_3_execution_ready is True
            assert service_factory._phase_4_orchestrator_ready is True
    
    def test_get_service_before_phase_raises_error(self, service_factory):
        """Test que obtener servicios antes de preparar fases lanza error"""
        # Intentar obtener servicios sin preparar fases
        with pytest.raises(RuntimeError, match="Fase 1 \\(Core\\) no está lista"):
            service_factory.get_database_service()
        
        with pytest.raises(RuntimeError, match="Fase 2 \\(AI\\) no está lista"):
            service_factory.get_advanced_telemetry_service()
        
        with pytest.raises(RuntimeError, match="Fase 3 \\(Execution\\) no está lista"):
            service_factory.get_chat_service()
        
        with pytest.raises(RuntimeError, match="Fase 4 \\(Orchestrator\\) no está lista"):
            service_factory.get_orchestrator_service()
    
    @pytest.mark.asyncio
    async def test_phase_preparation_is_idempotent(self, service_factory):
        """Test que preparar fases múltiples veces no causa problemas"""
        # Mock de imports
        with patch('app.services.management.ReadinessRegistry') as mock_readiness_registry, \
             patch('app.services.management.PhaseDependencyManager') as mock_phase_manager:
            
            # Configurar mocks
            mock_readiness_registry.return_value = Mock()
            
            # Configurar AsyncMock para métodos async
            mock_phase_manager_instance = AsyncMock()
            mock_phase_manager.return_value = mock_phase_manager_instance
            
            # Preparar Fase 1 múltiples veces
            await service_factory.prepare_phase_1_core()
            await service_factory.prepare_phase_1_core()
            await service_factory.prepare_phase_1_core()
            
            # Verificar que solo se ejecutó una vez (porque las siguientes veces retorna temprano)
            assert mock_phase_manager_instance.mark_phase_in_progress.call_count == 1
            assert mock_phase_manager_instance.mark_phase_completed.call_count == 1
            
            # Verificar que el flag está marcado como True
            assert service_factory._phase_1_core_ready is True


class TestSystemPreparationManager:
    """Tests para SystemPreparationManager"""
    
    @pytest.mark.asyncio
    async def test_prepare_for_chat(self, system_preparation_manager):
        """Test preparación para chat usando SystemPreparationManager"""
        # Mock de métodos del factory
        system_preparation_manager.factory.prepare_phase_1_core = AsyncMock()
        system_preparation_manager.factory.prepare_phase_2_ai = AsyncMock()
        system_preparation_manager.factory.prepare_phase_3_execution = AsyncMock()
        
        # Mock de phase manager
        mock_phase_manager = Mock()
        mock_phase_manager.get_phase_status = AsyncMock(return_value={'phase_1_core': 'completed'})
        system_preparation_manager.factory.phase_manager = mock_phase_manager
        
        # Ejecutar preparación
        result = await system_preparation_manager.prepare_for_chat()
        
        # Verificar resultado
        assert result['success'] is True
        assert result['ready_for_chat'] is True
        assert 'preparation_duration' in result
        assert result['completed_phases'] == ['phase_1_core', 'phase_2_ai', 'phase_3_execution']
        
        # Verificar que se llamaron los métodos del factory
        system_preparation_manager.factory.prepare_phase_1_core.assert_called_once()
        system_preparation_manager.factory.prepare_phase_2_ai.assert_called_once()
        system_preparation_manager.factory.prepare_phase_3_execution.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prepare_for_orchestrator(self, system_preparation_manager):
        """Test preparación para orquestador usando SystemPreparationManager"""
        # Mock de métodos del factory
        system_preparation_manager.factory.prepare_phase_1_core = AsyncMock()
        system_preparation_manager.factory.prepare_phase_2_ai = AsyncMock()
        system_preparation_manager.factory.prepare_phase_3_execution = AsyncMock()
        system_preparation_manager.factory.prepare_phase_4_orchestrator = AsyncMock()
        
        # Mock de phase manager
        mock_phase_manager = Mock()
        mock_phase_manager.get_phase_status = AsyncMock(return_value={'phase_4_orchestrator': 'completed'})
        system_preparation_manager.factory.phase_manager = mock_phase_manager
        
        # Ejecutar preparación
        result = await system_preparation_manager.prepare_for_orchestrator()
        
        # Verificar resultado
        assert result['success'] is True
        assert result['ready_for_orchestrator'] is True
        assert result['ready_for_chat'] is True
        assert 'preparation_duration' in result
        assert result['completed_phases'] == ['phase_1_core', 'phase_2_ai', 'phase_3_execution', 'phase_4_orchestrator']
        
        # Verificar que se llamaron todos los métodos del factory
        system_preparation_manager.factory.prepare_phase_4_orchestrator.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_preparation_status_not_started(self, system_preparation_manager):
        """Test estado de preparación cuando no se ha iniciado"""
        status = await system_preparation_manager.get_preparation_status()
        
        assert status['status'] == 'not_started'
        assert status['message'] == 'No se ha iniciado la preparación'
    
    @pytest.mark.asyncio
    async def test_get_preparation_status_in_progress(self, system_preparation_manager):
        """Test estado de preparación cuando está en progreso"""
        # Mock de phase manager con fases completadas
        mock_phase_manager = Mock()
        mock_phase_manager.completed_phases = {'phase_1_core', 'phase_2_ai'}
        mock_phase_manager.get_phase_status = AsyncMock(return_value={'phase_1_core': 'completed', 'phase_2_ai': 'completed'})
        system_preparation_manager.phase_manager = mock_phase_manager
        
        status = await system_preparation_manager.get_preparation_status()
        
        assert status['status'] == 'in_progress'
        assert status['message'] == 'Fase 2 de 4 completada'
        assert len(status['completed_phases']) == 2
        assert status['total_phases'] == 4
    
    @pytest.mark.asyncio
    async def test_get_preparation_status_completed(self, system_preparation_manager):
        """Test estado de preparación cuando está completada"""
        # Mock de phase manager con todas las fases completadas
        mock_phase_manager = Mock()
        mock_phase_manager.completed_phases = {'phase_1_core', 'phase_2_ai', 'phase_3_execution', 'phase_4_orchestrator'}
        mock_phase_manager.get_phase_status = AsyncMock(return_value={
            'phase_1_core': 'completed', 
            'phase_2_ai': 'completed', 
            'phase_3_execution': 'completed', 
            'phase_4_orchestrator': 'completed'
        })
        system_preparation_manager.phase_manager = mock_phase_manager
        
        status = await system_preparation_manager.get_preparation_status()
        
        assert status['status'] == 'completed'
        assert status['message'] == 'Todas las fases completadas'
        assert len(status['completed_phases']) == 4
        assert status['total_phases'] == 4
    
    @pytest.mark.asyncio
    async def test_is_ready_for_chat(self, system_preparation_manager):
        """Test verificación de readiness para chat"""
        # Mock de phase manager con fases suficientes para chat
        mock_phase_manager = Mock()
        mock_phase_manager.completed_phases = {'phase_1_core', 'phase_2_ai', 'phase_3_execution'}
        mock_phase_manager.get_phase_status = AsyncMock(return_value={'phase_1_core': 'completed'})
        system_preparation_manager.phase_manager = mock_phase_manager
        
        is_ready = await system_preparation_manager.is_ready_for_chat()
        assert is_ready is True
    
    @pytest.mark.asyncio
    async def test_is_ready_for_orchestrator(self, system_preparation_manager):
        """Test verificación de readiness para orquestador"""
        # Mock de phase manager con todas las fases completadas
        mock_phase_manager = Mock()
        mock_phase_manager.completed_phases = {'phase_1_core', 'phase_2_ai', 'phase_3_execution', 'phase_4_orchestrator'}
        mock_phase_manager.get_phase_status = AsyncMock(return_value={'phase_1_core': 'completed'})
        system_preparation_manager.phase_manager = mock_phase_manager
        
        is_ready = await system_preparation_manager.is_ready_for_orchestrator()
        assert is_ready is True
    
    @pytest.mark.asyncio
    async def test_reset_preparation(self, system_preparation_manager):
        """Test reseteo de preparación"""
        # Configurar estado inicial
        system_preparation_manager.factory._phase_1_core_ready = True
        system_preparation_manager.factory._phase_2_ai_ready = True
        system_preparation_manager.preparation_start_time = Mock()
        system_preparation_manager.preparation_end_time = Mock()
        
        # Mock de phase manager
        mock_phase_manager = Mock()
        mock_phase_manager.completed_phases = {'phase_1_core', 'phase_2_ai'}
        mock_phase_manager.phase_status = {'phase_1_core': 'completed'}
        system_preparation_manager.phase_manager = mock_phase_manager
        
        # Ejecutar reset
        result = await system_preparation_manager.reset_preparation()
        
        # Verificar resultado
        assert result is True
        
        # Verificar que se reseteó el estado
        assert system_preparation_manager.factory._phase_1_core_ready is False
        assert system_preparation_manager.factory._phase_2_ai_ready is False
        assert system_preparation_manager.preparation_start_time is None
        assert system_preparation_manager.preparation_end_time is None
        
        # Verificar que se limpió el phase manager
        # Nota: clear() es un método built-in, no un mock, así que verificamos que se llamó
        assert len(mock_phase_manager.completed_phases) == 0
        assert len(mock_phase_manager.phase_status) == 0
