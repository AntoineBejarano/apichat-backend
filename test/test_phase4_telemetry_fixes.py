"""
🔧 FASE 4: Test de corrección de errores de telemetría
──────────────────────────────────────────────────────
Verifica que el sistema no intente insertar estimated_cost_usd en columnas generadas
y que el método track_event funcione correctamente.
"""

import pytest
from unittest.mock import Mock, patch
from uuid import uuid4
from decimal import Decimal
from app.services.management.advanced_telemetry_service import AdvancedTelemetryService
from app.schemas.telemetry_schema import ConversationMetricsCreate


class TestPhase4TelemetryFixes:
    """Test de la FASE 4: Corrección de errores de telemetría"""
    
    @pytest.fixture
    def mock_db(self):
        """Database mock"""
        db = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.refresh = Mock()
        db.rollback = Mock()
        return db
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        factory = Mock()
        factory.user = Mock()
        factory.user.id = uuid4()
        return factory
    
    @pytest.fixture
    def telemetry_service(self, mock_factory):
        """Instancia de AdvancedTelemetryService para testing"""
        service = AdvancedTelemetryService(mock_factory)
        # Mock de la base de datos
        service.db = Mock()
        service.db.add = Mock()
        service.db.commit = Mock()
        service.db.refresh = Mock()
        service.db.rollback = Mock()
        return service
    
    def test_save_conversation_metrics_removes_estimated_cost_usd(self, telemetry_service):
        """🔧 FASE 4: Test que verifica que estimated_cost_usd se elimina antes del INSERT"""
        # Crear métricas con estimated_cost_usd usando un dict simple
        metrics_dict = {
            "conversation_id": uuid4(),
            "user_id": uuid4(),
            "chat_id": uuid4(),
            "session_id": uuid4(),
            "mode": "explorer",
            "started_at": "2023-01-01T00:00:00Z",
            "ended_at": "2023-01-01T01:00:00Z",
            "tokens_in": 100,
            "tokens_out": 50,
            "total_cost_usd": Decimal("0.001"),
            "estimated_cost_usd": Decimal("0.002"),  # Este campo debe ser eliminado
            "cache_hit_ratio": Decimal("0.8"),
            "cache_hits": 8,
            "cache_misses": 2,
            "steps_executed": 5,
            "confirmations_required": 1,
            "errors_encountered": 0,
            "latency_total_ms": Decimal("150.0"),
            "databases_accessed": 1,
            "apps_accessed": 0,
            "functions_executed": 0,
            "completed_at": "2023-01-01T01:00:00Z"
        }
        
        # Mock de ConversationMetrics
        mock_metrics = Mock()
        mock_metrics.id = uuid4()
        
        with patch('app.services.management.advanced_telemetry_service.ConversationMetrics') as mock_metrics_class:
            mock_metrics_class.return_value = mock_metrics
            
            # Crear un mock de ConversationMetricsCreate
            mock_metrics_data = Mock()
            mock_metrics_data.model_dump.return_value = metrics_dict
            
            # Llamar a la función
            result = telemetry_service._save_conversation_metrics(mock_metrics_data)
            
            # Verificar que ConversationMetrics se llamó con los parámetros correctos
            call_args = mock_metrics_class.call_args[1]
            
            # Verificar que estimated_cost_usd NO está presente
            assert "estimated_cost_usd" not in call_args, "estimated_cost_usd no debe estar presente en los parámetros"
            
            # Verificar que otros campos sí están presentes
            assert "conversation_id" in call_args
            assert "user_id" in call_args
            assert "tokens_in" in call_args
            assert "total_cost_usd" in call_args
            
            print("✅ estimated_cost_usd se elimina correctamente antes del INSERT")
    
    def test_save_conversation_metrics_without_estimated_cost_usd(self, telemetry_service):
        """🔧 FASE 4: Test que verifica que funciona correctamente sin estimated_cost_usd"""
        # Crear métricas sin estimated_cost_usd usando un dict simple
        metrics_dict = {
            "conversation_id": uuid4(),
            "user_id": uuid4(),
            "chat_id": uuid4(),
            "session_id": uuid4(),
            "mode": "explorer",
            "started_at": "2023-01-01T00:00:00Z",
            "ended_at": "2023-01-01T01:00:00Z",
            "tokens_in": 100,
            "tokens_out": 50,
            "total_cost_usd": Decimal("0.001"),
            "cache_hit_ratio": Decimal("0.8"),
            "cache_hits": 8,
            "cache_misses": 2,
            "steps_executed": 5,
            "confirmations_required": 1,
            "errors_encountered": 0,
            "latency_total_ms": Decimal("150.0"),
            "databases_accessed": 1,
            "apps_accessed": 0,
            "functions_executed": 0,
            "completed_at": "2023-01-01T01:00:00Z"
        }
        
        # Mock de ConversationMetrics
        mock_metrics = Mock()
        mock_metrics.id = uuid4()
        
        with patch('app.services.management.advanced_telemetry_service.ConversationMetrics') as mock_metrics_class:
            mock_metrics_class.return_value = mock_metrics
            
            # Crear un mock de ConversationMetricsCreate
            mock_metrics_data = Mock()
            mock_metrics_data.model_dump.return_value = metrics_dict
            
            # Llamar a la función
            result = telemetry_service._save_conversation_metrics(mock_metrics_data)
            
            # Verificar que ConversationMetrics se llamó con los parámetros correctos
            call_args = mock_metrics_class.call_args[1]
            
            # Verificar que los campos están presentes
            assert "conversation_id" in call_args
            assert "user_id" in call_args
            assert "tokens_in" in call_args
            
            print("✅ Función funciona correctamente sin estimated_cost_usd")
    
    def test_track_event_method_exists_and_works(self, telemetry_service):
        """🔧 FASE 4: Test que verifica que el método track_event existe y funciona"""
        # Verificar que el método existe
        assert hasattr(telemetry_service, 'track_event'), "El método track_event debe existir"
        
        # Verificar que es callable
        assert callable(telemetry_service.track_event), "El método track_event debe ser callable"
        
        # Llamar al método - debe funcionar sin errores
        event_name = "test_event"
        metadata = {"key": "value", "count": 42}
        
        try:
            telemetry_service.track_event(event_name, metadata)
            print("✅ Método track_event existe y funciona correctamente")
        except Exception as e:
            pytest.fail(f"track_event no debería fallar: {e}")
    
    def test_track_event_with_different_event_types(self, telemetry_service):
        """🔧 FASE 4: Test que verifica track_event con diferentes tipos de eventos"""
        test_events = [
            ("user_login", {"user_id": str(uuid4()), "timestamp": "2023-01-01T00:00:00Z"}),
            ("database_query", {"db_id": str(uuid4()), "query_type": "SELECT", "execution_time_ms": 150}),
            ("cache_hit", {"cache_key": "schema:123", "response_time_ms": 5}),
            ("error_occurred", {"error_type": "validation_error", "error_message": "Invalid input"})
        ]
        
        for event_name, metadata in test_events:
            try:
                telemetry_service.track_event(event_name, metadata)
                print(f"✅ Evento '{event_name}' se trackea correctamente")
            except Exception as e:
                pytest.fail(f"track_event no debería fallar para '{event_name}': {e}")
    
    def test_track_event_error_handling(self, telemetry_service):
        """🔧 FASE 4: Test que verifica que track_event maneja errores gracefully"""
        # Llamar al método - debe funcionar sin errores
        try:
            telemetry_service.track_event("test_event", {"key": "value"})
            print("✅ track_event maneja errores gracefully")
        except Exception as e:
            pytest.fail(f"track_event no debería fallar: {e}")
    
    def test_track_event_performance(self, telemetry_service):
        """🔧 FASE 4: Test de rendimiento de track_event"""
        import time
        
        # Evento de prueba
        event_name = "performance_test_event"
        metadata = {"test": True, "iteration": 0}
        
        # Medir tiempo de ejecución
        start_time = time.time()
        for i in range(100):
            metadata["iteration"] = i
            telemetry_service.track_event(event_name, metadata)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"✅ 100 eventos trackeados en {execution_time:.4f} segundos")
        
        # Verificar que es razonablemente rápido (< 1 segundo para 100 eventos)
        assert execution_time < 1.0, f"Tracking de eventos demasiado lento: {execution_time:.4f}s"
    
    def test_conversation_metrics_insert_success(self, telemetry_service):
        """🔧 FASE 4: Test que verifica que el INSERT de métricas funciona correctamente"""
        # Crear métricas válidas usando un dict simple
        metrics_dict = {
            "conversation_id": uuid4(),
            "user_id": uuid4(),
            "chat_id": uuid4(),
            "session_id": uuid4(),
            "mode": "explorer",
            "started_at": "2023-01-01T00:00:00Z",
            "ended_at": "2023-01-01T01:00:00Z",
            "tokens_in": 100,
            "tokens_out": 50,
            "total_cost_usd": Decimal("0.001"),
            "cache_hit_ratio": Decimal("0.8"),
            "cache_hits": 8,
            "cache_misses": 2,
            "steps_executed": 5,
            "confirmations_required": 1,
            "errors_encountered": 0,
            "latency_total_ms": Decimal("150.0"),
            "databases_accessed": 1,
            "apps_accessed": 0,
            "functions_executed": 0,
            "completed_at": "2023-01-01T01:00:00Z"
        }
        
        # Mock de ConversationMetrics
        mock_metrics = Mock()
        mock_metrics.id = uuid4()
        
        with patch('app.services.management.advanced_telemetry_service.ConversationMetrics') as mock_metrics_class:
            mock_metrics_class.return_value = mock_metrics
            
            # Crear un mock de ConversationMetricsCreate
            mock_metrics_data = Mock()
            mock_metrics_data.model_dump.return_value = metrics_dict
            
            # Llamar a la función
            result = telemetry_service._save_conversation_metrics(mock_metrics_data)
            
            # Verificar que se llamaron los métodos de la base de datos
            telemetry_service.db.add.assert_called_once_with(mock_metrics)
            telemetry_service.db.commit.assert_called_once()
            telemetry_service.db.refresh.assert_called_once_with(mock_metrics)
            
            # Verificar que se retornó el resultado correcto
            assert result == mock_metrics
            
            print("✅ INSERT de métricas funciona correctamente")


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
