#!/usr/bin/env python3
"""
🧪 Tests Unitarios para ResourcePriorityService

Tests que validan la funcionalidad del servicio de priorización de recursos.
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock
from app.services.ai.resource_priority_service import ResourcePriorityService, ResourceType, PriorityLevel


class TestResourcePriorityService:
    """Tests para ResourcePriorityService"""
    
    @pytest.fixture
    def service(self):
        """Instancia del servicio para testing"""
        mock_factory = Mock()
        mock_factory.user = Mock(id=uuid.uuid4())
        return ResourcePriorityService(mock_factory)
    
    @pytest.fixture
    def mock_resources(self):
        """Recursos mock para testing"""
        return [
            {"id": 1, "name": "test_db", "type": "postgresql", "priority": "HIGH"},
            {"id": 2, "name": "test_app", "type": "web", "priority": "LOW"}
        ]
    
    @pytest.fixture
    def mock_context(self):
        """Contexto mock para testing"""
        return {
            "user_id": uuid.uuid4(),
            "session_id": uuid.uuid4(),
            "current_mode": "EXPLORER",
            "query_type": "resource_analysis"
        }

    # =============================================================================
    # 🎯 TESTS BÁSICOS
    # =============================================================================

    @pytest.mark.asyncio
    async def test_prioritize_resources_basic(self, service, mock_resources, mock_context):
        """Test de priorización básica de recursos"""
        result = await service.prioritize_resources(
            requested_resources=mock_resources,
            query_context=mock_context
        )
        
        assert result is not None
        assert "success" in result
        assert "prioritized_resources" in result
        assert "execution_plan" in result

    @pytest.mark.asyncio
    async def test_prioritize_resources_empty(self, service, mock_context):
        """Test de priorización con recursos vacíos"""
        result = await service.prioritize_resources(
            requested_resources=[],
            query_context=mock_context
        )
        
        assert result is not None
        assert result["success"] is True
        assert result["prioritized_resources"] == []

    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test de inicialización del servicio"""
        assert service.user_id is not None
        assert service.factory is not None
        assert len(service._type_priorities) == 3
        assert ResourceType.DATABASE in service._type_priorities
        assert ResourceType.APP in service._type_priorities
        assert ResourceType.STRATEGY in service._type_priorities

    @pytest.mark.asyncio
    async def test_priority_levels(self):
        """Test de niveles de prioridad"""
        assert PriorityLevel.CRITICAL.value == 1
        assert PriorityLevel.HIGH.value == 2
        assert PriorityLevel.MEDIUM.value == 3
        assert PriorityLevel.LOW.value == 4
        assert PriorityLevel.MINIMAL.value == 5

    @pytest.mark.asyncio
    async def test_resource_types(self):
        """Test de tipos de recursos"""
        assert ResourceType.DATABASE.value == "database"
        assert ResourceType.APP.value == "app"
        assert ResourceType.STRATEGY.value == "strategy"
        assert ResourceType.UNKNOWN.value == "unknown"
