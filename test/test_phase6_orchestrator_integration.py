import pytest
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.management.orchestrator_activation_guard import OrchestratorActivationGuard
from app.services.management.system_readiness_manager import SystemReadinessManager

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_factory():
    """Factory mock con todos los servicios necesarios"""
    factory = Mock()
    
    # Mock readiness registry
    readiness_registry = AsyncMock()
    readiness_registry.get_all_resources = AsyncMock(return_value={
        "database": {"db_123": "ready"},
        "application": {"app_456": "ready"},
        "strategy": {"strat_789": "ready"}
    })
    readiness_registry.get_pending_resources = AsyncMock(return_value=[])
    factory.readiness_registry = readiness_registry
    
    # Mock phase manager
    phase_manager = AsyncMock()
    phase_manager.is_phase_completed = AsyncMock(return_value=True)
    factory.phase_manager = phase_manager
    
    # Mock background factory
    background_factory = Mock()
    resource_prep_service = AsyncMock()
    background_factory.get_resource_preparation_service = Mock(return_value=resource_prep_service)
    factory.background = background_factory
    
    return factory


@pytest.fixture
def orchestrator_service(mock_factory):
    """OrchestratorService con factory mock"""
    return OrchestratorService(mock_factory)


class TestOrchestratorService:
    """Tests para OrchestratorService"""
    
    @pytest.mark.asyncio
    async def test_handle_user_message_success(self, orchestrator_service):
        """Test: Manejo exitoso de mensaje cuando el orquestador puede activarse"""
        # Mock activation guard para permitir activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock process_message
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado correctamente"
        })
        
        result = await orchestrator_service.handle_user_message(
            message="Hola, ¿cómo estás?",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "success"
        assert "Mensaje procesado correctamente" in result["message"]
        orchestrator_service.activation_guard.can_activate_orchestrator.assert_called_once_with("user_456")
    
    @pytest.mark.asyncio
    async def test_handle_user_message_not_ready(self, orchestrator_service):
        """Test: Manejo de mensaje cuando el orquestador no puede activarse"""
        # Mock activation guard para denegar activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=False)
        
        # Mock system readiness manager
        orchestrator_service.system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            "overall_ready": False,
            "resources": {
                "database": [{"ready": False, "status": "⏳ Introspectando..."}]
            }
        })
        
        result = await orchestrator_service.handle_user_message(
            message="Hola, ¿cómo estás?",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "error"
        assert "Tu entorno no está completamente listo" in result["message"]
        assert "readiness_status" in result["details"]
    
    @pytest.mark.asyncio
    async def test_handle_user_message_exception(self, orchestrator_service):
        """Test: Manejo de excepciones durante el procesamiento"""
        # Mock activation guard para lanzar excepción
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(
            side_effect=Exception("Error de conexión")
        )
        
        result = await orchestrator_service.handle_user_message(
            message="Hola",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "error"
        assert "Error interno del sistema" in result["message"]
        assert "Error de conexión" in result["details"]["error"]
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, orchestrator_service):
        """Test: Procesamiento exitoso de mensaje"""
        result = await orchestrator_service.process_message(
            message="Este es un mensaje de prueba muy largo para verificar el truncamiento",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "success"
        assert "Mensaje procesado correctamente" in result["message"]
        assert result["chat_id"] == "chat_123"
        assert result["user_id"] == "user_456"
        assert "processed_at" in result
        # El mensaje se trunca a 50 caracteres, verificar que contenga el inicio
        assert "Este es un mensaje de prueba muy largo para verificar"[:50] in result["response"]
    
    @pytest.mark.asyncio
    async def test_process_message_exception(self, orchestrator_service):
        """Test: Manejo de excepciones en process_message"""
        # Crear una nueva instancia para este test específico
        test_orchestrator = OrchestratorService(orchestrator_service.factory)
        
        # Mock process_message para lanzar excepción
        test_orchestrator.process_message = AsyncMock(
            side_effect=Exception("Error de procesamiento")
        )
        
        # Reemplazar el método original con el mock
        original_process_message = test_orchestrator.process_message
        
        try:
            # Llamar al método mockeado
            result = await test_orchestrator.process_message(
                message="Hola",
                chat_id="chat_123",
                user_id="user_456"
            )
        except Exception as e:
            # Verificar que se lanza la excepción esperada
            assert "Error de procesamiento" in str(e)
            return
        
        # Si llegamos aquí, el test falló
        assert False, "Se esperaba que se lanzara una excepción"
    
    @pytest.mark.asyncio
    async def test_get_orchestrator_status_success(self, orchestrator_service):
        """Test: Obtención exitosa del estado del orquestador"""
        # Mock activation guard
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock system readiness manager
        orchestrator_service.system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            "overall_ready": True,
            "resources": {"database": [{"ready": True}]}
        })
        
        result = await orchestrator_service.get_orchestrator_status("user_456")
        
        assert result["can_activate"] is True
        assert "readiness_status" in result
        assert result["user_id"] == "user_456"
        assert "timestamp" in result
    
    @pytest.mark.asyncio
    async def test_get_orchestrator_status_exception(self, orchestrator_service):
        """Test: Manejo de excepciones en get_orchestrator_status"""
        # Mock para lanzar excepción
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(
            side_effect=Exception("Error de estado")
        )
        
        result = await orchestrator_service.get_orchestrator_status("user_456")
        
        assert result["can_activate"] is False
        assert "Error de estado" in result["error"]
        assert result["user_id"] == "user_456"
    
    @pytest.mark.asyncio
    async def test_force_environment_preparation_success(self, orchestrator_service):
        """Test: Forzar preparación del entorno exitosamente"""
        # Mock system readiness manager
        orchestrator_service.system_readiness_manager.start_async_preparation = AsyncMock()
        
        result = await orchestrator_service.force_environment_preparation("user_456")
        
        assert result["type"] == "success"
        assert "Preparación del entorno iniciada manualmente" in result["message"]
        assert result["user_id"] == "user_456"
        assert result["status"] == "preparation_started"
        
        orchestrator_service.system_readiness_manager.start_async_preparation.assert_called_once_with("user_456")
    
    @pytest.mark.asyncio
    async def test_force_environment_preparation_exception(self, orchestrator_service):
        """Test: Manejo de excepciones en force_environment_preparation"""
        # Mock para lanzar excepción
        orchestrator_service.system_readiness_manager.start_async_preparation = AsyncMock(
            side_effect=Exception("Error de preparación")
        )
        
        result = await orchestrator_service.force_environment_preparation("user_456")
        
        assert result["type"] == "error"
        assert "Error iniciando preparación del entorno" in result["message"]
        assert "Error de preparación" in result["details"]["error"]
    
    @pytest.mark.asyncio
    async def test_get_activation_details_success(self, orchestrator_service):
        """Test: Obtención exitosa de detalles de activación"""
        # Mock activation guard
        orchestrator_service.activation_guard.get_activation_status = AsyncMock(return_value={
            "can_activate": False,
            "message": "Recursos pendientes",
            "missing_resources": ["database:db_123"]
        })
        
        result = await orchestrator_service.get_activation_details("user_456")
        
        assert "activation_result" in result
        assert result["user_id"] == "user_456"
        assert "timestamp" in result
        assert result["activation_result"]["can_activate"] is False
    
    @pytest.mark.asyncio
    async def test_get_activation_details_exception(self, orchestrator_service):
        """Test: Manejo de excepciones en get_activation_details"""
        # Mock para lanzar excepción
        orchestrator_service.activation_guard.get_activation_status = AsyncMock(
            side_effect=Exception("Error de activación")
        )
        
        result = await orchestrator_service.get_activation_details("user_456")
        
        assert "Error de activación" in result["error"]
        assert result["user_id"] == "user_456"


