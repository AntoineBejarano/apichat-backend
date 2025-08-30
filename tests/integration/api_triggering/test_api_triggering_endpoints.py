"""
🧪 TESTS DE INTEGRACIÓN - API Triggering Endpoints

Tests de integración para los endpoints de API triggering.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import Dict, Any
from datetime import datetime

from app.main import app
from app.schemas.api_triggering_config_schema import APITriggeringConfigOut
from app.schemas.function_schema import FunctionOut


class TestAPITriggeringEndpoints:
    """Tests de integración para endpoints de API triggering"""

    @pytest.fixture
    def client(self):
        """Cliente de prueba para FastAPI"""
        return TestClient(app)

    @pytest.fixture
    def mock_user_id(self):
        """ID de usuario mock"""
        return str(uuid4())

    @pytest.fixture
    def mock_app_id(self):
        """ID de app mock"""
        return str(uuid4())

    @pytest.fixture
    def sample_config_data(self, mock_user_id, mock_app_id):
        """Datos de ejemplo para configuración"""
        return {
            "user_id": mock_user_id,
            "app_id": mock_app_id,
            "enabled": True,
            "confidence_threshold": 0.7,
            "max_auto_executions": 5,
            "timeout_seconds": 30,
            "allowed_endpoints": ["get_user_info", "create_user"],
            "blocked_endpoints": ["delete_user"],
            "auto_confirm": False,
            "require_explicit_consent": True
        }

    @pytest.fixture
    def mock_config_response(self, mock_user_id, mock_app_id):
        """Respuesta mock de configuración"""
        return APITriggeringConfigOut(
            id=str(uuid4()),
            user_id=mock_user_id,
            app_id=mock_app_id,
            enabled=True,
            confidence_threshold=0.7,
            max_auto_executions=5,
            timeout_seconds=30,
            allowed_endpoints=["get_user_info", "create_user"],
            blocked_endpoints=["delete_user"],
            auto_confirm=False,
            require_explicit_consent=True,
            created_at=datetime.now(),
            updated_at=None
        )

    @pytest.mark.asyncio
    async def test_create_api_triggering_config_success(self, client, sample_config_data, mock_config_response):
        """Test: Creación exitosa de configuración de API triggering"""
        # Arrange
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.create_config = AsyncMock(return_value=mock_config_response)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.post(
                "/api/v1/api-triggering/configs",
                json=sample_config_data
            )
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["user_id"] == sample_config_data["user_id"]
            assert data["app_id"] == sample_config_data["app_id"]
            assert data["enabled"] == sample_config_data["enabled"]
            assert data["confidence_threshold"] == sample_config_data["confidence_threshold"]

    @pytest.mark.asyncio
    async def test_create_api_triggering_config_validation_error(self, client, sample_config_data):
        """Test: Error de validación al crear configuración"""
        # Arrange
        sample_config_data["confidence_threshold"] = 1.5  # Inválido
        
        # Act
        response = client.post(
            "/api/v1/api-triggering/configs",
            json=sample_config_data
        )
        
        # Assert
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_get_api_triggering_config_success(self, client, mock_user_id, mock_app_id, mock_config_response):
        """Test: Obtención exitosa de configuración"""
        # Arrange
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.get_by_user_and_app = AsyncMock(return_value=mock_config_response)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.get(
                f"/api/v1/api-triggering/configs/user/{mock_user_id}/app/{mock_app_id}"
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == mock_user_id
            assert data["app_id"] == mock_app_id

    @pytest.mark.asyncio
    async def test_get_api_triggering_config_not_found(self, client, mock_user_id, mock_app_id):
        """Test: Configuración no encontrada"""
        # Arrange
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.get_by_user_and_app = AsyncMock(return_value=None)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.get(
                f"/api/v1/api-triggering/configs/user/{mock_user_id}/app/{mock_app_id}"
            )
            
            # Assert
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_api_triggering_config_success(self, client, mock_config_response):
        """Test: Actualización exitosa de configuración"""
        # Arrange
        config_id = str(uuid4())
        update_data = {
            "enabled": False,
            "confidence_threshold": 0.8
        }
        
        # Mock de la configuración actualizada
        updated_config = mock_config_response.copy()
        updated_config.enabled = False
        updated_config.confidence_threshold = 0.8
        
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.update_config = AsyncMock(return_value=updated_config)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.put(
                f"/api/v1/api-triggering/configs/{config_id}",
                json=update_data
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] == False
            assert data["confidence_threshold"] == 0.8

    @pytest.mark.asyncio
    async def test_delete_api_triggering_config_success(self, client):
        """Test: Eliminación exitosa de configuración"""
        # Arrange
        config_id = str(uuid4())
        
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.delete_config = AsyncMock(return_value=True)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.delete(f"/api/v1/api-triggering/configs/{config_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True

    @pytest.mark.asyncio
    async def test_trigger_api_function_success(self, client, mock_user_id, mock_app_id):
        """Test: Triggering exitoso de función API"""
        # Arrange
        query = "Obtén información del usuario con ID 123"
        
        mock_result = {
            "intent_detected": True,
            "function_name": "get_user_info",
            "confidence": 0.85,
            "extracted_params": {"user_id": "123"},
            "execution_result": {
                "success": True,
                "data": {"id": "123", "name": "Test User"},
                "status_code": 200
            }
        }
        
        with patch('app.routers.api_triggering_router.ServiceFactory') as mock_factory:
            mock_triggering_service = Mock()
            mock_triggering_service.process_query = AsyncMock(return_value=mock_result)
            mock_factory.get_api_triggering_service.return_value = mock_triggering_service
            
            # Act
            response = client.post(
                "/api/v1/api-triggering/trigger",
                json={
                    "query": query,
                    "user_id": mock_user_id,
                    "app_id": mock_app_id
                }
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["intent_detected"] == True
            assert data["function_name"] == "get_user_info"
            assert data["execution_result"]["success"] == True

    @pytest.mark.asyncio
    async def test_trigger_api_function_no_intent(self, client, mock_user_id, mock_app_id):
        """Test: No se detecta intención de API"""
        # Arrange
        query = "¿Cómo está el clima hoy?"
        
        mock_result = {
            "intent_detected": False,
            "reason": "No API intent detected",
            "confidence": 0.3
        }
        
        with patch('app.routers.api_triggering_router.ServiceFactory') as mock_factory:
            mock_triggering_service = Mock()
            mock_triggering_service.process_query = AsyncMock(return_value=mock_result)
            mock_factory.get_api_triggering_service.return_value = mock_triggering_service
            
            # Act
            response = client.post(
                "/api/v1/api-triggering/trigger",
                json={
                    "query": query,
                    "user_id": mock_user_id,
                    "app_id": mock_app_id
                }
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["intent_detected"] == False
            assert "reason" in data

    @pytest.mark.asyncio
    async def test_trigger_api_function_error(self, client, mock_user_id, mock_app_id):
        """Test: Error en triggering de función API"""
        # Arrange
        query = "Obtén información del usuario"
        
        with patch('app.routers.api_triggering_router.ServiceFactory') as mock_factory:
            mock_triggering_service = Mock()
            mock_triggering_service.process_query = AsyncMock(
                side_effect=Exception("Service error")
            )
            mock_factory.get_api_triggering_service.return_value = mock_triggering_service
            
            # Act
            response = client.post(
                "/api/v1/api-triggering/trigger",
                json={
                    "query": query,
                    "user_id": mock_user_id,
                    "app_id": mock_app_id
                }
            )
            
            # Assert
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_unified_chat_success(self, client, mock_user_id, mock_app_id):
        """Test: Chat unificado exitoso"""
        # Arrange
        query = "Obtén información del usuario 123 y también muéstrame las tablas de la base de datos"
        
        mock_result = {
            "response": "He obtenido la información del usuario y aquí están las tablas disponibles...",
            "api_calls_made": [
                {
                    "function": "get_user_info",
                    "success": True,
                    "data": {"id": "123", "name": "Test User"}
                }
            ],
            "db_queries_made": [
                {
                    "query": "SHOW TABLES",
                    "success": True,
                    "result": ["users", "orders", "products"]
                }
            ]
        }
        
        with patch('app.routers.unified_chat_router.ServiceFactory') as mock_factory:
            mock_chat_service = Mock()
            mock_chat_service.process_unified_query = AsyncMock(return_value=mock_result)
            mock_factory.get_unified_chat_service.return_value = mock_chat_service
            
            # Act
            response = client.post(
                "/api/v1/unified-chat/query",
                json={
                    "query": query,
                    "user_id": mock_user_id,
                    "app_id": mock_app_id,
                    "connection_id": str(uuid4())
                }
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "api_calls_made" in data
            assert "db_queries_made" in data

    @pytest.mark.asyncio
    async def test_get_user_configs_success(self, client, mock_user_id, mock_config_response):
        """Test: Obtención exitosa de configuraciones de usuario"""
        # Arrange
        mock_configs = [mock_config_response]
        
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.get_configs_by_user = AsyncMock(return_value=mock_configs)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.get(f"/api/v1/api-triggering/configs/user/{mock_user_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["user_id"] == mock_user_id

    @pytest.mark.asyncio
    async def test_get_app_configs_success(self, client, mock_app_id, mock_config_response):
        """Test: Obtención exitosa de configuraciones de app"""
        # Arrange
        mock_configs = [mock_config_response]
        
        with patch('app.routers.api_triggering_config_router.ServiceFactory') as mock_factory:
            mock_config_service = Mock()
            mock_config_service.get_configs_by_app = AsyncMock(return_value=mock_configs)
            mock_factory.get_api_triggering_config_service.return_value = mock_config_service
            
            # Act
            response = client.get(f"/api/v1/api-triggering/configs/app/{mock_app_id}")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["app_id"] == mock_app_id

    @pytest.mark.asyncio
    async def test_validate_query_success(self, client):
        """Test: Validación exitosa de query"""
        # Arrange
        query = "Obtén información del usuario 123"
        
        with patch('app.routers.api_triggering_router.ServiceFactory') as mock_factory:
            mock_triggering_service = Mock()
            mock_triggering_service.validate_query = AsyncMock(return_value={
                "valid": True,
                "suggestions": ["Considera especificar más detalles"]
            })
            mock_factory.get_api_triggering_service.return_value = mock_triggering_service
            
            # Act
            response = client.post(
                "/api/v1/api-triggering/validate",
                json={"query": query}
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] == True
            assert "suggestions" in data

    @pytest.mark.asyncio
    async def test_get_available_functions_success(self, client, mock_user_id, mock_app_id):
        """Test: Obtención exitosa de funciones disponibles"""
        # Arrange
        mock_functions = [
            FunctionOut(
                id=str(uuid4()),
                name="get_user_info",
                description="Obtiene información de un usuario",
                code="def get_user_info(id): return {'id': id}",
                timeout=30,
                is_enabled=True,
                app_id=mock_app_id,
                integration_id=None,
                created_at=datetime.now(),
                updated_at=None
            )
        ]
        
        with patch('app.routers.api_triggering_router.ServiceFactory') as mock_factory:
            mock_triggering_service = Mock()
            mock_triggering_service.get_available_functions = AsyncMock(return_value=mock_functions)
            mock_factory.get_api_triggering_service.return_value = mock_triggering_service
            
            # Act
            response = client.get(
                f"/api/v1/api-triggering/functions/user/{mock_user_id}/app/{mock_app_id}"
            )
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "get_user_info"
