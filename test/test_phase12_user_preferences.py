"""
🎯 FASE 12: Tests para preferencias de usuario (persistentes).

Este archivo de test valida la funcionalidad de las preferencias de usuario
que personalizan la experiencia del chat y las confirmaciones.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException

from app.schemas.user_schema import (
    UserPreferences, 
    UserPreferencesUpdate, 
    UserPreferencesResponse
)
from app.services.management.user_service import UserService
from app.models.user_model import User


class TestUserPreferences:
    """Tests para el esquema de preferencias de usuario."""
    
    def test_user_preferences_defaults(self):
        """Test que las preferencias por defecto son correctas."""
        preferences = UserPreferences()
        
        assert preferences.response_format == "detailed"
        assert preferences.detail_level == "medium"
        assert preferences.risk_tolerance == "medium"
        assert preferences.confirmations is True
        assert preferences.language == "es"
        assert preferences.timezone == "UTC"
    
    def test_user_preferences_custom_values(self):
        """Test que se pueden establecer valores personalizados."""
        preferences = UserPreferences(
            response_format="concise",
            detail_level="high",
            risk_tolerance="low",
            confirmations=False,
            language="en",
            timezone="America/New_York"
        )
        
        assert preferences.response_format == "concise"
        assert preferences.detail_level == "high"
        assert preferences.risk_tolerance == "low"
        assert preferences.confirmations is False
        assert preferences.language == "en"
        assert preferences.timezone == "America/New_York"
    
    def test_user_preferences_validation(self):
        """Test que la validación de valores enum funciona."""
        with pytest.raises(ValueError):
            UserPreferences(response_format="invalid")
        
        with pytest.raises(ValueError):
            UserPreferences(detail_level="invalid")
        
        with pytest.raises(ValueError):
            UserPreferences(risk_tolerance="invalid")
        
        with pytest.raises(ValueError):
            UserPreferences(language="invalid")


class TestUserPreferencesUpdate:
    """Tests para la actualización de preferencias."""
    
    def test_partial_update(self):
        """Test que se puede actualizar solo algunos campos."""
        update = UserPreferencesUpdate(
            response_format="minimal",
            language="fr"
        )
        
        # Solo los campos especificados deben estar presentes
        data = update.model_dump(exclude_unset=True)
        assert "response_format" in data
        assert "language" in data
        assert "detail_level" not in data
        assert "risk_tolerance" not in data
        assert "confirmations" not in data
        assert "timezone" not in data
    
    def test_empty_update(self):
        """Test que un update vacío no modifica nada."""
        update = UserPreferencesUpdate()
        data = update.model_dump(exclude_unset=True)
        assert len(data) == 0


class TestUserPreferencesResponse:
    """Tests para la respuesta de preferencias."""
    
    def test_user_preferences_response(self):
        """Test que la respuesta se construye correctamente."""
        user_id = uuid4()
        preferences = UserPreferences(
            response_format="concise",
            detail_level="low"
        )
        updated_at = datetime.utcnow()
        
        response = UserPreferencesResponse(
            user_id=user_id,
            preferences=preferences,
            updated_at=updated_at
        )
        
        assert response.user_id == user_id
        assert response.preferences == preferences
        assert response.updated_at == updated_at


class TestUserModelPreferences:
    """Tests para los métodos de preferencias del modelo User."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.user = User(
            email="test@example.com",
            name="Test User"
        )
    
    def test_update_preferences(self):
        """Test que se pueden actualizar las preferencias."""
        # Cambiar solo algunos campos
        self.user.update_preferences(
            response_format="minimal",
            language="en"
        )
        
        assert self.user.response_format == "minimal"
        assert self.user.language == "en"
        # Los demás campos deben mantener sus valores por defecto
        assert self.user.detail_level == "medium"
        assert self.user.risk_tolerance == "medium"
        assert self.user.confirmations is True
        assert self.user.timezone == "UTC"
    
    def test_update_preferences_invalid_field(self):
        """Test que campos inválidos no se actualizan."""
        original_format = self.user.response_format
        
        # Intentar actualizar un campo que no existe
        self.user.update_preferences(invalid_field="value")
        
        # El campo original no debe cambiar
        assert self.user.response_format == original_format
    
    def test_get_preferences(self):
        """Test que se obtienen todas las preferencias."""
        preferences = self.user.get_preferences()
        
        expected_keys = {
            'response_format', 'detail_level', 'risk_tolerance',
            'confirmations', 'language', 'timezone'
        }
        
        assert set(preferences.keys()) == expected_keys
        assert preferences['response_format'] == "detailed"
        assert preferences['detail_level'] == "medium"
        assert preferences['risk_tolerance'] == "medium"
        assert preferences['confirmations'] is True
        assert preferences['language'] == "es"
        assert preferences['timezone'] == "UTC"
    
    def test_should_confirm_action(self):
        """Test que la lógica de confirmación funciona correctamente."""
        # Usuario con tolerancia media
        self.user.risk_tolerance = "medium"
        self.user.confirmations = True
        
        # Acción de riesgo bajo - no requiere confirmación
        assert self.user.should_confirm_action("low") is False
        
        # Acción de riesgo medio - requiere confirmación
        assert self.user.should_confirm_action("medium") is True
        
        # Acción de riesgo alto - requiere confirmación
        assert self.user.should_confirm_action("high") is True
    
    def test_should_confirm_action_no_confirmations(self):
        """Test que sin confirmaciones habilitadas, nunca se pide confirmación."""
        self.user.confirmations = False
        
        # No importa el nivel de riesgo, nunca se pide confirmación
        assert self.user.should_confirm_action("low") is False
        assert self.user.should_confirm_action("medium") is False
        assert self.user.should_confirm_action("high") is False
    
    def test_should_confirm_action_different_tolerances(self):
        """Test que diferentes tolerancias al riesgo funcionan correctamente."""
        # Usuario con tolerancia baja
        self.user.risk_tolerance = "low"
        self.user.confirmations = True
        
        assert self.user.should_confirm_action("low") is True
        assert self.user.should_confirm_action("medium") is True
        assert self.user.should_confirm_action("high") is True
        
        # Usuario con tolerancia alta
        self.user.risk_tolerance = "high"
        
        assert self.user.should_confirm_action("low") is False
        assert self.user.should_confirm_action("medium") is False
        # Acción de riesgo alto requiere confirmación incluso para usuarios con alta tolerancia
        assert self.user.should_confirm_action("high") is True


