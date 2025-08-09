import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import UUID, uuid4
from typing import Dict, Any

from app.services.graphs.guided_graph import GuidedGraph, GuidedState
from app.services.intent_classifier_service import IntentClassifierService, IntentType
from app.services.app_descriptor_cache_service import AppDescriptorCacheService
from app.services.telemetry_service import TelemetryService, EventType
from app.schemas.chat_schema import ChatMessage
from app.schemas.plan_schema import PlanModel, ActionModel


class TestIntentClassifierService:
    """Tests para IntentClassifierService"""
    
    def test_classify_db_read_intent(self):
        """Test clasificación de intención de lectura de DB"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        result = classifier.classify("Muéstrame todos los usuarios de la base de datos")
        
        assert result["intent"] == IntentType.DB_READ
        assert result["confidence"] > 0.4
        assert result["requires_resources"] is True
    
    def test_classify_db_write_intent(self):
        """Test clasificación de intención de escritura de DB"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        result = classifier.classify("Crea un nuevo usuario en la tabla users")
        
        assert result["intent"] == IntentType.DB_WRITE
        assert result["confidence"] > 0.4
        assert result["requires_resources"] is True
    
    def test_classify_app_call_intent(self):
        """Test clasificación de intención de llamada a app"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        result = classifier.classify("Ejecuta la función de envío de emails")
        
        assert result["intent"] == IntentType.APP_CALL
        assert result["confidence"] > 0.4
        assert result["requires_resources"] is True
    
    def test_classify_chat_intent(self):
        """Test clasificación de intención de chat"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        result = classifier.classify("Hola, ¿cómo estás?")
        
        assert result["intent"] == IntentType.CHAT
        assert result["requires_resources"] is False
    
    def test_classify_unknown_intent(self):
        """Test clasificación de intención desconocida"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        result = classifier.classify("xyz123 random text")
        
        assert result["intent"] == IntentType.UNKNOWN
        assert result["confidence"] == 0.0
    
    def test_get_clarification_message(self):
        """Test generación de mensajes de aclaración"""
        factory = Mock()
        classifier = IntentClassifierService(factory)
        
        message = classifier.get_clarification_message(IntentType.DB_READ)
        assert "base de datos" in message.lower()
        
        message = classifier.get_clarification_message(IntentType.APP_CALL)
        assert "aplicación" in message.lower() or "servicio" in message.lower()


class TestAppDescriptorCacheService:
    """Tests para AppDescriptorCacheService"""
    
    @pytest.fixture
    def mock_factory(self):
        factory = Mock()
        
        # Mock app service
        app_service = Mock()
        app = Mock()
        app.id = uuid4()
        app.name = "Test App"
        app.description = "Test app description"
        app.openapi_json = None
        app.mcp_integration_id = None
        app.proxy_id = None
        app.updated_at = None
        app_service.get_by_id.return_value = app
        factory.get_app_service.return_value = app_service
        
        # Mock function service
        function_service = Mock()
        func = Mock()
        func.name = "test_function"
        func.description = "Test function description"
        func.method = "POST"
        func.url = "/api/test"
        func.parameters = {"param1": "string"}
        func.execution_type = "api"
        func.active = True
        func.is_enabled = True
        func.updated_at = None
        function_service.get_by_app_id.return_value = [func]
        factory.get_function_service.return_value = function_service
        
        return factory
    
    def test_get_app_descriptors_compact_success(self, mock_factory):
        """Test obtención exitosa de descriptores compactos"""
        cache_service = AppDescriptorCacheService(mock_factory)
        app_ids = [uuid4()]
        
        result = cache_service.get_app_descriptors_compact(app_ids)
        
        assert len(result) == 1
        app_id_str = str(app_ids[0])
        assert app_id_str in result
        assert "Test App" in result[app_id_str]
        assert "test_function" in result[app_id_str]
    
    def test_get_app_descriptors_compact_empty_list(self, mock_factory):
        """Test con lista vacía de app IDs"""
        cache_service = AppDescriptorCacheService(mock_factory)
        
        result = cache_service.get_app_descriptors_compact([])
        
        assert result == {}
    
    def test_get_app_descriptors_compact_char_limit(self, mock_factory):
        """Test límite de caracteres"""
        cache_service = AppDescriptorCacheService(mock_factory)
        app_ids = [uuid4()]
        
        result = cache_service.get_app_descriptors_compact(app_ids, max_total_chars=10)
        
        # Debería estar vacío debido al límite muy bajo
        assert len(result) == 0
    
    def test_cache_invalidation(self, mock_factory):
        """Test invalidación de cache"""
        cache_service = AppDescriptorCacheService(mock_factory)
        app_id = uuid4()
        
        # Generar cache inicial
        cache_service.get_app_descriptors_compact([app_id])
        assert len(cache_service._cache) == 1
        
        # Invalidar cache
        cache_service.invalidate_cache(app_id)
        assert str(app_id) not in cache_service._cache


class TestTelemetryService:
    """Tests para TelemetryService"""
    
    def test_track_event(self):
        """Test registro de eventos"""
        factory = Mock()
        telemetry = TelemetryService(factory)
        user_id = uuid4()
        
        telemetry.track_event(
            event_type=EventType.CACHE_HIT,
            user_id=user_id,
            duration_ms=100.0,
            success=True,
            metadata={"resource_id": "test"}
        )
        
        assert len(telemetry._events) == 1
        event = telemetry._events[0]
        assert event.event_type == EventType.CACHE_HIT
        assert event.user_id == user_id
        assert event.duration_ms == 100.0
        assert event.success is True
        assert event.metadata["resource_id"] == "test"
    
    def test_track_cache_operation(self):
        """Test registro de operaciones de cache"""
        factory = Mock()
        telemetry = TelemetryService(factory)
        user_id = uuid4()
        
        telemetry.track_cache_operation(
            user_id=user_id,
            operation="hit",
            resource_type="db_schema",
            resource_id="test_db"
        )
        
        assert len(telemetry._events) == 1
        event = telemetry._events[0]
        assert event.event_type == EventType.CACHE_HIT
        assert event.metadata["resource_type"] == "db_schema"
        assert event.metadata["resource_id"] == "test_db"
    
    def test_get_cache_metrics(self):
        """Test obtención de métricas de cache"""
        factory = Mock()
        telemetry = TelemetryService(factory)
        user_id = uuid4()
        
        # Simular eventos de cache
        telemetry.track_event(EventType.CACHE_HIT, user_id, duration_ms=50.0)
        telemetry.track_event(EventType.CACHE_HIT, user_id, duration_ms=75.0)
        telemetry.track_event(EventType.CACHE_MISS, user_id, duration_ms=150.0)
        
        metrics = telemetry.get_cache_metrics(user_id)
        
        assert metrics["total_operations"] == 3
        assert metrics["hits"] == 2
        assert metrics["misses"] == 1
        assert metrics["hit_rate"] == 2/3
        assert abs(metrics["avg_duration_ms"] - 91.67) < 0.01  # (50+75+150)/3
    
    def test_clear_events(self):
        """Test limpieza de eventos"""
        factory = Mock()
        telemetry = TelemetryService(factory)
        user_id = uuid4()
        
        telemetry.track_event(EventType.CACHE_HIT, user_id)
        assert len(telemetry._events) == 1
        
        telemetry.clear_events(user_id)
        assert len(telemetry._events) == 0


class TestGuidedGraph:
    """Tests para GuidedGraph"""
    
    @pytest.fixture
    def mock_factory(self):
        factory = Mock()
        
        # Mock user
        user = Mock()
        user.id = uuid4()
        factory.user = user
        
        # Mock intent classifier
        intent_classifier = Mock()
        factory.get_intent_classifier_service.return_value = intent_classifier
        
        # Mock app descriptor cache
        app_cache = Mock()
        factory.get_app_descriptor_cache_service.return_value = app_cache
        
        # Mock telemetry service
        telemetry = Mock()
        factory.get_telemetry_service.return_value = telemetry
        
        # Mock orchestrator service
        orchestrator = Mock()
        orchestrator._load_database_schemas_async = AsyncMock()
        factory.get_orchestrator_service.return_value = orchestrator
        
        # Mock OpenAI service
        openai_service = Mock()
        openai_service.plan_actions = AsyncMock()
        factory.get_openai_service.return_value = openai_service
        
        return factory
    
    @pytest.mark.asyncio
    async def test_guided_graph_chat_mode(self, mock_factory):
        """Test flujo de chat normal sin recursos específicos"""
        # Setup
        graph = GuidedGraph(mock_factory)
        message = ChatMessage(role="user", content="Hola, ¿cómo estás?")
        
        # Mock intent classification
        mock_factory.get_intent_classifier_service().classify.return_value = {
            "intent": IntentType.CHAT,
            "confidence": 0.9,
            "requires_resources": False
        }
        
        # Mock OpenAI response for chat
        mock_factory.get_openai_service().plan_actions.return_value = {
            "assistant_response": "¡Hola! Estoy bien, ¿en qué puedo ayudarte?"
        }
        
        # Execute
        state: GuidedState = {
            "chat_id": "test_chat",
            "message": message
        }
        
        result = await graph.run(state)
        
        # Verify
        assert "assistant_response" in result
        assert result["assistant_response"] == "¡Hola! Estoy bien, ¿en qué puedo ayudarte?"
        assert result["intent"] == IntentType.CHAT
    
    @pytest.mark.asyncio
    async def test_guided_graph_requires_resources_no_ids(self, mock_factory):
        """Test flujo que requiere recursos pero no se proporcionaron IDs"""
        # Setup
        graph = GuidedGraph(mock_factory)
        message = ChatMessage(role="user", content="Muéstrame los usuarios")
        
        # Mock intent classification
        mock_factory.get_intent_classifier_service().classify.return_value = {
            "intent": IntentType.DB_READ,
            "confidence": 0.8,
            "requires_resources": True
        }
        
        # Mock clarification message
        mock_factory.get_intent_classifier_service().get_clarification_message.return_value = \
            "Para realizar esta consulta, necesito saber con qué base de datos deseas trabajar."
        
        # Execute
        state: GuidedState = {
            "chat_id": "test_chat",
            "message": message,
            "db_ids": [],  # Sin IDs específicos
            "app_ids": []
        }
        
        result = await graph.run(state)
        
        # Verify
        assert "assistant_response" in result
        assert "base de datos" in result["assistant_response"].lower()
        assert result["intent"] == IntentType.DB_READ
    
    @pytest.mark.asyncio
    async def test_guided_graph_with_resources_success(self, mock_factory):
        """Test flujo exitoso con recursos específicos"""
        # Setup
        graph = GuidedGraph(mock_factory)
        message = ChatMessage(role="user", content="SELECT * FROM users")
        db_id = uuid4()
        
        # Mock intent classification
        mock_factory.get_intent_classifier_service().classify.return_value = {
            "intent": IntentType.DB_READ,
            "confidence": 0.9,
            "requires_resources": True
        }
        
        # Mock schema warm-up
        mock_factory.get_orchestrator_service()._load_database_schemas_async.return_value = {
            "compact_schemas": {str(db_id): "TABLE users (id INT, name VARCHAR)"},
            "cache_status": {str(db_id): "cache_hit"}
        }
        
        # Mock app descriptor cache (empty for this test)
        mock_factory.get_app_descriptor_cache_service().get_app_descriptors_compact.return_value = {}
        
        # Mock OpenAI plan generation
        mock_factory.get_openai_service().plan_actions.return_value = {
            "actions": [
                {
                    "type": "db_query",
                    "sql": "SELECT id, name FROM users LIMIT 10",
                    "store_as": "users_result"
                }
            ],
            "assistant_response": "Ejecutando consulta..."
        }
        
        # Execute
        state: GuidedState = {
            "chat_id": "test_chat",
            "message": message,
            "db_ids": [db_id],
            "app_ids": []
        }
        
        result = await graph.run(state)
        
        # Verify
        assert "plan" in result
        assert result["plan"] is not None
        assert result["intent"] == IntentType.DB_READ
        assert result["cache_hits"] == 1
        assert result["cache_misses"] == 0
    
    @pytest.mark.asyncio
    async def test_guided_graph_with_apps(self, mock_factory):
        """Test flujo con aplicaciones específicas"""
        # Setup
        graph = GuidedGraph(mock_factory)
        message = ChatMessage(role="user", content="Envía un email")
        app_id = uuid4()
        
        # Mock intent classification
        mock_factory.get_intent_classifier_service().classify.return_value = {
            "intent": IntentType.APP_CALL,
            "confidence": 0.85,
            "requires_resources": True
        }
        
        # Mock app descriptor cache
        mock_factory.get_app_descriptor_cache_service().get_app_descriptors_compact.return_value = {
            str(app_id): "APP: Email Service\nFUNCTIONS:\n  - send_email: Sends an email message"
        }
        
        # Mock OpenAI response
        mock_factory.get_openai_service().plan_actions.return_value = {
            "assistant_response": "¿A quién quieres enviar el email y cuál es el contenido?"
        }
        
        # Execute
        state: GuidedState = {
            "chat_id": "test_chat",
            "message": message,
            "db_ids": [],
            "app_ids": [app_id]
        }
        
        result = await graph.run(state)
        
        # Verify
        assert "assistant_response" in result
        assert "email" in result["assistant_response"].lower()
        assert result["intent"] == IntentType.APP_CALL
    
    @pytest.mark.asyncio
    async def test_guided_graph_error_handling(self, mock_factory):
        """Test manejo de errores en el flujo"""
        # Setup
        graph = GuidedGraph(mock_factory)
        message = ChatMessage(role="user", content="Test error")
        
        # Mock intent classification to raise exception
        mock_factory.get_intent_classifier_service().classify.side_effect = Exception("Test error")
        
        # Execute
        state: GuidedState = {
            "chat_id": "test_chat",
            "message": message
        }
        
        result = await graph.run(state)
        
        # Verify
        assert "error" in result
        assert "assistant_response" in result
        assert "error interno" in result["assistant_response"].lower()
    
    def test_validate_resources_success(self, mock_factory):
        """Test validación exitosa de recursos"""
        graph = GuidedGraph(mock_factory)
        db_id = uuid4()
        app_id = uuid4()
        
        state: GuidedState = {
            "db_ids": [db_id],
            "app_ids": [app_id],
            "compact_schemas": {str(db_id): "TABLE users (id INT)"},
            "app_descriptors": {str(app_id): "APP: Test App"}
        }
        
        result = graph._validate_resources(state)
        assert result is True
    
    def test_validate_resources_missing_schema(self, mock_factory):
        """Test validación fallida por schema faltante"""
        graph = GuidedGraph(mock_factory)
        db_id = uuid4()
        
        state: GuidedState = {
            "db_ids": [db_id],
            "app_ids": [],
            "compact_schemas": {},  # Schema faltante
            "app_descriptors": {}
        }
        
        result = graph._validate_resources(state)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
