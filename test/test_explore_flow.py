# test/test_explore_flow.py
"""
Tests para el flujo de Exploration Mode mejorado
──────────────────────────────────────────────
Tests para verificar el flujo end-to-end del modo explore:
- Selección automática de recursos
- Warm-up de schemas
- Planificación con compact_schemas
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.services.execution.graphs.exploration_graph import ExplorationGraph
from app.services.execution.graphs.state.exploration_state import ExplorationState
from app.schemas.chat_schema import ChatMessage


class TestExploreFlow:
    """Tests para el flujo completo de exploration mode"""
    
    def setup_method(self):
        """Setup para cada test"""
        # Mock del factory completo
        self.mock_factory = Mock()
        self.mock_user = Mock()
        self.mock_user.id = uuid4()
        self.mock_factory.user = self.mock_user
        
        # Mock services
        self.setup_mock_services()
        
        # Crear graph
        self.graph = ExplorationGraph(self.mock_factory)
    
    def setup_mock_services(self):
        """Setup de todos los mock services"""
        # Description Selector Service
        self.mock_selector = Mock()
        self.mock_factory.get_description_selector_service.return_value = self.mock_selector
        
        # Database Service
        self.mock_db_service = Mock()
        self.mock_factory.get_database_service.return_value = self.mock_db_service
        
        # Cache Service
        self.mock_cache_service = Mock()
        self.mock_factory.get_detailed_schema_cache_service.return_value = self.mock_cache_service
        
        # App Service
        self.mock_app_service = Mock()
        self.mock_factory.get_app_service.return_value = self.mock_app_service
        
        # Function Service
        self.mock_function_service = Mock()
        self.mock_factory.get_function_service.return_value = self.mock_function_service
        
        # OpenAI Service
        self.mock_openai_service = AsyncMock()
        self.mock_factory.get_openai_service.return_value = self.mock_openai_service
    
    @pytest.mark.asyncio
    async def test_explore_flow_no_ids_success(self):
        """Test flujo completo: selecciona candidatos, hace warm-up y planifica"""
        # Setup: Mock selector response
        db_id = str(uuid4())
        app_id = "test-app-1"
        
        self.mock_selector.select.return_value = {
            "db_candidates": [(db_id, 0.85)],
            "app_candidates": [(app_id, 0.75)]
        }
        
        # Mock cache service - schema exists
        mock_cache_entry = Mock()
        mock_cache_entry.compact = "-- Users table\\nCREATE TABLE users (id UUID, name TEXT);"
        self.mock_cache_service.get_schema_cache.return_value = mock_cache_entry
        
        # Mock database connection
        mock_db_conn = Mock()
        mock_db_conn.id = uuid4()
        self.mock_db_service.get_record.return_value = mock_db_conn
        
        # Mock engine for dialect
        mock_engine = Mock()
        mock_engine.dialect.name = "postgresql"
        self.mock_db_service.build_sqlalchemy_engine.return_value = mock_engine
        
        # Mock app and functions
        mock_app = Mock()
        mock_app.id = app_id
        mock_app.name = "Test App"
        mock_app.proxy_id = None
        self.mock_app_service.get_by_id.return_value = mock_app
        
        mock_functions = [Mock(), Mock()]  # 2 functions
        self.mock_function_service.get_by_app.return_value = mock_functions
        
        # Mock OpenAI response with plan
        self.mock_openai_service.plan_actions.return_value = {
            "actions": [
                {"type": "db_query", "sql": "SELECT * FROM users LIMIT 10"}
            ],
            "assistant_response": "Aquí tienes los usuarios:"
        }
        
        # Prepare state
        message = ChatMessage(role="user", content="Show me user information from the database")
        state: ExplorationState = {
            "chat_id": "test-chat",
            "message": message,
            "history": []
        }
        
        # Execute
        result = await self.graph.run(state)
        
        # Verify selector was called
        self.mock_selector.select.assert_called_once_with(message.content, top_k=2, threshold=0.55)
        
        # Verify cache warm-up was attempted
        self.mock_cache_service.get_schema_cache.assert_called_once()
        
        # Verify resources were loaded
        assert "db_ids" in result
        assert "compact_schemas" in result
        assert "apps" in result
        assert "functions" in result
        
        # Verify schema was passed to OpenAI
        self.mock_openai_service.plan_actions.assert_called_once()
        call_args = self.mock_openai_service.plan_actions.call_args
        assert "db_schema" in call_args.kwargs
        assert "users" in call_args.kwargs["db_schema"].lower()
        
        # Verify plan was generated
        assert "plan" in result
    
    @pytest.mark.asyncio
    async def test_explore_no_match_threshold(self):
        """Test sin candidatos ≥ threshold → conversación general"""
        # Setup: No matches above threshold
        self.mock_selector.select.return_value = {
            "db_candidates": [],
            "app_candidates": []
        }
        
        # Mock OpenAI response without plan (general conversation)
        self.mock_openai_service.plan_actions.return_value = {
            "assistant_response": "Hola, ¿en qué puedo ayudarte?"
        }
        
        # Prepare state
        message = ChatMessage(role="user", content="Hello there")
        state: ExplorationState = {
            "chat_id": "test-chat",
            "message": message,
            "history": []
        }
        
        # Execute
        result = await self.graph.run(state)
        
        # Verify no resources were loaded
        assert result.get("db_ids") == []
        assert result.get("apps") == []
        assert result.get("compact_schemas") == {}
        
        # Verify OpenAI was called without db_schema
        self.mock_openai_service.plan_actions.assert_called_once()
        call_args = self.mock_openai_service.plan_actions.call_args
        assert not call_args.kwargs.get("db_schema")
        
        # Verify general response
        assert "assistant_response" in result
        assert "plan" not in result
    
    @pytest.mark.asyncio
    async def test_warmup_failure_continues_with_others(self):
        """Test si una DB falla warm-up, continúa con las demás"""
        # Setup: Two DB candidates
        db_id_1 = str(uuid4())
        db_id_2 = str(uuid4())
        
        self.mock_selector.select.return_value = {
            "db_candidates": [(db_id_1, 0.85), (db_id_2, 0.80)],
            "app_candidates": []
        }
        
        # Mock cache service: first fails, second succeeds
        def mock_get_cache(user_id, db_id):
            if str(db_id) == db_id_1:
                return None  # No cache, will fail
            else:
                mock_entry = Mock()
                mock_entry.compact = "-- Products table\\nCREATE TABLE products (id UUID, name TEXT);"
                return mock_entry
        
        self.mock_cache_service.get_schema_cache.side_effect = mock_get_cache
        self.mock_cache_service.create_or_update_schema_cache.return_value = None  # Fails for first
        
        # Mock database connections
        mock_db_conn = Mock()
        self.mock_db_service.get_record.return_value = mock_db_conn
        
        # Mock engine
        mock_engine = Mock()
        mock_engine.dialect.name = "postgresql"
        self.mock_db_service.build_sqlalchemy_engine.return_value = mock_engine
        
        # Mock OpenAI
        self.mock_openai_service.plan_actions.return_value = {
            "actions": [{"type": "db_query", "sql": "SELECT * FROM products LIMIT 10"}]
        }
        
        # Prepare state
        message = ChatMessage(role="user", content="Show me products")
        state: ExplorationState = {
            "chat_id": "test-chat", 
            "message": message,
            "history": []
        }
        
        # Execute
        result = await self.graph.run(state)
        
        # Verify only successful DB was included
        assert len(result.get("db_ids", [])) == 1
        assert db_id_2 in result.get("db_ids", [])
        assert db_id_1 not in result.get("db_ids", [])
        
        # Verify cache status shows the failure
        cache_status = result.get("cache_status", {})
        assert cache_status.get(db_id_1) in ["cache_miss_failed", "processing_error"]
        assert cache_status.get(db_id_2) in ["cache_hit", "cache_miss_created"]
    
    @pytest.mark.asyncio
    async def test_resources_already_provided_skip_inference(self):
        """Test si ya vienen db_ids/apps en state, respeta y salta inferencia"""
        # Prepare state with existing resources
        existing_db_ids = ["existing-db-1"]
        existing_apps = [Mock()]
        
        state: ExplorationState = {
            "chat_id": "test-chat",
            "message": ChatMessage(role="user", content="test message"),
            "history": [],
            "db_ids": existing_db_ids,
            "apps": existing_apps
        }
        
        # Mock OpenAI
        self.mock_openai_service.plan_actions.return_value = {
            "assistant_response": "Using existing resources"
        }
        
        # Execute
        result = await self.graph.run(state)
        
        # Verify selector was NOT called
        self.mock_selector.select.assert_not_called()
        
        # Verify existing resources were preserved
        assert result.get("db_ids") == existing_db_ids
        assert result.get("apps") == existing_apps
    
    @pytest.mark.asyncio
    async def test_openai_plan_actions_called_correctly(self):
        """Test OpenAI plan_actions es llamado con los parámetros correctos"""
        # Setup successful flow
        db_id = str(uuid4())
        self.mock_selector.select.return_value = {
            "db_candidates": [(db_id, 0.85)],
            "app_candidates": []
        }
        
        # Mock cache
        mock_cache_entry = Mock()
        mock_cache_entry.compact = "-- Test Schema\\nCREATE TABLE test (id INT);"
        self.mock_cache_service.get_schema_cache.return_value = mock_cache_entry
        
        # Mock DB connection
        self.mock_db_service.get_record.return_value = Mock()
        mock_engine = Mock()
        mock_engine.dialect.name = "mysql"
        self.mock_db_service.build_sqlalchemy_engine.return_value = mock_engine
        
        # Mock OpenAI
        self.mock_openai_service.plan_actions.return_value = {
            "assistant_response": "Test response"
        }
        
        # Prepare state
        message = ChatMessage(role="user", content="test query")
        state: ExplorationState = {
            "chat_id": "test-chat-123",
            "message": message,
            "history": [{"role": "user", "content": "previous message"}]
        }
        
        # Execute
        await self.graph.run(state)
        
        # Verify OpenAI was called with correct parameters
        self.mock_openai_service.plan_actions.assert_called_once()
        call_args = self.mock_openai_service.plan_actions.call_args
        
        assert call_args.kwargs["chat_id"] == "test-chat-123"
        assert call_args.kwargs["user_message"] == message
        assert "-- DATABASE" in call_args.kwargs["db_schema"]
        assert "CREATE TABLE test" in call_args.kwargs["db_schema"]
        assert call_args.kwargs["available_functions"] == []
        assert call_args.kwargs["available_mcp_tools"] is None
        assert call_args.kwargs["history"] == [{"role": "user", "content": "previous message"}]
        assert call_args.kwargs["use_enriched_context"] == False
        
        # Verify db_ids are converted to UUID
        db_ids_param = call_args.kwargs["db_ids"]
        assert len(db_ids_param) == 1
        # Should be UUID object, not string
        assert hasattr(db_ids_param[0], 'hex')  # UUID has hex attribute