class TestUserServicePreferences:
    """Tests para el servicio de usuario con preferencias."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.mock_factory = Mock()
        self.mock_db = Mock()
        self.mock_factory.db = self.mock_db
        
        self.user_service = UserService(self.mock_factory)
        
        # Mock user con preferencias reales
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.mock_user.email = "test@example.com"
        self.mock_user.name = "Test User"
        self.mock_user.updated_at = datetime.utcnow()
        
        # Configurar métodos de preferencias
        self.mock_user.get_preferences.return_value = {
            'response_format': 'concise',
            'detail_level': 'high',
            'risk_tolerance': 'medium',
            'confirmations': True,
            'language': 'en',
            'timezone': 'UTC'
        }
        self.mock_user.should_confirm_action.return_value = True
    
    def test_get_user_preferences_user_not_found(self):
        """Test que retorna None si el usuario no existe."""
        # Mock del método get_user_by_id para que retorne None
        self.user_service.get_user_by_id = Mock(return_value=None)
        
        result = self.user_service.get_user_preferences(999)
        
        assert result is None
    
    def test_get_user_preferences_user_found(self):
        """Test que retorna las preferencias si el usuario existe."""
        # Mock del método get_user_by_id para que retorne un usuario
        self.user_service.get_user_by_id = Mock(return_value=self.mock_user)
        
        result = self.user_service.get_user_preferences(1)
        
        assert result is not None
        assert result.response_format == 'concise'
        assert result.detail_level == 'high'
    
    def test_update_user_preferences_user_not_found(self):
        """Test que lanza error si el usuario no existe."""
        # Mock del método get_user_by_id para que retorne None
        self.user_service.get_user_by_id = Mock(return_value=None)
        
        preferences_update = UserPreferencesUpdate(response_format="minimal")
        
        with pytest.raises(HTTPException) as exc_info:
            self.user_service.update_user_preferences(999, preferences_update)
        
        assert exc_info.value.status_code == 404
    
    def test_update_user_preferences_success(self):
        """Test que actualiza las preferencias correctamente."""
        # Mock del método get_user_by_id para que retorne un usuario
        self.user_service.get_user_by_id = Mock(return_value=self.mock_user)
        
        # Mock del método update_preferences del usuario
        self.mock_user.update_preferences.return_value = None
        
        preferences_update = UserPreferencesUpdate(
            response_format="minimal",
            detail_level="low"
        )
        
        result = self.user_service.update_user_preferences(1, preferences_update)
        
        # Verificar que se llamaron los métodos correctos
        self.mock_user.update_preferences.assert_called_once()
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once()
        
        assert result is not None
        assert result.response_format == 'concise'
        assert result.detail_level == 'high'
    
    def test_should_confirm_action(self):
        """Test que el servicio determina correctamente si se requiere confirmación."""
        # Mock del método get_user_by_id para que retorne un usuario
        self.user_service.get_user_by_id = Mock(return_value=self.mock_user)
        
        result = self.user_service.should_confirm_action(1, "medium")
        
        assert result is True
        self.mock_user.should_confirm_action.assert_called_once_with("medium")
    
    def test_should_confirm_action_user_not_found(self):
        """Test que por defecto pide confirmación si no se encuentra el usuario."""
        # Mock del método get_user_by_id para que retorne None
        self.user_service.get_user_by_id = Mock(return_value=None)
        
        result = self.user_service.should_confirm_action(999, "medium")
        
        # Por defecto, debe pedir confirmación
        assert result is True


class TestUserPreferencesIntegration:
    """Tests de integración para las preferencias de usuario."""
    
    def test_preferences_flow_complete(self):
        """Test del flujo completo de preferencias."""
        # 1. Crear usuario con preferencias por defecto
        user = User(
            email="integration@example.com",
            name="Integration User"
        )
        
        # Verificar preferencias por defecto
        preferences = user.get_preferences()
        assert preferences['response_format'] == "detailed"
        assert preferences['language'] == "es"
        
        # 2. Actualizar preferencias
        user.update_preferences(
            response_format="concise",
            language="en",
            risk_tolerance="low"
        )
        
        # Verificar cambios
        updated_preferences = user.get_preferences()
        assert updated_preferences['response_format'] == "concise"
        assert updated_preferences['language'] == "en"
        assert updated_preferences['risk_tolerance'] == "low"
        
        # 3. Verificar lógica de confirmación
        assert user.should_confirm_action("low") is True   # Tolerancia baja
        assert user.should_confirm_action("medium") is True  # Tolerancia baja
        assert user.should_confirm_action("high") is True    # Tolerancia baja
        
        # 4. Cambiar tolerancia y verificar
        user.update_preferences(risk_tolerance="high")
        assert user.should_confirm_action("low") is False   # Tolerancia alta
        assert user.should_confirm_action("medium") is False # Tolerancia alta
        # Acción de riesgo alto requiere confirmación incluso para usuarios con alta tolerancia
        assert user.should_confirm_action("high") is True   # Tolerancia alta
    
    def test_preferences_serialization(self):
        """Test que las preferencias se serializan correctamente."""
        preferences = UserPreferences(
            response_format="minimal",
            detail_level="high",
            risk_tolerance="low",
            confirmations=False,
            language="en",
            timezone="UTC"
        )
        
        # Serializar a dict
        data = preferences.model_dump()
        
        # Verificar que todos los campos están presentes
        expected_fields = {
            'response_format', 'detail_level', 'risk_tolerance',
            'confirmations', 'language', 'timezone'
        }
        assert set(data.keys()) == expected_fields
        
        # Verificar valores
        assert data['response_format'] == "minimal"
        assert data['detail_level'] == "high"
        assert data['risk_tolerance'] == "low"
        assert data['confirmations'] is False
        assert data['language'] == "en"
        assert data['timezone'] == "UTC"
