#!/usr/bin/env python3
"""
🧪 Tests Unitarios para SmartFallbackService

Tests que validan la funcionalidad del servicio de fallback inteligente.
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock
from app.services.ai.smart_fallback_service import SmartFallbackService, FallbackType, FallbackStrategy


class TestSmartFallbackService:
    """Tests para SmartFallbackService"""
    
    @pytest.fixture
    def service(self):
        """Instancia del servicio para testing"""
        mock_factory = Mock()
        mock_factory.user = Mock(id=uuid.uuid4())
        return SmartFallbackService(mock_factory)
    
    @pytest.fixture
    def mock_fallback_info(self):
        """Información de fallback mock para testing"""
        return {
            "fallback_type": FallbackType.MODE_DETECTION_FAILED,
            "query": "test query",
            "context": {"mode": "EXPLORER"}
        }

    # =============================================================================
    # 🧪 TESTS BÁSICOS
    # =============================================================================

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test de inicialización del servicio"""
        assert service.user_id is not None
        assert service.factory is not None
        assert len(service._fallback_configs) > 0
        assert FallbackType.MODE_DETECTION_FAILED in service._fallback_configs
        assert FallbackType.UNKNOWN in service._fallback_configs

    @pytest.mark.asyncio
    async def test_fallback_types(self):
        """Test de tipos de fallback"""
        assert FallbackType.MODE_DETECTION_FAILED.value == "mode_detection_failed"
        assert FallbackType.RESOURCE_CONFLICT.value == "resource_conflict"
        assert FallbackType.AGENT_NOT_FOUND.value == "agent_not_found"
        assert FallbackType.SYSTEM_ERROR.value == "system_error"
        assert FallbackType.AMBIGUOUS_QUERY.value == "ambiguous_query"
        assert FallbackType.TIMEOUT.value == "timeout"
        assert FallbackType.UNKNOWN.value == "unknown"

    @pytest.mark.asyncio
    async def test_fallback_strategies(self):
        """Test de estrategias de fallback"""
        assert FallbackStrategy.BINARY_CHOICE.value == "binary_choice"
        assert FallbackStrategy.RESOURCE_LIST.value == "resource_list"
        assert FallbackStrategy.MODE_SELECTION.value == "mode_selection"
        assert FallbackStrategy.RETRY.value == "retry"
        assert FallbackStrategy.HELP.value == "help"

    @pytest.mark.asyncio
    async def test_fallback_configs_structure(self, service):
        """Test de estructura de configuraciones de fallback"""
        for fallback_type, config in service._fallback_configs.items():
            assert "strategy" in config
            assert "message" in config
            assert "options" in config
            assert "recovery_timeout" in config
            assert isinstance(config["strategy"], FallbackStrategy)
            assert isinstance(config["message"], str)
            assert isinstance(config["options"], list)
            assert isinstance(config["recovery_timeout"], int)

    @pytest.mark.asyncio
    async def test_unknown_fallback_config(self, service):
        """Test de configuración para fallback desconocido"""
        unknown_config = service._fallback_configs[FallbackType.UNKNOWN]
        assert unknown_config["strategy"] == FallbackStrategy.BINARY_CHOICE
        assert "Would you like me to show your resources or start with a plan?" in unknown_config["message"]
        assert len(unknown_config["options"]) == 2
        assert unknown_config["recovery_timeout"] == 30
