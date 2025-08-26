import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
import asyncio
import uuid

from app.routers.upload_router import router
from app.core.service_factory import ServiceFactory
from app.services.background.resource_upload_trigger import ResourceUploadTrigger

# Crear cliente de prueba
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

class TestUploadRouter:
    """Tests para el upload router con triggers automáticos"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock con todos los servicios necesarios"""
        factory = Mock(spec=ServiceFactory)
        
        # Mock del background factory
        background_factory = Mock()
        factory.background = background_factory
        
        # Mock del upload trigger service
        upload_trigger = Mock(spec=ResourceUploadTrigger)
        upload_trigger.on_database_uploaded = AsyncMock()
        upload_trigger.on_application_uploaded = AsyncMock()
        upload_trigger.on_strategies_uploaded = AsyncMock()
        background_factory.get_upload_trigger_service.return_value = upload_trigger
        
        # Mock del resource preparation service
        preparation_service = Mock()
        preparation_service.prepare_database = AsyncMock()
        preparation_service.prepare_application = AsyncMock()
        preparation_service.prepare_strategies = AsyncMock()
        background_factory.get_resource_preparation_service.return_value = preparation_service
        
        # Mock del readiness registry
        readiness_registry = Mock()
        readiness_registry.get_resource_status = AsyncMock(return_value="ready")
        factory.readiness_registry = readiness_registry
        
        return factory
    
    @pytest.fixture
    def mock_dependencies(self, mock_factory, monkeypatch):
        """Mock de las dependencias"""
        async def mock_get_current_user_id():
            return "test_user_123"
        
        async def mock_get_service_factory():
            return mock_factory
        
        monkeypatch.setattr("app.routers.upload_router.get_current_user_id", mock_get_current_user_id)
        monkeypatch.setattr("app.routers.upload_router.get_service_factory", mock_get_service_factory)
        
        return mock_factory
    
    def test_upload_database_success(self, mock_dependencies):
        """Test de upload exitoso de base de datos"""
        # Preparar archivo de prueba
        test_file = ("test_db.sql", b"CREATE TABLE test (id INT);", "text/plain")
        
        # Mock de asyncio.create_task
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            
            response = client.post(
                "/upload/database",
                files={"file": test_file}
            )
        
        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Base de datos subida y preparación iniciada automáticamente"
        assert "db_uuid" in data
        assert data["filename"] == "test_db.sql"
        assert data["status"] == "uploading_and_preparing"
        assert data["user_id"] == "test_user_123"
        assert "timestamp" in data
        
        # Verificar que se llamó al trigger
        mock_factory.background.get_upload_trigger_service.assert_called_once()
    
    def test_upload_database_invalid_file(self, mock_dependencies):
        """Test de upload con archivo inválido"""
        # Archivo con extensión incorrecta
        test_file = ("test_db.txt", b"invalid content", "text/plain")
        
        response = client.post(
            "/upload/database",
            files={"file": test_file}
        )
        
        # Verificar error
        assert response.status_code == 400
        data = response.json()
        assert "Archivo debe ser un .sql válido" in data["detail"]
    
    def test_upload_application_success(self, mock_dependencies):
        """Test de upload exitoso de aplicación"""
        # Preparar archivo de prueba
        test_file = ("test_app.json", b'{"functions": []}', "application/json")
        
        # Mock de asyncio.create_task
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            
            response = client.post(
                "/upload/application",
                files={"file": test_file}
            )
        
        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Aplicación subida y preparación iniciada automáticamente"
        assert "app_id" in data
        assert data["filename"] == "test_app.json"
        assert data["status"] == "uploading_and_preparing"
        assert data["user_id"] == "test_user_123"
        assert "timestamp" in data
        
        # Verificar que se llamó al trigger
        mock_factory.background.get_upload_trigger_service.assert_called_once()
    
    def test_upload_application_invalid_file(self, mock_dependencies):
        """Test de upload con archivo inválido"""
        # Archivo con extensión incorrecta
        test_file = ("test_app.txt", b"invalid content", "text/plain")
        
        response = client.post(
            "/upload/application",
            files={"file": test_file}
        )
        
        # Verificar error
        assert response.status_code == 400
        data = response.json()
        assert "Archivo debe ser un .json válido" in data["detail"]
    
    def test_upload_strategies_success(self, mock_dependencies):
        """Test de upload exitoso de estrategias"""
        # Preparar archivo de prueba
        test_file = ("test_strategies.json", b'[{"name": "test"}]', "application/json")
        
        # Mock de asyncio.create_task
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            
            response = client.post(
                "/upload/strategies",
                files={"file": test_file}
            )
        
        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Estrategias subidas y preparación iniciada automáticamente"
        assert "strategy_id" in data
        assert data["filename"] == "test_strategies.json"
        assert data["status"] == "uploading_and_preparing"
        assert data["user_id"] == "test_user_123"
        assert "timestamp" in data
        
        # Verificar que se llamó al trigger
        mock_factory.background.get_upload_trigger_service.assert_called_once()
    
    def test_upload_strategies_invalid_file(self, mock_dependencies):
        """Test de upload con archivo inválido"""
        # Archivo con extensión incorrecta
        test_file = ("test_strategies.txt", b"invalid content", "text/plain")
        
        response = client.post(
            "/upload/strategies",
            files={"file": test_file}
        )
        
        # Verificar error
        assert response.status_code == 400
        data = response.json()
        assert "Archivo debe ser un .json válido" in data["detail"]
    
    def test_get_upload_status_success(self, mock_dependencies):
        """Test de consulta de estado exitosa"""
        response = client.get("/upload/status/database/test_db_123")
        
        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        
        assert data["resource_type"] == "database"
        assert data["resource_id"] == "test_db_123"
        assert data["status"] == "ready"
        assert data["user_id"] == "test_user_123"
        assert "timestamp" in data
        
        # Verificar que se consultó el registry
        mock_dependencies.readiness_registry.get_resource_status.assert_called_once_with(
            "database", "test_db_123"
        )
    
    def test_force_prepare_database_success(self, mock_dependencies):
        """Test de preparación forzada exitosa de base de datos"""
        # Mock de asyncio.create_task
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            
            response = client.post("/upload/force-prepare/database/test_db_123")
        
        # Verificar respuesta
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Preparación forzada iniciada para database test_db_123"
        assert data["resource_type"] == "database"
        assert data["resource_id"] == "test_db_123"
        assert data["status"] == "force_preparation_started"
        assert data["user_id"] == "test_user_123"
        assert "timestamp" in data
        
        # Verificar que se llamó al servicio de preparación
        mock_dependencies.background.get_resource_preparation_service.assert_called_once()
    
    def test_force_prepare_invalid_resource_type(self, mock_dependencies):
        """Test de preparación forzada con tipo de recurso inválido"""
        response = client.post("/upload/force-prepare/invalid/test_123")
        
        # Verificar error
        assert response.status_code == 400
        data = response.json()
        assert "Tipo de recurso no válido: invalid" in data["detail"]
    
    def test_upload_triggers_automatic_preparation(self, mock_dependencies):
        """Test de que los uploads activan automáticamente la preparación"""
        # Preparar archivo de prueba
        test_file = ("test_db.sql", b"CREATE TABLE test (id INT);", "text/plain")
        
        # Mock de asyncio.create_task
        mock_task = Mock()
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock(return_value=mock_task))
            
            response = client.post(
                "/upload/database",
                files={"file": test_file}
            )
        
        # Verificar que se creó la tarea asíncrona
        import asyncio
        asyncio.create_task.assert_called_once()
        
        # Verificar que se llamó al trigger
        upload_trigger = mock_dependencies.background.get_upload_trigger_service.return_value
        upload_trigger.on_database_uploaded.assert_called_once()
    
    def test_upload_error_handling(self, mock_dependencies):
        """Test de manejo de errores en upload"""
        # Simular error en el factory
        mock_dependencies.background.get_upload_trigger_service.side_effect = Exception("Service error")
        
        test_file = ("test_db.sql", b"CREATE TABLE test (id INT);", "text/plain")
        
        response = client.post(
            "/upload/database",
            files={"file": test_file}
        )
        
        # Verificar error interno
        assert response.status_code == 500
        data = response.json()
        assert "Service error" in data["detail"]

