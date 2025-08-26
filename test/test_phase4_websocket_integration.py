import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.management.environment_preparation_orchestrator import EnvironmentPreparationOrchestrator
from app.services.management.system_readiness_manager import SystemReadinessManager, SystemStatus
from app.services.management.readiness_registry import ReadinessStatus


@pytest.fixture
def mock_factory():
    """Factory mock con todos los servicios necesarios"""
    factory = Mock()
    
    # Mock readiness registry
    readiness_registry = AsyncMock()
    readiness_registry.mark_resource_preparing = AsyncMock()
    readiness_registry.get_resource_status = AsyncMock(return_value=ReadinessStatus.READY)
    readiness_registry.is_environment_ready = AsyncMock(return_value=True)
    readiness_registry.get_all_resources = AsyncMock(return_value={
        "database": {"db_123": "ready"},
        "application": {"app_456": "ready"},
        "strategy": {"strat_789": "ready"}
    })
    factory.readiness_registry = readiness_registry
    
    # Mock phase manager
    phase_manager = AsyncMock()
    phase_manager.is_phase_completed = AsyncMock(return_value=True)
    factory.phase_manager = phase_manager
    
    # Mock background factory
    background_factory = Mock()
    
    # Mock warmup engine
    warmup_engine = AsyncMock()
    warmup_engine.warmup_database = AsyncMock()
    warmup_engine.warmup_application = AsyncMock()
    warmup_engine.warmup_strategies = AsyncMock()
    background_factory.get_warmup_engine = Mock(return_value=warmup_engine)
    
    # Mock resource preparation service
    resource_prep = AsyncMock()
    background_factory.get_resource_preparation_service = Mock(return_value=resource_prep)
    
    factory.background = background_factory
    
    return factory


@pytest.fixture
def environment_prep_orchestrator(mock_factory):
    """EnvironmentPreparationOrchestrator con factory mock"""
    return EnvironmentPreparationOrchestrator(mock_factory)


@pytest.fixture
def system_readiness_manager(mock_factory):
    """SystemReadinessManager con factory mock"""
    return SystemReadinessManager(mock_factory)


class TestEnvironmentPreparationOrchestrator:
    """Tests para EnvironmentPreparationOrchestrator"""
    
    @pytest.mark.asyncio
    async def test_prepare_user_environment_success(self, environment_prep_orchestrator):
        """Test preparación exitosa del entorno del usuario"""
        result = await environment_prep_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456",
            strategy_ids=["strat_789"]
        )
        
        assert result["success"] is True
        assert len(result["preparing_resources"]) == 3
        assert ("database", "db_123") in result["preparing_resources"]
        assert ("application", "app_456") in result["preparing_resources"]
        assert ("strategy", "strat_789") in result["preparing_resources"]
        
        # Verificar que se marcaron los recursos como preparándose
        environment_prep_orchestrator.readiness_registry.mark_resource_preparing.assert_any_call("database", "db_123")
        environment_prep_orchestrator.readiness_registry.mark_resource_preparing.assert_any_call("application", "app_456")
        environment_prep_orchestrator.readiness_registry.mark_resource_preparing.assert_any_call("strategy", "strat_789")
    
    @pytest.mark.asyncio
    async def test_prepare_user_environment_no_resources(self, environment_prep_orchestrator):
        """Test preparación del entorno sin recursos"""
        result = await environment_prep_orchestrator.prepare_user_environment(
            user_id="user_123"
        )
        
        assert result["success"] is True
        assert len(result["preparing_resources"]) == 0
        assert result["message"] == "Preparación iniciada para 0 recursos"
    
    @pytest.mark.asyncio
    async def test_prepare_user_environment_services_unavailable(self, environment_prep_orchestrator):
        """Test preparación del entorno con servicios no disponibles"""
        # Mock servicios no disponibles
        environment_prep_orchestrator.factory.background.get_warmup_engine.return_value = None
        
        result = await environment_prep_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123"
        )
        
        assert result["success"] is False
        assert "Servicios de background no disponibles" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_environment_status(self, environment_prep_orchestrator):
        """Test obtención del estado del entorno"""
        status = await environment_prep_orchestrator.get_environment_status(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456",
            strategy_ids=["strat_789"]
        )
        
        assert status["user_id"] == "user_123"
        assert "timestamp" in status
        assert "resources" in status
        assert status["resources"]["database"]["uuid"] == "db_123"
        assert status["resources"]["application"]["id"] == "app_456"
        assert "strat_789" in status["resources"]["strategies"]
        assert status["environment_ready"] is True
    
    @pytest.mark.asyncio
    async def test_wait_for_environment_ready_success(self, environment_prep_orchestrator):
        """Test espera exitosa del entorno"""
        # Mock entorno listo inmediatamente
        environment_prep_orchestrator.readiness_registry.is_environment_ready.return_value = True
        
        result = await environment_prep_orchestrator.wait_for_environment_ready(
            user_id="user_123",
            db_uuid="db_123",
            timeout=5
        )
        
        assert result["success"] is True
        assert result["ready"] is True
        assert result["elapsed_seconds"] >= 0
    
    @pytest.mark.asyncio
    async def test_wait_for_environment_ready_timeout(self, environment_prep_orchestrator):
        """Test timeout esperando que el entorno esté listo"""
        # Mock entorno nunca listo
        environment_prep_orchestrator.readiness_registry.is_environment_ready.return_value = False
        
        result = await environment_prep_orchestrator.wait_for_environment_ready(
            user_id="user_123",
            db_uuid="db_123",
            timeout=1  # Timeout corto para el test
        )
        
        assert result["success"] is False
        assert result["ready"] is False
        assert result["timeout"] is True
        assert result["elapsed_seconds"] == 1


