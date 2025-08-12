"""
Tests para la Fase 15 - Hardening (timeouts, reintentos, undo)
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from app.services.execution.retry_service import RetryService, retry_service
from app.services.execution.undo_service import UndoService, undo_service, UndoOperation
from app.core.config import settings


class TestRetryService:
    """Tests para el servicio de reintentos con backoff."""
    
    def test_retry_service_initialization(self):
        """Test que RetryService se inicializa correctamente."""
        service = RetryService()
        assert service.max_retries == settings.MAX_RETRIES
        assert service.backoff_factor == settings.RETRY_BACKOFF_FACTOR
        assert service.initial_delay == settings.RETRY_DELAY_SECONDS
    
    def test_retry_with_backoff_decorator(self):
        """Test del decorador de reintentos síncrono."""
        call_count = 0
        
        @retry_service.retry_with_backoff(max_retries=2, initial_delay=0.1)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"
        
        result = failing_function()
        assert result == "success"
        assert call_count == 3  # 1 fallo + 2 reintentos
    
    def test_retry_with_backoff_max_retries_exceeded(self):
        """Test que falla después de exceder reintentos máximos."""
        call_count = 0
        
        @retry_service.retry_with_backoff(max_retries=2, initial_delay=0.1)
        def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            always_failing_function()
        
        assert call_count == 3  # 1 fallo + 2 reintentos
    
    def test_retry_with_backoff_timeout(self):
        """Test de timeout en reintentos."""
        @retry_service.retry_with_backoff(timeout=0.1, initial_delay=0.05)
        def slow_function():
            time.sleep(0.2)  # Más lento que el timeout
            return "success"
        
        with pytest.raises(TimeoutError):
            slow_function()
    
    def test_should_retry_method(self):
        """Test del método should_retry."""
        service = RetryService()
        
        # Errores que deben causar reintento
        assert service.should_retry(ConnectionError("Connection refused"))
        assert service.should_retry(TimeoutError("Request timed out"))
        assert service.should_retry(OSError("Network is unreachable"))
        
        # Errores que no deben causar reintento
        assert not service.should_retry(ValueError("Invalid input"))
        assert not service.should_retry(TypeError("Wrong type"))
    
    def test_get_retry_delay(self):
        """Test del cálculo de delays de reintento."""
        service = RetryService()
        
        # Primer intento
        delay1 = service.get_retry_delay(0, base_delay=1.0)
        assert 0.9 <= delay1 <= 1.1  # Con jitter
        
        # Segundo intento
        delay2 = service.get_retry_delay(1, base_delay=1.0)
        assert delay2 > delay1  # Debe ser mayor por backoff
        
        # Delay máximo
        delay_max = service.get_retry_delay(10, base_delay=1.0)
        assert delay_max <= 60  # Máximo 60 segundos


class TestUndoService:
    """Tests para el servicio de undo/rollback."""
    
    def test_undo_service_initialization(self):
        """Test que UndoService se inicializa correctamente."""
        service = UndoService()
        assert len(service.undo_operations) == 0
        assert len(service.undo_history) == 0
    
    def test_register_undo_operation(self):
        """Test de registro de operaciones de undo."""
        service = UndoService()
        
        def mock_undo_function():
            return "undone"
        
        undo_id = service.register_undo_operation(
            operation_type="db_query",
            description="Test operation",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        assert undo_id in service.undo_operations
        assert service.undo_operations[undo_id].description == "Test operation"
        assert service.undo_operations[undo_id].operation_type == "db_query"
    
    def test_can_undo(self):
        """Test del método can_undo."""
        service = UndoService()
        
        def mock_undo_function():
            return "undone"
        
        undo_id = service.register_undo_operation(
            operation_type="db_query",
            description="Test operation",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        assert service.can_undo(undo_id) == True
        
        # Ejecutar undo
        service.execute_undo(undo_id)
        assert service.can_undo(undo_id) == False
    
    def test_execute_undo(self):
        """Test de ejecución de undo."""
        service = UndoService()
        
        def mock_undo_function():
            return "undone"
        
        undo_id = service.register_undo_operation(
            operation_type="db_query",
            description="Test operation",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        result = service.execute_undo(undo_id)
        assert result["success"] == True
        assert result["result"] == "undone"
        
        # Verificar que se movió al historial
        assert undo_id not in service.undo_operations
        assert len(service.undo_history) == 1
    
    def test_execute_undo_nonexistent(self):
        """Test de undo de operación inexistente."""
        service = UndoService()
        
        result = service.execute_undo("nonexistent_id")
        assert result["success"] == False
        assert "no encontrada" in result["error"]
    
    def test_execute_undo_already_executed(self):
        """Test de undo de operación ya ejecutada."""
        service = UndoService()
        
        def mock_undo_function():
            return "undone"
        
        undo_id = service.register_undo_operation(
            operation_type="db_query",
            description="Test operation",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        # Ejecutar undo una vez
        service.execute_undo(undo_id)
        
        # Intentar ejecutar undo de nuevo (debe fallar porque ya no existe)
        result = service.execute_undo(undo_id)
        assert result["success"] == False
        assert "no encontrada" in result["error"]
    
    def test_get_undo_suggestions(self):
        """Test de generación de sugerencias de undo."""
        service = UndoService()
        
        # Registrar algunas operaciones
        def mock_undo_function():
            return "undone"
        
        service.register_undo_operation(
            operation_type="db_query",
            description="DELETE users",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        service.register_undo_operation(
            operation_type="api_function",
            description="create_user",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        suggestions = service.get_undo_suggestions({})
        assert len(suggestions) == 2
        
        # Verificar prioridades
        db_suggestion = next(s for s in suggestions if s["type"] == "db_operations")
        assert db_suggestion["priority"] == "high"  # DELETE es alta prioridad
        
        api_suggestion = next(s for s in suggestions if s["type"] == "api_operations")
        assert api_suggestion["priority"] == "medium"
    
    def test_cleanup_expired_operations(self):
        """Test de limpieza de operaciones expiradas."""
        service = UndoService()
        
        # Registrar operación
        def mock_undo_function():
            return "undone"
        
        undo_id = service.register_undo_operation(
            operation_type="db_query",
            description="Test operation",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        # Simular operación expirada (más de 24 horas)
        from datetime import timedelta
        service.undo_operations[undo_id].timestamp = service.undo_operations[undo_id].timestamp - timedelta(hours=25)
        
        cleaned = service.cleanup_expired_operations(max_age_hours=24)
        assert cleaned == 1
        assert undo_id not in service.undo_operations


class TestHardeningIntegration:
    """Tests de integración para hardening."""
    
    def test_config_timeouts_available(self):
        """Test que las configuraciones de timeout están disponibles."""
        assert hasattr(settings, 'LLM_TIMEOUT_SECONDS')
        assert hasattr(settings, 'DB_QUERY_TIMEOUT_SECONDS')
        assert hasattr(settings, 'HTTP_REQUEST_TIMEOUT_SECONDS')
        assert hasattr(settings, 'MAX_RETRIES')
        assert hasattr(settings, 'RETRY_BACKOFF_FACTOR')
        assert hasattr(settings, 'RETRY_DELAY_SECONDS')
        
        # Verificar valores por defecto
        assert settings.LLM_TIMEOUT_SECONDS == 60
        assert settings.DB_QUERY_TIMEOUT_SECONDS == 30
        assert settings.HTTP_REQUEST_TIMEOUT_SECONDS == 30
        assert settings.MAX_RETRIES == 3
        assert settings.RETRY_BACKOFF_FACTOR == 2.0
        assert settings.RETRY_DELAY_SECONDS == 1.0
    
    def test_retry_service_global_instance(self):
        """Test que la instancia global de retry_service está disponible."""
        assert retry_service is not None
        assert isinstance(retry_service, RetryService)
    
    def test_undo_service_global_instance(self):
        """Test que la instancia global de undo_service está disponible."""
        assert undo_service is not None
        assert isinstance(undo_service, UndoService)
    
    def test_undo_operation_class(self):
        """Test de la clase UndoOperation."""
        def mock_undo_function():
            return "undone"
        
        undo_op = UndoOperation(
            operation_id="test_id",
            operation_type="test_type",
            description="Test description",
            undo_function=mock_undo_function,
            undo_args={}
        )
        
        assert undo_op.operation_id == "test_id"
        assert undo_op.operation_type == "test_type"
        assert undo_op.description == "Test description"
        assert undo_op.executed == False
        
        # Test de ejecución
        result = undo_op.execute_undo()
        assert result["success"] == True
        assert result["result"] == "undone"
        assert undo_op.executed == True


@pytest.mark.asyncio
class TestAsyncRetryService:
    """Tests para reintentos asíncronos."""
    
    async def test_retry_with_backoff_async_decorator(self):
        """Test del decorador de reintentos asíncrono."""
        call_count = 0
        
        @retry_service.retry_with_backoff_async(max_retries=2, initial_delay=0.1)
        async def failing_async_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                await asyncio.sleep(0.1)
                raise ConnectionError("Connection failed")
            return "success"
        
        result = await failing_async_function()
        assert result == "success"
        assert call_count == 3  # 1 fallo + 2 reintentos
    
    async def test_retry_with_backoff_async_timeout(self):
        """Test de timeout en reintentos asíncronos."""
        @retry_service.retry_with_backoff_async(timeout=0.1, initial_delay=0.05)
        async def slow_async_function():
            await asyncio.sleep(0.2)  # Más lento que el timeout
            return "success"
        
        with pytest.raises(TimeoutError):
            await slow_async_function()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
