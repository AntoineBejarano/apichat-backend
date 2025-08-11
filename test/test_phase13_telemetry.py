"""
🎯 FASE 13: Tests de telemetría y KPIs

Tests para verificar que el sistema de telemetría funciona correctamente
y emite snapshots al final de cada turno.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from app.services.management.advanced_telemetry_service import (
    AdvancedTelemetryService, TelemetryContext
)
from app.services.orchestrator_service import OrchestratorService
from app.schemas.chat_schema import ChatMessage
from app.common.enums import Mode


class TestPhase13Telemetry:
    """Tests para la FASE 13: Telemetría y KPIs mínimos."""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock para testing."""
        factory = Mock()
        factory.user.id = uuid4()
        factory.db = Mock()
        
        # Mock del ws_emitter con métodos asíncronos
        mock_ws_emitter = Mock()
        # Mockear todos los métodos asíncronos del ws_emitter
        for method_name in ['emit_status_typing', 'emit_telemetry_snapshot', 'emit_status_progress', 
                           'emit_error', 'emit_success', 'emit_notice_info', 'emit_chat_message']:
            setattr(mock_ws_emitter, method_name, AsyncMock(return_value=True))
        factory.get_ws_emitter = Mock(return_value=mock_ws_emitter)
        
        factory.get_advanced_telemetry_service = Mock(return_value=Mock())
        
        # Mockear otros servicios que se usan en el test
        factory.get_chat_service = Mock(return_value=Mock())
        factory.get_chat_history_service = Mock(return_value=Mock())
        factory.get_session_service = Mock(return_value=Mock())
        
        return factory
    
    @pytest.fixture
    def mock_telemetry_service(self):
        """Servicio de telemetría mock."""
        service = Mock()
        service.start_conversation_tracking = Mock(return_value=Mock())
        service.end_conversation_tracking = Mock(return_value=Mock())
        service.track_step_execution = Mock()
        service.track_error = Mock()
        return service
    
    @pytest.fixture
    def orchestrator_service(self, mock_factory, mock_telemetry_service):
        """Orchestrator service con telemetría mock."""
        mock_factory.get_advanced_telemetry_service.return_value = mock_telemetry_service
        return OrchestratorService(mock_factory)
    
    def test_telemetry_context_initialization(self):
        """Test: El contexto de telemetría se inicializa correctamente."""
        # Arrange
        conversation_id = str(uuid4())
        user_id = uuid4()
        chat_id = uuid4()
        mode = "guided"
        
        # Act
        context = TelemetryContext(
            conversation_id=conversation_id,
            user_id=user_id,
            chat_id=chat_id,
            session_id=None,
            mode=mode,
            started_at=datetime.now(timezone.utc)
        )
        
        # Assert
        assert context.conversation_id == conversation_id
        assert context.user_id == user_id
        assert context.chat_id == chat_id
        assert context.mode == mode
        assert context.tokens_in == 0
        assert context.tokens_out == 0
        assert context.cache_hits == 0
        assert context.cache_misses == 0
        assert context.steps_executed == 0
        assert context.confirmations_required == 0
        assert context.errors_encountered == 0
    
    def test_telemetry_context_token_tracking(self):
        """Test: El contexto de telemetría rastrea tokens correctamente."""
        # Arrange
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=datetime.now(timezone.utc)
        )
        
        # Act
        context.add_tokens(tokens_in=100, tokens_out=50)
        context.add_tokens(tokens_in=200, tokens_out=75)
        
        # Assert
        assert context.tokens_in == 300
        assert context.tokens_out == 125
    
    def test_telemetry_context_cache_tracking(self):
        """Test: El contexto de telemetría rastrea cache correctamente."""
        # Arrange
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=datetime.now(timezone.utc)
        )
        
        # Act
        context.add_cache_operation(hit=True)
        context.add_cache_operation(hit=False)
        context.add_cache_operation(hit=True)
        
        # Assert
        assert context.cache_hits == 2
        assert context.cache_misses == 1
        assert context.get_cache_hit_ratio() == 2/3
    
    def test_telemetry_context_latency_tracking(self):
        """Test: El contexto de telemetría rastrea latencias correctamente."""
        # Arrange
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=datetime.now(timezone.utc)
        )
        
        # Act
        context.add_latency("llm", 100.0)
        context.add_latency("db", 50.0)
        context.add_latency("cache", 25.0)
        
        # Assert
        assert context.latency_llm_ms == 100.0
        assert context.latency_db_ms == 50.0
        assert context.latency_cache_ms == 25.0
        assert context.get_total_latency_ms() == 175.0
    
    def test_telemetry_context_resource_tracking(self):
        """Test: El contexto de telemetría rastrea recursos correctamente."""
        # Arrange
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=datetime.now(timezone.utc)
        )
        
        # Act
        context.add_resource_access("database", "db1")
        context.add_resource_access("database", "db2")
        context.add_resource_access("app", "app1")
        context.add_resource_access("function", "func1")
        
        # Assert
        assert len(context.databases_accessed) == 2
        assert len(context.apps_accessed) == 1
        assert len(context.functions_executed) == 1
        assert "db1" in context.databases_accessed
        assert "db2" in context.databases_accessed
        assert "app1" in context.apps_accessed
        assert "func1" in context.functions_executed
    
    def test_orchestrator_telemetry_integration(self, orchestrator_service, mock_telemetry_service):
        """Test: El orquestador integra telemetría correctamente."""
        # Arrange
        mock_telemetry_service.start_conversation_tracking.return_value = Mock()

        # Act - Solo verificar que el servicio de telemetría esté disponible
        assert orchestrator_service.telemetry_service is not None
        assert orchestrator_service.current_telemetry_context is None  # Inicialmente None

        # Assert
        mock_telemetry_service.start_conversation_tracking.assert_not_called()  # No se ha llamado aún
    
    @pytest.mark.asyncio
    async def test_telemetry_snapshot_emission(self, orchestrator_service):
        """Test: El orquestador emite snapshots de telemetría correctamente."""
        # Arrange
        tokens_in = 100
        tokens_out = 50
        latency_ms = 150.0
        cache_hit_ratio = 0.8
        steps_executed = 3
        confirmations_required = 1
        mode = Mode.GUIDED
        
        # Mock del ws_emitter
        orchestrator_service.ws_emitter = AsyncMock()
        
        # Act
        result = await orchestrator_service.emit_telemetry_snapshot(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cache_hit_ratio=cache_hit_ratio,
            steps_executed=steps_executed,
            confirmations_required=confirmations_required,
            mode=mode
        )
        
        # Assert
        assert result is True
        orchestrator_service.ws_emitter.emit.assert_called_once()
    
    def test_telemetry_context_to_conversation_metrics(self):
        """Test: El contexto se convierte a métricas de conversación correctamente."""
        # Arrange
        started_at = datetime.now(timezone.utc)
        completed_at = started_at + timedelta(seconds=30)
        
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=started_at
        )
        
        # Añadir algunos datos
        context.add_tokens(tokens_in=100, tokens_out=50)
        context.add_cache_operation(hit=True)
        context.add_cache_operation(hit=False)
        context.add_latency("llm", 100.0)
        context.add_latency("db", 50.0)
        
        # Act
        metrics = context.to_conversation_metrics(
            completed_at=completed_at,
            user_agent="test-agent",
            ip_address="127.0.0.1"
        )
        
        # Assert
        assert metrics.tokens_in == 100
        assert metrics.tokens_out == 50
        assert metrics.cache_hits == 1
        assert metrics.cache_misses == 1
        assert metrics.cache_hit_ratio == 0.5
        assert metrics.latency_total_ms == 150.0
        assert metrics.latency_llm_ms == 100.0
        assert metrics.latency_db_ms == 50.0
        assert metrics.steps_executed == 0
        assert metrics.confirmations_required == 0
        assert metrics.errors_encountered == 0
        assert metrics.mode == "guided"
        assert metrics.started_at == started_at
        assert metrics.completed_at == completed_at
        assert metrics.user_agent == "test-agent"
        assert metrics.ip_address == "127.0.0.1"
    
    def test_telemetry_context_cost_calculation(self):
        """Test: El contexto calcula costos correctamente."""
        # Arrange
        context = TelemetryContext(
            conversation_id=str(uuid4()),
            user_id=uuid4(),
            chat_id=uuid4(),
            session_id=None,
            mode="guided",
            started_at=datetime.now(timezone.utc)
        )
        
        # Act
        context.add_tokens(tokens_in=1000, tokens_out=500)  # 1K input, 0.5K output
        
        # Assert
        # Costo esperado: (1 * 0.0015) + (0.5 * 0.006) = 0.0015 + 0.003 = 0.0045
        from decimal import Decimal
        expected_cost = Decimal("0.0045")
        actual_cost = context._calculate_cost()
        assert abs(actual_cost - expected_cost) < Decimal("0.0001")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