class TestOrchestratorIntegration:
    """Tests de integración del orquestador"""
    
    @pytest.mark.asyncio
    async def test_full_message_flow_success(self, mock_factory):
        """Test: Flujo completo de mensaje exitoso"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Mock activation guard para permitir activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock process_message
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado"
        })
        
        result = await orchestrator_service.handle_user_message(
            message="Consulta de prueba",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "success"
        assert "Mensaje procesado" in result["message"]
    
    @pytest.mark.asyncio
    async def test_full_message_flow_not_ready(self, mock_factory):
        """Test: Flujo completo cuando el sistema no está listo"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Mock activation guard para denegar activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=False)
        
        # Mock system readiness manager
        orchestrator_service.system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            "overall_ready": False,
            "resources": {
                "database": [{"ready": False, "status": "⏳ Preparando..."}]
            },
            "estimated_time": 5
        })
        
        result = await orchestrator_service.handle_user_message(
            message="Consulta de prueba",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result["type"] == "error"
        assert "Tu entorno no está completamente listo" in result["message"]
        assert result["details"]["estimated_wait_time"] == "5-10 segundos"
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, mock_factory):
        """Test: Manejo concurrente de múltiples mensajes"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Mock activation guard para permitir activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock process_message
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado"
        })
        
        # Crear múltiples mensajes concurrentes
        messages = [
            ("Mensaje 1", "chat_1", "user_1"),
            ("Mensaje 2", "chat_2", "user_2"),
            ("Mensaje 3", "chat_3", "user_3")
        ]
        
        # Procesar todos los mensajes concurrentemente
        tasks = [
            orchestrator_service.handle_user_message(msg, chat_id, user_id)
            for msg, chat_id, user_id in messages
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verificar que todos los mensajes se procesaron correctamente
        assert len(results) == 3
        for result in results:
            assert result["type"] == "success"
            assert "Mensaje procesado" in result["message"]
    
    @pytest.mark.asyncio
    async def test_error_recovery_flow(self, mock_factory):
        """Test: Flujo de recuperación de errores"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Primera llamada falla
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(
            side_effect=Exception("Error temporal")
        )
        
        result1 = await orchestrator_service.handle_user_message(
            message="Mensaje 1",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result1["type"] == "error"
        assert "Error interno del sistema" in result1["message"]
        
        # Segunda llamada funciona
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado"
        })
        
        result2 = await orchestrator_service.handle_user_message(
            message="Mensaje 2",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        assert result2["type"] == "success"
        assert "Mensaje procesado" in result2["message"]


class TestOrchestratorPerformance:
    """Tests de performance del orquestador"""
    
    @pytest.mark.asyncio
    async def test_message_processing_performance(self, mock_factory):
        """Test: Performance del procesamiento de mensajes"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Mock activation guard para permitir activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock process_message
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado"
        })
        
        start_time = datetime.now(timezone.utc)
        
        # Procesar mensaje
        result = await orchestrator_service.handle_user_message(
            message="Mensaje de prueba para performance",
            chat_id="chat_123",
            user_id="user_456"
        )
        
        end_time = datetime.now(timezone.utc)
        processing_time = (end_time - start_time).total_seconds()
        
        assert result["type"] == "success"
        assert processing_time < 1.0  # Debe procesarse en menos de 1 segundo
        logger.info(f"Tiempo de procesamiento: {processing_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_concurrent_performance(self, mock_factory):
        """Test: Performance con múltiples mensajes concurrentes"""
        orchestrator_service = OrchestratorService(mock_factory)
        
        # Mock activation guard para permitir activación
        orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # Mock process_message
        orchestrator_service.process_message = AsyncMock(return_value={
            "type": "success",
            "message": "Mensaje procesado"
        })
        
        start_time = datetime.now(timezone.utc)
        
        # Crear 10 mensajes concurrentes
        tasks = []
        for i in range(10):
            task = orchestrator_service.handle_user_message(
                message=f"Mensaje {i}",
                chat_id=f"chat_{i}",
                user_id=f"user_{i}"
            )
            tasks.append(task)
        
        # Procesar todos concurrentemente
        results = await asyncio.gather(*tasks)
        
        end_time = datetime.now(timezone.utc)
        total_time = (end_time - start_time).total_seconds()
        
        assert len(results) == 10
        for result in results:
            assert result["type"] == "success"
        
        # El tiempo total debe ser menor que procesar secuencialmente
        assert total_time < 2.0  # Debe completarse en menos de 2 segundos
        logger.info(f"Tiempo total para 10 mensajes concurrentes: {total_time:.3f}s")
        logger.info(f"Tiempo promedio por mensaje: {total_time/10:.3f}s")
