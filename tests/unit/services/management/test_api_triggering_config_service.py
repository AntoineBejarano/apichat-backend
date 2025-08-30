"""
🧪 TESTS UNITARIOS - APITriggeringConfigService

Tests para el servicio de gestión de configuraciones de API triggering.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import List, Optional

from app.services.management.api_triggering_config_service import APITriggeringConfigService
from app.schemas.api_triggering_config_schema import (
    APITriggeringConfigCreate,
    APITriggeringConfigUpdate,
    APITriggeringConfigOut
)
from app.models.api_triggering_config_model import APITriggeringConfig


class TestAPITriggeringConfigService:
    """Tests para APITriggeringConfigService"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock de la sesión de base de datos"""
        session = Mock()
        session.add = Mock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.delete = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def config_service(self, mock_db_session):
        """Instancia del servicio para testing"""
        with patch('app.services.management.api_triggering_config_service.get_db_session') as mock_get_session:
            mock_get_session.return_value = mock_db_session
            return APITriggeringConfigService()

    @pytest.fixture
    def sample_config_data(self):
        """Datos de ejemplo para configuración"""
        return {
            "user_id": uuid4(),
            "app_id": uuid4(),
            "enabled": True,
            "confidence_threshold": 0.7,
            "max_auto_executions": 5,
            "timeout_seconds": 30,
            "allowed_endpoints": ["get_user_info", "create_user"],
            "blocked_endpoints": ["delete_user"],
            "auto_confirm": False,
            "require_explicit_consent": True
        }

    @pytest.mark.asyncio
    async def test_create_config_success(self, config_service, mock_db_session, sample_config_data):
        """Test: Creación exitosa de configuración"""
        # Arrange
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Mock del objeto de configuración creado
        mock_config = Mock(spec=APITriggeringConfig)
        mock_config.id = uuid4()
        mock_config.user_id = sample_config_data["user_id"]
        mock_config.app_id = sample_config_data["app_id"]
        mock_config.enabled = sample_config_data["enabled"]
        mock_config.confidence_threshold = sample_config_data["confidence_threshold"]
        mock_config.max_auto_executions = sample_config_data["max_auto_executions"]
        mock_config.timeout_seconds = sample_config_data["timeout_seconds"]
        mock_config.allowed_endpoints = sample_config_data["allowed_endpoints"]
        mock_config.blocked_endpoints = sample_config_data["blocked_endpoints"]
        mock_config.auto_confirm = sample_config_data["auto_confirm"]
        mock_config.require_explicit_consent = sample_config_data["require_explicit_consent"]
        
        # Mock de la query
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None  # No existe configuración previa
        mock_db_session.query.return_value = mock_query
        
        # Mock del constructor del modelo
        with patch('app.services.management.api_triggering_config_service.APITriggeringConfig') as mock_model:
            mock_model.return_value = mock_config
            
            # Act
            result = await config_service.create_config(config_create)
            
            # Assert
            assert result is not None
            assert result.user_id == sample_config_data["user_id"]
            assert result.app_id == sample_config_data["app_id"]
            assert result.enabled == sample_config_data["enabled"]
            assert result.confidence_threshold == sample_config_data["confidence_threshold"]
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_config_already_exists(self, config_service, mock_db_session, sample_config_data):
        """Test: Error al crear configuración que ya existe"""
        # Arrange
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Mock de configuración existente
        existing_config = Mock(spec=APITriggeringConfig)
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = existing_config
        mock_db_session.query.return_value = mock_query
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await config_service.create_config(config_create)
        
        assert "Configuration already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_config_by_id_success(self, config_service, mock_db_session):
        """Test: Obtención exitosa de configuración por ID"""
        # Arrange
        config_id = uuid4()
        mock_config = Mock(spec=APITriggeringConfig)
        mock_config.id = config_id
        mock_config.user_id = uuid4()
        mock_config.app_id = uuid4()
        mock_config.enabled = True
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_config
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_config_by_id(config_id)
        
        # Assert
        assert result is not None
        assert result.id == config_id

    @pytest.mark.asyncio
    async def test_get_config_by_id_not_found(self, config_service, mock_db_session):
        """Test: Configuración no encontrada por ID"""
        # Arrange
        config_id = uuid4()
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_config_by_id(config_id)
        
        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_config_by_user_and_app_success(self, config_service, mock_db_session):
        """Test: Obtención exitosa de configuración por usuario y app"""
        # Arrange
        user_id = uuid4()
        app_id = uuid4()
        
        mock_config = Mock(spec=APITriggeringConfig)
        mock_config.user_id = user_id
        mock_config.app_id = app_id
        mock_config.enabled = True
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_config
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_by_user_and_app(user_id, app_id)
        
        # Assert
        assert result is not None
        assert result.user_id == user_id
        assert result.app_id == app_id

    @pytest.mark.asyncio
    async def test_get_configs_by_user_success(self, config_service, mock_db_session):
        """Test: Obtención exitosa de configuraciones por usuario"""
        # Arrange
        user_id = uuid4()
        
        mock_configs = [
            Mock(spec=APITriggeringConfig, user_id=user_id, app_id=uuid4()),
            Mock(spec=APITriggeringConfig, user_id=user_id, app_id=uuid4())
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_configs
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_configs_by_user(user_id)
        
        # Assert
        assert result is not None
        assert len(result) == 2
        assert all(config.user_id == user_id for config in result)

    @pytest.mark.asyncio
    async def test_update_config_success(self, config_service, mock_db_session):
        """Test: Actualización exitosa de configuración"""
        # Arrange
        config_id = uuid4()
        update_data = APITriggeringConfigUpdate(
            enabled=False,
            confidence_threshold=0.8,
            max_auto_executions=10
        )
        
        mock_config = Mock(spec=APITriggeringConfig)
        mock_config.id = config_id
        mock_config.user_id = uuid4()
        mock_config.app_id = uuid4()
        mock_config.enabled = True
        mock_config.confidence_threshold = 0.7
        mock_config.max_auto_executions = 5
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_config
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.update_config(config_id, update_data)
        
        # Assert
        assert result is not None
        assert result.enabled == update_data.enabled
        assert result.confidence_threshold == update_data.confidence_threshold
        assert result.max_auto_executions == update_data.max_auto_executions
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_config_not_found(self, config_service, mock_db_session):
        """Test: Error al actualizar configuración no encontrada"""
        # Arrange
        config_id = uuid4()
        update_data = APITriggeringConfigUpdate(enabled=False)
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await config_service.update_config(config_id, update_data)
        
        assert "Configuration not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_config_success(self, config_service, mock_db_session):
        """Test: Eliminación exitosa de configuración"""
        # Arrange
        config_id = uuid4()
        
        mock_config = Mock(spec=APITriggeringConfig)
        mock_config.id = config_id
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_config
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.delete_config(config_id)
        
        # Assert
        assert result is True
        mock_db_session.delete.assert_called_once_with(mock_config)
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_config_not_found(self, config_service, mock_db_session):
        """Test: Error al eliminar configuración no encontrada"""
        # Arrange
        config_id = uuid4()
        
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            await config_service.delete_config(config_id)
        
        assert "Configuration not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_all_configs_success(self, config_service, mock_db_session):
        """Test: Obtención exitosa de todas las configuraciones"""
        # Arrange
        mock_configs = [
            Mock(spec=APITriggeringConfig, id=uuid4()),
            Mock(spec=APITriggeringConfig, id=uuid4()),
            Mock(spec=APITriggeringConfig, id=uuid4())
        ]
        
        mock_query = Mock()
        mock_query.all.return_value = mock_configs
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_all_configs()
        
        # Assert
        assert result is not None
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_configs_by_app_success(self, config_service, mock_db_session):
        """Test: Obtención exitosa de configuraciones por app"""
        # Arrange
        app_id = uuid4()
        
        mock_configs = [
            Mock(spec=APITriggeringConfig, app_id=app_id, user_id=uuid4()),
            Mock(spec=APITriggeringConfig, app_id=app_id, user_id=uuid4())
        ]
        
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = mock_configs
        mock_db_session.query.return_value = mock_query
        
        # Act
        result = await config_service.get_configs_by_app(app_id)
        
        # Assert
        assert result is not None
        assert len(result) == 2
        assert all(config.app_id == app_id for config in result)

    @pytest.mark.asyncio
    async def test_validate_config_data_success(self, config_service, sample_config_data):
        """Test: Validación exitosa de datos de configuración"""
        # Arrange
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Act
        result = config_service._validate_config_data(config_create)
        
        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_config_data_invalid_threshold(self, config_service, sample_config_data):
        """Test: Validación fallida por threshold inválido"""
        # Arrange
        sample_config_data["confidence_threshold"] = 1.5  # Inválido (> 1.0)
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            config_service._validate_config_data(config_create)
        
        assert "Confidence threshold must be between 0 and 1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_config_data_invalid_timeout(self, config_service, sample_config_data):
        """Test: Validación fallida por timeout inválido"""
        # Arrange
        sample_config_data["timeout_seconds"] = -1  # Inválido (< 0)
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            config_service._validate_config_data(config_create)
        
        assert "Timeout must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_config_data_invalid_max_executions(self, config_service, sample_config_data):
        """Test: Validación fallida por max_executions inválido"""
        # Arrange
        sample_config_data["max_auto_executions"] = 0  # Inválido (<= 0)
        config_create = APITriggeringConfigCreate(**sample_config_data)
        
        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            config_service._validate_config_data(config_create)
        
        assert "Max auto executions must be positive" in str(exc_info.value)