class TestSystemReadinessManager:
    """Tests para SystemReadinessManager"""
    
    @pytest.mark.asyncio
    async def test_initialize_system_success(self, system_readiness_manager):
        """Test inicialización exitosa del sistema"""
        result = await system_readiness_manager.initialize_system()
        
        assert result["success"] is True
        assert "system_status" in result
        assert "phase_status" in result
        
        # Verificar que se verificó el estado de las fases
        system_readiness_manager.phase_manager.is_phase_completed.assert_called()
    
    @pytest.mark.asyncio
    async def test_initialize_system_services_unavailable(self, system_readiness_manager):
        """Test inicialización del sistema con servicios no disponibles"""
        # Mock servicios no disponibles
        system_readiness_manager.readiness_registry = None
        
        result = await system_readiness_manager.initialize_system()
        
        assert result["success"] is False
        assert "Servicios core no disponibles" in result["error"]
        assert system_readiness_manager.system_status == SystemStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_get_system_status(self, system_readiness_manager):
        """Test obtención del estado del sistema"""
        status = await system_readiness_manager.get_system_status()
        
        assert "system_status" in status
        assert "timestamp" in status
        assert "phase_status" in status
        assert "active_resources" in status
        assert "health_checks" in status
    
    @pytest.mark.asyncio
    async def test_perform_health_check(self, system_readiness_manager):
        """Test realización de health check"""
        health_result = await system_readiness_manager.perform_health_check()
        
        assert "timestamp" in health_result
        assert "health_score" in health_result
        assert "core_services" in health_result
        assert "phases" in health_result
        assert "resources" in health_result
        assert "system_status" in health_result
        assert "duration_ms" in health_result
        
        # Verificar que se registró el health check
        assert len(system_readiness_manager.health_checks) > 0
    
    @pytest.mark.asyncio
    async def test_calculate_health_score(self, system_readiness_manager):
        """Test cálculo del health score"""
        core_health = {
            "readiness_registry": "available",
            "phase_manager": "available",
            "service_factory": "available"
        }
        
        phase_health = {
            "all_phases_ready": True,
            "ready_phases": ["phase_1_core", "phase_2_ai", "phase_3_execution", "phase_4_orchestrator"],
            "pending_phases": [],
            "total_phases": 4,
            "ready_count": 4
        }
        
        resource_health = {
            "total": 3,
            "ready": 3,
            "preparing": 0,
            "error": 0
        }
        
        score = system_readiness_manager._calculate_health_score(core_health, phase_health, resource_health)
        
        assert 0.0 <= score <= 1.0
        assert score > 0.9  # Debería ser alto con todos los servicios disponibles
    
    @pytest.mark.asyncio
    async def test_get_status_history(self, system_readiness_manager):
        """Test obtención del historial de cambios de estado"""
        # Simular algunos cambios de estado
        await system_readiness_manager._record_status_change("Test 1", "ready")
        await system_readiness_manager._record_status_change("Test 2", "degraded")
        
        history = await system_readiness_manager.get_status_history()
        
        assert len(history) == 2
        assert history[0]["reason"] == "Test 1"
        assert history[1]["reason"] == "Test 2"
    
    @pytest.mark.asyncio
    async def test_start_health_monitoring(self, system_readiness_manager):
        """Test inicio del monitoreo de salud"""
        await system_readiness_manager.start_health_monitoring(interval_seconds=5)
        
        assert system_readiness_manager.health_check_interval == 5
    
    @pytest.mark.asyncio
    async def test_check_phase_status(self, system_readiness_manager):
        """Test verificación del estado de las fases"""
        phase_status = await system_readiness_manager._check_phase_status()
        
        assert "all_phases_ready" in phase_status
        assert "ready_phases" in phase_status
        assert "pending_phases" in phase_status
        assert "total_phases" in phase_status
        assert "ready_count" in phase_status
    
    @pytest.mark.asyncio
    async def test_check_core_services(self, system_readiness_manager):
        """Test verificación de servicios core"""
        core_health = await system_readiness_manager._check_core_services()
        
        assert "readiness_registry" in core_health
        assert "phase_manager" in core_health
        assert "service_factory" in core_health
        
        # Todos deberían estar disponibles
        for service_status in core_health.values():
            assert service_status == "available"


