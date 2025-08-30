"""
🧪 TESTS UNITARIOS - ExtensibleEmbeddingService

Tests para el servicio extensible de generación de embeddings
que soporta diferentes tipos de recursos (DB, API, estrategias).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import List, Dict, Any

from app.services.context.extensible_embedding_service import ExtensibleEmbeddingService
from app.common.enums import EmbeddingResourceType


class TestExtensibleEmbeddingService:
    """Tests para ExtensibleEmbeddingService"""

    @pytest.fixture
    def mock_embedding_adapter(self):
        """Mock del adaptador de embeddings"""
        adapter = Mock()
        adapter.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
        adapter.generate_embeddings_batch = AsyncMock(
            return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        )
        return adapter

    @pytest.fixture
    def mock_vector_service(self):
        """Mock del servicio vectorial"""
        service = Mock()
        service.store_embedding = AsyncMock(return_value=uuid4())
        service.store_embeddings_batch = AsyncMock(return_value=[uuid4(), uuid4()])
        service.search_similar = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def embedding_service(self, mock_embedding_adapter, mock_vector_service):
        """Instancia del servicio para testing"""
        with patch('app.services.context.extensible_embedding_service.ServiceFactory') as mock_factory:
            mock_factory.get_embedding_adapter.return_value = mock_embedding_adapter
            mock_factory.get_vector_service.return_value = mock_vector_service
            
            return ExtensibleEmbeddingService()

    @pytest.mark.asyncio
    async def test_generate_api_embeddings_success(self, embedding_service, mock_embedding_adapter):
        """Test: Generación exitosa de embeddings para APIs"""
        # Arrange
        api_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "Get users",
                        "description": "Retrieve list of users",
                        "parameters": [
                            {"name": "limit", "description": "Number of users to return"}
                        ]
                    }
                }
            }
        }
        app_id = uuid4()
        
        # Act
        result = await embedding_service.generate_api_embeddings(api_spec, app_id)
        
        # Assert
        assert result is not None
        assert "chunks_created" in result
        assert "embeddings_generated" in result
        assert result["chunks_created"] > 0
        assert result["embeddings_generated"] > 0

    @pytest.mark.asyncio
    async def test_generate_api_embeddings_empty_spec(self, embedding_service):
        """Test: Generación con especificación vacía"""
        # Arrange
        api_spec = {}
        app_id = uuid4()
        
        # Act
        result = await embedding_service.generate_api_embeddings(api_spec, app_id)
        
        # Assert
        assert result is not None
        assert result["chunks_created"] == 0
        assert result["embeddings_generated"] == 0

    @pytest.mark.asyncio
    async def test_generate_db_embeddings_success(self, embedding_service, mock_embedding_adapter):
        """Test: Generación exitosa de embeddings para DB"""
        # Arrange
        db_schema = {
            "tables": [
                {
                    "name": "users",
                    "description": "User information table",
                    "columns": [
                        {"name": "id", "type": "integer", "description": "User ID"},
                        {"name": "name", "type": "varchar", "description": "User name"}
                    ]
                }
            ]
        }
        connection_id = uuid4()
        
        # Act
        result = await embedding_service.generate_db_embeddings(db_schema, connection_id)
        
        # Assert
        assert result is not None
        assert "chunks_created" in result
        assert "embeddings_generated" in result
        assert result["chunks_created"] > 0
        assert result["embeddings_generated"] > 0

    @pytest.mark.asyncio
    async def test_generate_strategy_embeddings_success(self, embedding_service, mock_embedding_adapter):
        """Test: Generación exitosa de embeddings para estrategias"""
        # Arrange
        strategy_config = {
            "name": "user_engagement_strategy",
            "description": "Strategy for improving user engagement",
            "rules": [
                {"condition": "user_active", "action": "send_notification"},
                {"condition": "user_inactive", "action": "send_reminder"}
            ]
        }
        user_id = uuid4()
        
        # Act
        result = await embedding_service.generate_strategy_embeddings(strategy_config, user_id)
        
        # Assert
        assert result is not None
        assert "chunks_created" in result
        assert "embeddings_generated" in result
        assert result["chunks_created"] > 0
        assert result["embeddings_generated"] > 0

    @pytest.mark.asyncio
    async def test_create_chunks_from_api_spec(self, embedding_service):
        """Test: Creación de chunks desde especificación API"""
        # Arrange
        api_spec = {
            "paths": {
                "/users/{id}": {
                    "get": {
                        "summary": "Get user by ID",
                        "description": "Retrieve a specific user by their ID",
                        "parameters": [
                            {"name": "id", "description": "User ID"}
                        ]
                    }
                }
            }
        }
        
        # Act
        chunks = embedding_service._create_chunks_from_api_spec(api_spec)
        
        # Assert
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
        assert all(chunk["metadata"]["resource_type"] == EmbeddingResourceType.API for chunk in chunks)

    @pytest.mark.asyncio
    async def test_create_chunks_from_db_schema(self, embedding_service):
        """Test: Creación de chunks desde esquema de DB"""
        # Arrange
        db_schema = {
            "tables": [
                {
                    "name": "orders",
                    "description": "Customer orders table",
                    "columns": [
                        {"name": "order_id", "type": "integer", "description": "Order identifier"},
                        {"name": "customer_id", "type": "integer", "description": "Customer identifier"}
                    ]
                }
            ]
        }
        
        # Act
        chunks = embedding_service._create_chunks_from_db_schema(db_schema)
        
        # Assert
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
        assert all(chunk["metadata"]["resource_type"] == EmbeddingResourceType.DATABASE for chunk in chunks)

    @pytest.mark.asyncio
    async def test_create_chunks_from_strategy_config(self, embedding_service):
        """Test: Creación de chunks desde configuración de estrategia"""
        # Arrange
        strategy_config = {
            "name": "pricing_strategy",
            "description": "Dynamic pricing strategy based on demand",
            "rules": [
                {"condition": "high_demand", "action": "increase_price"},
                {"condition": "low_demand", "action": "decrease_price"}
            ]
        }
        
        # Act
        chunks = embedding_service._create_chunks_from_strategy_config(strategy_config)
        
        # Assert
        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("metadata" in chunk for chunk in chunks)
        assert all(chunk["metadata"]["resource_type"] == EmbeddingResourceType.STRATEGY for chunk in chunks)

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(self, embedding_service, mock_embedding_adapter):
        """Test: Generación exitosa de embeddings en lote"""
        # Arrange
        chunks = [
            {"content": "Get user information", "metadata": {"type": "api"}},
            {"content": "Create new user", "metadata": {"type": "api"}}
        ]
        
        # Act
        result = await embedding_service._generate_embeddings_batch(chunks)
        
        # Assert
        assert result is not None
        assert len(result) == len(chunks)
        assert all("embedding" in chunk for chunk in result)
        assert all("content" in chunk for chunk in result)
        assert all("metadata" in chunk for chunk in result)

    @pytest.mark.asyncio
    async def test_store_embeddings_success(self, embedding_service, mock_vector_service):
        """Test: Almacenamiento exitoso de embeddings"""
        # Arrange
        chunks_with_embeddings = [
            {
                "content": "Get user information",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {"resource_type": EmbeddingResourceType.API, "app_id": str(uuid4())}
            }
        ]
        
        # Act
        result = await embedding_service._store_embeddings(chunks_with_embeddings)
        
        # Assert
        assert result is not None
        assert "stored_count" in result
        assert result["stored_count"] > 0

    @pytest.mark.asyncio
    async def test_cleanup_old_embeddings_success(self, embedding_service, mock_vector_service):
        """Test: Limpieza exitosa de embeddings antiguos"""
        # Arrange
        resource_type = EmbeddingResourceType.API
        resource_id = str(uuid4())
        
        mock_vector_service.delete_by_resource = AsyncMock(return_value=5)
        
        # Act
        result = await embedding_service.cleanup_old_embeddings(resource_type, resource_id)
        
        # Assert
        assert result is not None
        assert "deleted_count" in result
        assert result["deleted_count"] == 5

    @pytest.mark.asyncio
    async def test_get_embedding_stats_success(self, embedding_service, mock_vector_service):
        """Test: Obtención exitosa de estadísticas de embeddings"""
        # Arrange
        mock_vector_service.get_embedding_stats = AsyncMock(
            return_value={
                "total_embeddings": 100,
                "by_resource_type": {
                    "api": 50,
                    "database": 30,
                    "strategy": 20
                }
            }
        )
        
        # Act
        result = await embedding_service.get_embedding_stats()
        
        # Assert
        assert result is not None
        assert "total_embeddings" in result
        assert result["total_embeddings"] == 100
        assert "by_resource_type" in result
        assert result["by_resource_type"]["api"] == 50

    @pytest.mark.asyncio
    async def test_error_handling_embedding_generation(self, embedding_service, mock_embedding_adapter):
        """Test: Manejo de errores en generación de embeddings"""
        # Arrange
        mock_embedding_adapter.generate_embeddings_batch = AsyncMock(
            side_effect=Exception("Embedding generation failed")
        )
        
        chunks = [{"content": "Test content", "metadata": {"type": "api"}}]
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await embedding_service._generate_embeddings_batch(chunks)
        
        assert "Embedding generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_storage(self, embedding_service, mock_vector_service):
        """Test: Manejo de errores en almacenamiento"""
        # Arrange
        mock_vector_service.store_embeddings_batch = AsyncMock(
            side_effect=Exception("Storage failed")
        )
        
        chunks_with_embeddings = [
            {
                "content": "Test content",
                "embedding": [0.1, 0.2, 0.3],
                "metadata": {"resource_type": EmbeddingResourceType.API}
            }
        ]
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await embedding_service._store_embeddings(chunks_with_embeddings)
        
        assert "Storage failed" in str(exc_info.value)
