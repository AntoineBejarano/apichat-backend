"""
🧪 TESTS UNITARIOS - UnifiedChatService

Tests para el servicio de chat unificado que combina
consultas de base de datos y triggering de APIs.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import List, Dict, Any

from app.services.ai.unified_chat_service import UnifiedChatService
from app.schemas.function_schema import FunctionResponse


class TestUnifiedChatService:
    """Tests para UnifiedChatService"""

    @pytest.fixture
    def mock_api_triggering_service(self):
        """Mock del servicio de API triggering"""
        service = Mock()
        service.process_query = AsyncMock(return_value={
            "intent_detected": True,
            "function_name": "get_user_info",
            "confidence": 0.85,
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"}
            }
        })
        return service

    @pytest.fixture
    def mock_chat_service(self):
        """Mock del servicio de chat existente"""
        service = Mock()
        service.process_query = AsyncMock(return_value={
            "response": "Database query executed successfully",
            "sql_query": "SELECT * FROM users WHERE id = 123",
            "result": [{"id": "123", "name": "Test User"}]
        })
        return service

    @pytest.fixture
    def mock_llm_service(self):
        """Mock del servicio de LLM"""
        service = Mock()
        service.analyze_query_intent = AsyncMock(return_value={
            "intent": "mixed",
            "confidence": 0.9,
            "components": {
                "database": True,
                "api": True
            }
        })
        service.generate_unified_response = AsyncMock(return_value="Combined response with both DB and API results")
        return service

    @pytest.fixture
    def unified_chat_service(self, mock_api_triggering_service, mock_chat_service, mock_llm_service):
        """Instancia del servicio para testing"""
        with patch('app.services.ai.unified_chat_service.ServiceFactory') as mock_factory:
            mock_factory.get_api_triggering_service.return_value = mock_api_triggering_service
            mock_factory.get_chat_service.return_value = mock_chat_service
            mock_factory.get_llm_service.return_value = mock_llm_service
            
            return UnifiedChatService()

    @pytest.mark.asyncio
    async def test_process_unified_query_database_only(self, unified_chat_service, mock_llm_service, mock_chat_service):
        """Test: Procesamiento de query solo de base de datos"""
        # Arrange
        query = "Muéstrame todos los usuarios de la base de datos"
        user_id = uuid4()
        connection_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "database",
            "confidence": 0.9,
            "components": {
                "database": True,
                "api": False
            }
        })
        
        mock_chat_service.process_query = AsyncMock(return_value={
            "response": "Here are all users from the database",
            "sql_query": "SELECT * FROM users",
            "result": [{"id": "1", "name": "User 1"}, {"id": "2", "name": "User 2"}]
        })
        
        # Act
        result = await unified_chat_service.process_unified_query(
            query, user_id, connection_id=connection_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "db_queries_made" in result
        assert "api_calls_made" in result
        assert len(result["db_queries_made"]) > 0
        assert len(result["api_calls_made"]) == 0
        assert "Here are all users" in result["response"]

    @pytest.mark.asyncio
    async def test_process_unified_query_api_only(self, unified_chat_service, mock_llm_service, mock_api_triggering_service):
        """Test: Procesamiento de query solo de API"""
        # Arrange
        query = "Obtén información del usuario con ID 123"
        user_id = uuid4()
        app_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "api",
            "confidence": 0.9,
            "components": {
                "database": False,
                "api": True
            }
        })
        
        mock_api_triggering_service.process_query = AsyncMock(return_value={
            "intent_detected": True,
            "function_name": "get_user_info",
            "confidence": 0.85,
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"}
            }
        })
        
        # Act
        result = await unified_chat_service.process_unified_query(
            query, user_id, app_id=app_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "db_queries_made" in result
        assert "api_calls_made" in result
        assert len(result["db_queries_made"]) == 0
        assert len(result["api_calls_made"]) > 0
        assert result["api_calls_made"][0]["function"] == "get_user_info"

    @pytest.mark.asyncio
    async def test_process_unified_query_mixed(self, unified_chat_service, mock_llm_service, mock_chat_service, mock_api_triggering_service):
        """Test: Procesamiento de query mixta (DB + API)"""
        # Arrange
        query = "Obtén información del usuario 123 y también muéstrame las órdenes de la base de datos"
        user_id = uuid4()
        app_id = uuid4()
        connection_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "mixed",
            "confidence": 0.9,
            "components": {
                "database": True,
                "api": True
            }
        })
        
        mock_chat_service.process_query = AsyncMock(return_value={
            "response": "Database query executed",
            "sql_query": "SELECT * FROM orders WHERE user_id = 123",
            "result": [{"id": "1", "user_id": "123", "total": 100}]
        })
        
        mock_api_triggering_service.process_query = AsyncMock(return_value={
            "intent_detected": True,
            "function_name": "get_user_info",
            "confidence": 0.85,
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"}
            }
        })
        
        mock_llm_service.generate_unified_response = AsyncMock(return_value="User info: Test User. Orders: 1 order with total $100")
        
        # Act
        result = await unified_chat_service.process_unified_query(
            query, user_id, app_id=app_id, connection_id=connection_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "db_queries_made" in result
        assert "api_calls_made" in result
        assert len(result["db_queries_made"]) > 0
        assert len(result["api_calls_made"]) > 0
        assert "User info: Test User" in result["response"]
        assert "Orders: 1 order" in result["response"]

    @pytest.mark.asyncio
    async def test_process_unified_query_general(self, unified_chat_service, mock_llm_service):
        """Test: Procesamiento de query general (sin DB ni API)"""
        # Arrange
        query = "¿Cómo está el clima hoy?"
        user_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "general",
            "confidence": 0.9,
            "components": {
                "database": False,
                "api": False
            }
        })
        
        mock_llm_service.generate_general_response = AsyncMock(return_value="I can't help with weather information. Please ask about database queries or API functions.")
        
        # Act
        result = await unified_chat_service.process_unified_query(query, user_id)
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "db_queries_made" in result
        assert "api_calls_made" in result
        assert len(result["db_queries_made"]) == 0
        assert len(result["api_calls_made"]) == 0
        assert "weather information" in result["response"]

    @pytest.mark.asyncio
    async def test_process_unified_query_api_error(self, unified_chat_service, mock_llm_service, mock_api_triggering_service):
        """Test: Error en procesamiento de API"""
        # Arrange
        query = "Obtén información del usuario 123"
        user_id = uuid4()
        app_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "api",
            "confidence": 0.9,
            "components": {
                "database": False,
                "api": True
            }
        })
        
        mock_api_triggering_service.process_query = AsyncMock(
            side_effect=Exception("API service error")
        )
        
        # Act
        result = await unified_chat_service.process_unified_query(
            query, user_id, app_id=app_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "error" in result["response"] or "API service error" in result["response"]

    @pytest.mark.asyncio
    async def test_process_unified_query_database_error(self, unified_chat_service, mock_llm_service, mock_chat_service):
        """Test: Error en procesamiento de base de datos"""
        # Arrange
        query = "Muéstrame todos los usuarios"
        user_id = uuid4()
        connection_id = uuid4()
        
        mock_llm_service.analyze_query_intent = AsyncMock(return_value={
            "intent": "database",
            "confidence": 0.9,
            "components": {
                "database": True,
                "api": False
            }
        })
        
        mock_chat_service.process_query = AsyncMock(
            side_effect=Exception("Database service error")
        )
        
        # Act
        result = await unified_chat_service.process_unified_query(
            query, user_id, connection_id=connection_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "error" in result["response"] or "Database service error" in result["response"]

    @pytest.mark.asyncio
    async def test_combine_results_success(self, unified_chat_service, mock_llm_service):
        """Test: Combinación exitosa de resultados"""
        # Arrange
        db_results = {
            "response": "Database query executed",
            "sql_query": "SELECT * FROM orders",
            "result": [{"id": "1", "total": 100}]
        }
        
        api_results = {
            "intent_detected": True,
            "function_name": "get_user_info",
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"}
            }
        }
        
        mock_llm_service.generate_unified_response = AsyncMock(
            return_value="User: Test User. Orders: 1 order with total $100"
        )
        
        # Act
        result = await unified_chat_service._combine_results(db_results, api_results)
        
        # Assert
        assert result is not None
        assert "User: Test User" in result
        assert "Orders: 1 order" in result

    @pytest.mark.asyncio
    async def test_format_database_results(self, unified_chat_service):
        """Test: Formateo de resultados de base de datos"""
        # Arrange
        db_results = {
            "response": "Query executed successfully",
            "sql_query": "SELECT * FROM users",
            "result": [{"id": "1", "name": "User 1"}]
        }
        
        # Act
        formatted = unified_chat_service._format_database_results(db_results)
        
        # Assert
        assert formatted is not None
        assert "sql_query" in formatted
        assert "result" in formatted
        assert formatted["sql_query"] == "SELECT * FROM users"

    @pytest.mark.asyncio
    async def test_format_api_results(self, unified_chat_service):
        """Test: Formateo de resultados de API"""
        # Arrange
        api_results = {
            "intent_detected": True,
            "function_name": "get_user_info",
            "confidence": 0.85,
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"}
            }
        }
        
        # Act
        formatted = unified_chat_service._format_api_results(api_results)
        
        # Assert
        assert formatted is not None
        assert "function" in formatted
        assert "success" in formatted
        assert formatted["function"] == "get_user_info"
        assert formatted["success"] == True

    @pytest.mark.asyncio
    async def test_validate_parameters_success(self, unified_chat_service):
        """Test: Validación exitosa de parámetros"""
        # Arrange
        user_id = uuid4()
        app_id = uuid4()
        connection_id = uuid4()
        
        # Act
        result = unified_chat_service._validate_parameters(
            user_id, app_id=app_id, connection_id=connection_id
        )
        
        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_parameters_missing_user_id(self, unified_chat_service):
        """Test: Error por user_id faltante"""
        # Arrange
        app_id = uuid4()
        connection_id = uuid4()
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            unified_chat_service._validate_parameters(
                None, app_id=app_id, connection_id=connection_id
            )
        
        assert "user_id is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_parameters_missing_context(self, unified_chat_service):
        """Test: Error por falta de contexto (app_id o connection_id)"""
        # Arrange
        user_id = uuid4()
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            unified_chat_service._validate_parameters(user_id)
        
        assert "Either app_id or connection_id must be provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_query_context_success(self, unified_chat_service):
        """Test: Obtención exitosa de contexto de query"""
        # Arrange
        query = "Obtén información del usuario 123 y muéstrame las órdenes"
        user_id = uuid4()
        app_id = uuid4()
        connection_id = uuid4()
        
        # Act
        context = unified_chat_service._get_query_context(
            query, user_id, app_id=app_id, connection_id=connection_id
        )
        
        # Assert
        assert context is not None
        assert context["user_id"] == user_id
        assert context["app_id"] == app_id
        assert context["connection_id"] == connection_id
        assert context["query"] == query

    @pytest.mark.asyncio
    async def test_handle_mixed_query_success(self, unified_chat_service, mock_chat_service, mock_api_triggering_service, mock_llm_service):
        """Test: Manejo exitoso de query mixta"""
        # Arrange
        query = "Query mixta"
        user_id = uuid4()
        app_id = uuid4()
        connection_id = uuid4()
        
        mock_chat_service.process_query = AsyncMock(return_value={
            "response": "DB result",
            "sql_query": "SELECT * FROM users",
            "result": [{"id": "1"}]
        })
        
        mock_api_triggering_service.process_query = AsyncMock(return_value={
            "intent_detected": True,
            "function_name": "get_user_info",
            "execution_result": {"success": True, "data": {"id": "123"}}
        })
        
        mock_llm_service.generate_unified_response = AsyncMock(
            return_value="Combined response"
        )
        
        # Act
        result = await unified_chat_service._handle_mixed_query(
            query, user_id, app_id, connection_id
        )
        
        # Assert
        assert result is not None
        assert "response" in result
        assert "db_queries_made" in result
        assert "api_calls_made" in result
        assert result["response"] == "Combined response"