class TestUploadRouterIntegration:
    """Tests de integración del upload router"""
    
    @pytest.fixture
    def real_factory(self):
        """Factory real para tests de integración"""
        from app.core.service_factory import ServiceFactory
        return ServiceFactory()
    
    def test_upload_router_endpoints_registered(self):
        """Test de que los endpoints están registrados correctamente"""
        # Verificar que el router tiene los endpoints esperados
        routes = [route.path for route in router.routes]
        
        expected_routes = [
            "/upload/database",
            "/upload/application", 
            "/upload/strategies",
            "/upload/status/{resource_type}/{resource_id}",
            "/upload/force-prepare/{resource_type}/{resource_id}"
        ]
        
        for route in expected_routes:
            assert route in routes, f"Endpoint {route} no encontrado"
    
    def test_upload_router_response_structure(self):
        """Test de estructura de respuesta de los endpoints"""
        # Verificar que las respuestas tienen la estructura correcta
        test_file = ("test.json", b'{"test": "data"}', "application/json")
        
        # Mock de dependencias para este test
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            m.setattr("app.routers.upload_router.get_current_user_id", lambda: "test_user")
            m.setattr("app.routers.upload_router.get_service_factory", lambda: Mock())
            
            response = client.post(
                "/upload/application",
                files={"file": test_file}
            )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verificar campos obligatorios
            required_fields = ["message", "app_id", "filename", "status", "user_id", "timestamp"]
            for field in required_fields:
                assert field in data, f"Campo {field} no encontrado en la respuesta"
    
    def test_upload_router_error_responses(self):
        """Test de respuestas de error del upload router"""
        # Test de archivo faltante
        response = client.post("/upload/database")
        
        # Debería fallar por falta de archivo
        assert response.status_code in [400, 422]  # FastAPI validation error
    
    def test_upload_router_async_behavior(self):
        """Test de comportamiento asíncrono del upload router"""
        # Verificar que los endpoints son asíncronos
        for route in router.routes:
            if hasattr(route, 'endpoint'):
                # Verificar que el endpoint es coroutine
                import inspect
                if inspect.iscoroutinefunction(route.endpoint):
                    assert True, f"Endpoint {route.path} es asíncrono"
                else:
                    # Algunos endpoints pueden ser síncronos (como GET)
                    if "force-prepare" in route.path or "upload" in route.path:
                        assert inspect.iscoroutinefunction(route.endpoint), f"Endpoint {route.path} debe ser asíncrono"