class TestWebSocketIntegration:
    """Tests para integración con WebSocket"""
    
    @pytest.mark.asyncio
    async def test_websocket_environment_preparation_flow(self, mock_factory):
        """Test flujo completo de preparación del entorno en WebSocket"""
        # Crear orchestrator
        env_orchestrator = EnvironmentPreparationOrchestrator(mock_factory)
        
        # Simular preparación del entorno
        prep_result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456"
        )
        
        assert prep_result["success"] is True
        
        # Verificar que se iniciaron los warmups
        mock_factory.background.get_warmup_engine.return_value.warmup_database.assert_called_once_with("db_123", "user_123")
        mock_factory.background.get_warmup_engine.return_value.warmup_application.assert_called_once_with("app_456", "user_123")
    
    @pytest.mark.asyncio
    async def test_websocket_system_status_flow(self, mock_factory):
        """Test flujo completo de estado del sistema en WebSocket"""
        # Crear system readiness manager
        system_manager = SystemReadinessManager(mock_factory)
        
        # Inicializar sistema
        init_result = await system_manager.initialize_system()
        assert init_result["success"] is True
        
        # Obtener estado del sistema
        system_status = await system_manager.get_system_status()
        assert "system_status" in system_status
        assert "phase_status" in system_status
        assert "active_resources" in system_status
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self, mock_factory):
        """Test manejo de errores en WebSocket"""
        # Crear orchestrator con factory que falla
        failing_factory = Mock()
        failing_factory.background.get_warmup_engine.return_value = None
        
        env_orchestrator = EnvironmentPreparationOrchestrator(failing_factory)
        
        # Intentar preparar entorno
        result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123"
        )
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_websocket_concurrent_operations(self, mock_factory):
        """Test operaciones concurrentes en WebSocket"""
        env_orchestrator = EnvironmentPreparationOrchestrator(mock_factory)
        
        # Ejecutar múltiples preparaciones concurrentemente
        tasks = [
            env_orchestrator.prepare_user_environment("user_1", "db_1", "app_1"),
            env_orchestrator.prepare_user_environment("user_2", "db_2", "app_2"),
            env_orchestrator.prepare_user_environment("user_3", "db_3", "app_3")
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Todas deberían ser exitosas
        for result in results:
            assert result["success"] is True
        
        # Verificar que se procesaron todos los usuarios
        assert len(results) == 3


class TestIntegrationScenarios:
    """Tests para escenarios de integración complejos"""
    
    @pytest.mark.asyncio
    async def test_full_user_environment_setup(self, mock_factory):
        """Test configuración completa del entorno del usuario"""
        # 1. Inicializar sistema
        system_manager = SystemReadinessManager(mock_factory)
        await system_manager.initialize_system()
        
        # 2. Preparar entorno del usuario
        env_orchestrator = EnvironmentPreparationOrchestrator(mock_factory)
        prep_result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456",
            strategy_ids=["strat_789"]
        )
        
        assert prep_result["success"] is True
        
        # 3. Verificar estado del entorno
        env_status = await env_orchestrator.get_environment_status(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456",
            strategy_ids=["strat_789"]
        )
        
        assert env_status["environment_ready"] is True
        
        # 4. Verificar estado del sistema
        system_status = await system_manager.get_system_status()
        assert "system_status" in system_status
    
    @pytest.mark.asyncio
    async def test_environment_degradation_recovery(self, mock_factory):
        """Test degradación y recuperación del entorno"""
        system_manager = SystemReadinessManager(mock_factory)
        
        # Simular degradación
        mock_factory.phase_manager.is_phase_completed.return_value = False
        
        # Verificar estado degradado
        status = await system_manager.get_system_status()
        assert status["system_status"] in ["initializing", "degraded"]
        
        # Simular recuperación
        mock_factory.phase_manager.is_phase_completed.return_value = True
        
        # Verificar recuperación
        status = await system_manager.get_system_status()
        assert status["system_status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_resource_preparation_cascade(self, mock_factory):
        """Test cascada de preparación de recursos"""
        env_orchestrator = EnvironmentPreparationOrchestrator(mock_factory)
        
        # Preparar recursos en secuencia
        db_result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            db_uuid="db_123"
        )
        assert db_result["success"] is True
        
        app_result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            app_id="app_456"
        )
        assert app_result["success"] is True
        
        strategy_result = await env_orchestrator.prepare_user_environment(
            user_id="user_123",
            strategy_ids=["strat_789"]
        )
        assert strategy_result["success"] is True
        
        # Verificar estado final
        final_status = await env_orchestrator.get_environment_status(
            user_id="user_123",
            db_uuid="db_123",
            app_id="app_456",
            strategy_ids=["strat_789"]
        )
        
        assert final_status["environment_ready"] is True
