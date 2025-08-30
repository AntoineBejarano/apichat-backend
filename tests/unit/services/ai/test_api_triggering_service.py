"""
🧪 TESTS UNITARIOS - APITriggeringService

Tests para el servicio de detección y ejecución automática de APIs
basado en consultas en lenguaje natural.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import List, Dict, Any
from datetime import datetime

from app.services.ai.api_triggering_service import APITriggeringService
from app.schemas.api_triggering_config_schema import APITriggeringConfigOut
from app.schemas.function_schema import FunctionOut


class TestAPITriggeringService:
    """Tests para APITriggeringService"""

    @pytest.fixture
    def mock_config(self):
        """Configuración mock para testing"""
        return APITriggeringConfigOut(
            id=uuid4(),
            user_id=uuid4(),
            app_id=uuid4(),
            enabled=True,
            confidence_threshold=0.7,
            max_auto_executions=5,
            timeout_seconds=30,
            allowed_endpoints=[],
            blocked_endpoints=[],
            auto_confirm=False,
            require_explicit_consent=True,
            created_at=datetime.now(),
            updated_at=None
        )

    @pytest.fixture
    def mock_functions(self):
        """Funciones mock para testing"""
        return [
            FunctionOut(
                id=uuid4(),
                name="get_user_info",
                description="Obtiene información de un usuario por ID",
                code="def get_user_info(user_id): return {'id': user_id}",
                timeout=30,
                is_enabled=True,
                app_id=uuid4(),
                integration_id=None,
                created_at=datetime.now(),
                updated_at=None
            ),
            FunctionOut(
                id=uuid4(),
                name="create_user",
                description="Crea un nuevo usuario",
                code="def create_user(name, email): return {'name': name, 'email': email}",
                timeout=30,
                is_enabled=True,
                app_id=uuid4(),
                integration_id=None,
                created_at=datetime.now(),
                updated_at=None
            )
        ]

    @pytest.fixture
    def api_triggering_service(self, mock_config):
        """Instancia del servicio para testing"""
        with patch('app.services.ai.api_triggering_service.ServiceFactory') as mock_factory:
            # Mock de dependencias
            mock_config_service = Mock()
            mock_config_service.get_by_user_and_app.return_value = mock_config
            
            mock_vector_search = Mock()
            mock_function_executor = Mock()
            mock_llm_service = Mock()
            
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            mock_factory.get_unified_vector_search_service.return_value = mock_vector_search
            mock_factory.get_function_executor_service.return_value = mock_function_executor
            mock_factory.get_llm_service.return_value = mock_llm_service
            
            return APITriggeringService(mock_factory)

    @pytest.mark.asyncio
    async def test_detect_api_intent_success(self, api_triggering_service, mock_functions):
        """Test: Detección exitosa de intención de API"""
        # Arrange
        query = "Obtén la información del usuario con ID 123"
        user_id = uuid4()
        app_id = uuid4()
        
        api_triggering_service.unified_search_service.search_api_functions = AsyncMock(
            return_value=mock_functions[:1]  # Solo get_user_info
        )
        
        # Mock del LLM service a través del factory
        mock_llm_service = Mock()
        mock_llm_service.detect_api_intent = AsyncMock(
            return_value={
                "intent": "api_call",
                "confidence": 0.85,
                "function_name": "get_user_info",
                "extracted_params": {"user_id": "123"}
            }
        )
        
        # Act
        result = await api_triggering_service.detect_api_intent(query, user_id, app_id)
        
        # Assert
        assert result is not None
        assert result["intent"] == "api_call"
        assert result["confidence"] == 0.85
        assert result["function_name"] == "get_user_info"
        assert result["extracted_params"]["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_detect_api_intent_no_intent(self, api_triggering_service):
        """Test: No se detecta intención de API"""
        # Arrange
        query = "¿Cómo está el clima hoy?"
        user_id = uuid4()
        app_id = uuid4()
        
        api_triggering_service._unified_vector_search.search_api_functions = AsyncMock(
            return_value=[]
        )
        
        api_triggering_service._llm_service.detect_api_intent = AsyncMock(
            return_value={
                "intent": "general_query",
                "confidence": 0.3
            }
        )
        
        # Act
        result = await api_triggering_service.detect_api_intent(query, user_id, app_id)
        
        # Assert
        assert result is not None
        assert result["intent"] == "general_query"
        assert result["confidence"] < 0.5

    @pytest.mark.asyncio
    async def test_extract_parameters_success(self, api_triggering_service, mock_functions):
        """Test: Extracción exitosa de parámetros"""
        # Arrange
        query = "Crea un usuario llamado Juan con email juan@test.com"
        function = mock_functions[1]  # create_user
        
        api_triggering_service._llm_service.extract_function_parameters = AsyncMock(
            return_value={
                "name": "Juan",
                "email": "juan@test.com"
            }
        )
        
        # Act
        result = await api_triggering_service.extract_parameters(query, function)
        
        # Assert
        assert result is not None
        assert result["name"] == "Juan"
        assert result["email"] == "juan@test.com"

    @pytest.mark.asyncio
    async def test_extract_parameters_missing_required(self, api_triggering_service, mock_functions):
        """Test: Extracción con parámetros requeridos faltantes"""
        # Arrange
        query = "Crea un usuario llamado Juan"  # Falta email
        function = mock_functions[1]  # create_user
        
        api_triggering_service._llm_service.extract_function_parameters = AsyncMock(
            return_value={
                "name": "Juan"
                # email faltante
            }
        )
        
        # Act
        result = await api_triggering_service.extract_parameters(query, function)
        
        # Assert
        assert result is not None
        assert result["name"] == "Juan"
        # El servicio debería manejar parámetros faltantes

    @pytest.mark.asyncio
    async def test_execute_api_function_success(self, api_triggering_service, mock_functions):
        """Test: Ejecución exitosa de función API"""
        # Arrange
        function = mock_functions[0]  # get_user_info
        parameters = {"user_id": "123"}
        
        api_triggering_service._function_executor.execute_http_function = AsyncMock(
            return_value={
                "success": True,
                "data": {"id": "123", "name": "Test User"},
                "status_code": 200
            }
        )
        
        # Act
        result = await api_triggering_service.execute_api_function(function, parameters)
        
        # Assert
        assert result is not None
        assert result["success"] is True
        assert result["data"]["id"] == "123"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_execute_api_function_error(self, api_triggering_service, mock_functions):
        """Test: Error en ejecución de función API"""
        # Arrange
        function = mock_functions[0]  # get_user_info
        parameters = {"user_id": "invalid"}
        
        api_triggering_service._function_executor.execute_http_function = AsyncMock(
            return_value={
                "success": False,
                "error": "User not found",
                "status_code": 404
            }
        )
        
        # Act
        result = await api_triggering_service.execute_api_function(function, parameters)
        
        # Assert
        assert result is not None
        assert result["success"] is False
        assert result["error"] == "User not found"
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_should_auto_execute_high_confidence(self, api_triggering_service, mock_config):
        """Test: Auto-ejecución con alta confianza"""
        # Arrange
        confidence = 0.9
        function_name = "get_user_info"
        
        # Act
        result = await api_triggering_service.should_auto_execute(
            confidence, function_name, mock_config
        )
        
        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_should_auto_execute_low_confidence(self, api_triggering_service, mock_config):
        """Test: No auto-ejecución con baja confianza"""
        # Arrange
        confidence = 0.5  # Menor al threshold de 0.7
        function_name = "get_user_info"
        
        # Act
        result = await api_triggering_service.should_auto_execute(
            confidence, function_name, mock_config
        )
        
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_should_auto_execute_blocked_endpoint(self, api_triggering_service, mock_config):
        """Test: No auto-ejecución para endpoint bloqueado"""
        # Arrange
        mock_config.blocked_endpoints = ["get_user_info"]
        confidence = 0.9
        function_name = "get_user_info"
        
        # Act
        result = await api_triggering_service.should_auto_execute(
            confidence, function_name, mock_config
        )
        
        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_process_query_complete_flow(self, api_triggering_service, mock_config, mock_functions):
        """Test: Flujo completo de procesamiento de query"""
        # Arrange
        query = "Obtén información del usuario 123"
        user_id = uuid4()
        app_id = uuid4()
        
        # Mock de todas las dependencias
        api_triggering_service._config_service.get_by_user_and_app = AsyncMock(
            return_value=mock_config
        )
        api_triggering_service._unified_vector_search.search_api_functions = AsyncMock(
            return_value=mock_functions[:1]
        )
        api_triggering_service._llm_service.detect_api_intent = AsyncMock(
            return_value={
                "intent": "api_call",
                "confidence": 0.85,
                "function_name": "get_user_info",
                "extracted_params": {"user_id": "123"}
            }
        )
        api_triggering_service._function_executor.execute_http_function = AsyncMock(
            return_value={
                "success": True,
                "data": {"id": "123", "name": "Test User"},
                "status_code": 200
            }
        )
        
        # Act
        result = await api_triggering_service.process_query(query, user_id, app_id)
        
        # Assert
        assert result is not None
        assert result["intent_detected"] is True
        assert result["function_name"] == "get_user_info"
        assert result["execution_result"]["success"] is True
        assert result["execution_result"]["data"]["id"] == "123"

    @pytest.mark.asyncio
    async def test_process_query_no_config(self, api_triggering_service):
        """Test: Procesamiento sin configuración"""
        # Arrange
        query = "Obtén información del usuario 123"
        user_id = uuid4()
        app_id = uuid4()
        
        api_triggering_service._config_service.get_by_user_and_app = AsyncMock(
            return_value=None  # Sin configuración
        )
        
        # Act
        result = await api_triggering_service.process_query(query, user_id, app_id)
        
        # Assert
        assert result is not None
        assert result["intent_detected"] is False
        assert "error" in result
        assert "No configuration found" in result["error"]