class TestUploadRouterPerformance:
    """Tests de rendimiento del upload router"""
    
    def test_upload_router_response_time(self):
        """Test de tiempo de respuesta del upload router"""
        import time
        
        test_file = ("test.json", b'{"test": "data"}', "application/json")
        
        # Mock de dependencias
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            m.setattr("app.routers.upload_router.get_current_user_id", lambda: "test_user")
            m.setattr("app.routers.upload_router.get_service_factory", lambda: Mock())
            
            start_time = time.time()
            response = client.post(
                "/upload/application",
                files={"file": test_file}
            )
            end_time = time.time()
        
        if response.status_code == 200:
            response_time = end_time - start_time
            
            # La respuesta debe ser rápida (< 1 segundo)
            assert response_time < 1.0, f"Respuesta muy lenta: {response_time:.3f}s"
    
    def test_upload_router_concurrent_requests(self):
        """Test de manejo de requests concurrentes"""
        import asyncio
        import time
        
        test_file = ("test.json", b'{"test": "data"}', "application/json")
        
        # Mock de dependencias
        with pytest.MonkeyPatch().context() as m:
            m.setattr("asyncio.create_task", Mock())
            m.setattr("app.routers.upload_router.get_current_user_id", lambda: "test_user")
            m.setattr("app.routers.upload_router.get_service_factory", lambda: Mock())
            
            # Simular requests concurrentes
            start_time = time.time()
            
            # Crear múltiples requests (simulado)
            responses = []
            for i in range(5):
                response = client.post(
                    "/upload/application",
                    files={"file": test_file}
                )
                responses.append(response)
            
            end_time = time.time()
        
        # Verificar que todos los requests fueron exitosos
        successful_responses = [r for r in responses if r.status_code == 200]
        assert len(successful_responses) == 5, "No todos los requests concurrentes fueron exitosos"
        
        # Verificar tiempo total
        total_time = end_time - start_time
        assert total_time < 2.0, f"Tiempo total muy alto para requests concurrentes: {total_time:.3f}s"
