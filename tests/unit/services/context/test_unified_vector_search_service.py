"""
🧪 TESTS UNITARIOS - UnifiedVectorSearchService

Tests para el servicio de búsqueda vectorial unificada
que permite buscar en múltiples tipos de recursos (DB, API, estrategias).
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import List, Dict, Any

from app.services.context.unified_vector_search_service import UnifiedVectorSearchService
from app.common.enums import EmbeddingResourceType


class TestUnifiedVectorSearchService:
    """Tests para UnifiedVectorSearchService"""

    @pytest.fixture
    def mock_vector_service(self):
        """Mock del servicio vectorial"""
        service = Mock()
        service.search_similar = AsyncMock(return_value=[])
        service.search_by_resource_type = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def mock_embedding_adapter(self):
        """Mock del adaptador de embeddings"""
        adapter = Mock()
        adapter.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
        return adapter

    @pytest.fixture
    def unified_search_service(self, mock_vector_service, mock_embedding_adapter):
        """Instancia del servicio para testing"""
        with patch('app.services.context.unified_vector_search_service.ServiceFactory') as mock_factory:
            mock_factory.get_vector_service.return_value = mock_vector_service
            mock_factory.get_embedding_adapter.return_value = mock_embedding_adapter
            
            return UnifiedVectorSearchService()

    @pytest.mark.asyncio
    async def test_search_database_schema_success(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda exitosa en esquema de base de datos"""
        # Arrange
        query = "usuarios con información de contacto"
        user_id = uuid4()
        connection_id = uuid4()
        
        mock_results = [
            {
                "id": str(uuid4()),
                "content": "users table with contact information",
                "metadata": {
                    "resource_type": EmbeddingResourceType.DATABASE,
                    "table_name": "users",
                    "connection_id": str(connection_id)
                },
                "similarity": 0.85
            }
        ]
        
        mock_vector_service.search_similar = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.search_database_schema(
            query, user_id, connection_id, limit=5
        )
        
        # Assert
        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "users table with contact information"
        assert result[0]["metadata"]["table_name"] == "users"
        assert result[0]["similarity"] == 0.85

    @pytest.mark.asyncio
    async def test_search_api_functions_success(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda exitosa en funciones de API"""
        # Arrange
        query = "obtener información de usuario"
        user_id = uuid4()
        app_id = uuid4()
        
        mock_results = [
            {
                "id": str(uuid4()),
                "content": "GET /users/{id} - Get user information by ID",
                "metadata": {
                    "resource_type": EmbeddingResourceType.API,
                    "endpoint": "GET /users/{id}",
                    "app_id": str(app_id)
                },
                "similarity": 0.92
            }
        ]
        
        mock_vector_service.search_similar = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.search_api_functions(
            query, user_id, app_id, limit=5
        )
        
        # Assert
        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "GET /users/{id} - Get user information by ID"
        assert result[0]["metadata"]["endpoint"] == "GET /users/{id}"
        assert result[0]["similarity"] == 0.92

    @pytest.mark.asyncio
    async def test_search_strategies_success(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda exitosa en estrategias"""
        # Arrange
        query = "estrategia de engagement de usuarios"
        user_id = uuid4()
        
        mock_results = [
            {
                "id": str(uuid4()),
                "content": "user engagement strategy with notification rules",
                "metadata": {
                    "resource_type": EmbeddingResourceType.STRATEGY,
                    "strategy_name": "user_engagement",
                    "user_id": str(user_id)
                },
                "similarity": 0.88
            }
        ]
        
        mock_vector_service.search_similar = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.search_strategies(
            query, user_id, limit=5
        )
        
        # Assert
        assert result is not None
        assert len(result) == 1
        assert result[0]["content"] == "user engagement strategy with notification rules"
        assert result[0]["metadata"]["strategy_name"] == "user_engagement"
        assert result[0]["similarity"] == 0.88

    @pytest.mark.asyncio
    async def test_unified_search_success(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda unificada exitosa en múltiples recursos"""
        # Arrange
        query = "información de usuarios"
        user_id = uuid4()
        connection_id = uuid4()
        app_id = uuid4()
        
        mock_results = [
            {
                "id": str(uuid4()),
                "content": "users table with user information",
                "metadata": {
                    "resource_type": EmbeddingResourceType.DATABASE,
                    "table_name": "users",
                    "connection_id": str(connection_id)
                },
                "similarity": 0.85
            },
            {
                "id": str(uuid4()),
                "content": "GET /users/{id} - Get user information",
                "metadata": {
                    "resource_type": EmbeddingResourceType.API,
                    "endpoint": "GET /users/{id}",
                    "app_id": str(app_id)
                },
                "similarity": 0.90
            }
        ]
        
        mock_vector_service.search_similar = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.unified_search(
            query, user_id, connection_id=connection_id, app_id=app_id, limit=10
        )
        
        # Assert
        assert result is not None
        assert len(result) == 2
        assert any(r["metadata"]["resource_type"] == EmbeddingResourceType.DATABASE for r in result)
        assert any(r["metadata"]["resource_type"] == EmbeddingResourceType.API for r in result)

    @pytest.mark.asyncio
    async def test_search_with_filters_success(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda con filtros específicos"""
        # Arrange
        query = "usuarios activos"
        user_id = uuid4()
        filters = {
            "resource_types": [EmbeddingResourceType.DATABASE],
            "table_names": ["users", "profiles"]
        }
        
        mock_results = [
            {
                "id": str(uuid4()),
                "content": "users table with active status",
                "metadata": {
                    "resource_type": EmbeddingResourceType.DATABASE,
                    "table_name": "users"
                },
                "similarity": 0.87
            }
        ]
        
        mock_vector_service.search_with_filters = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.search_with_filters(
            query, user_id, filters, limit=5
        )
        
        # Assert
        assert result is not None
        assert len(result) == 1
        assert result[0]["metadata"]["table_name"] == "users"

    @pytest.mark.asyncio
    async def test_search_no_results(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda sin resultados"""
        # Arrange
        query = "consulta que no existe"
        user_id = uuid4()
        
        mock_vector_service.search_similar = AsyncMock(return_value=[])
        
        # Act
        result = await unified_search_service.search_database_schema(
            query, user_id, uuid4(), limit=5
        )
        
        # Assert
        assert result is not None
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_search_with_embedding_generation(self, unified_search_service, mock_embedding_adapter):
        """Test: Búsqueda con generación de embedding"""
        # Arrange
        query = "nueva consulta"
        user_id = uuid4()
        
        mock_embedding_adapter.generate_embedding = AsyncMock(
            return_value=[0.1, 0.2, 0.3, 0.4, 0.5]
        )
        
        # Act
        embedding = await unified_search_service._generate_query_embedding(query)
        
        # Assert
        assert embedding is not None
        assert len(embedding) == 5
        assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]

    @pytest.mark.asyncio
    async def test_rank_results_by_relevance(self, unified_search_service):
        """Test: Ranking de resultados por relevancia"""
        # Arrange
        results = [
            {"similarity": 0.7, "content": "result 1"},
            {"similarity": 0.9, "content": "result 2"},
            {"similarity": 0.6, "content": "result 3"},
            {"similarity": 0.8, "content": "result 4"}
        ]
        
        # Act
        ranked_results = unified_search_service._rank_results_by_relevance(results)
        
        # Assert
        assert len(ranked_results) == 4
        assert ranked_results[0]["similarity"] == 0.9  # Mayor similitud primero
        assert ranked_results[1]["similarity"] == 0.8
        assert ranked_results[2]["similarity"] == 0.7
        assert ranked_results[3]["similarity"] == 0.6

    @pytest.mark.asyncio
    async def test_filter_results_by_threshold(self, unified_search_service):
        """Test: Filtrado de resultados por umbral de similitud"""
        # Arrange
        results = [
            {"similarity": 0.9, "content": "high relevance"},
            {"similarity": 0.7, "content": "medium relevance"},
            {"similarity": 0.5, "content": "low relevance"},
            {"similarity": 0.8, "content": "good relevance"}
        ]
        threshold = 0.7
        
        # Act
        filtered_results = unified_search_service._filter_by_similarity_threshold(
            results, threshold
        )
        
        # Assert
        assert len(filtered_results) == 3  # Solo los >= 0.7
        assert all(r["similarity"] >= threshold for r in filtered_results)

    @pytest.mark.asyncio
    async def test_group_results_by_resource_type(self, unified_search_service):
        """Test: Agrupación de resultados por tipo de recurso"""
        # Arrange
        results = [
            {
                "similarity": 0.9,
                "metadata": {"resource_type": EmbeddingResourceType.DATABASE}
            },
            {
                "similarity": 0.8,
                "metadata": {"resource_type": EmbeddingResourceType.API}
            },
            {
                "similarity": 0.7,
                "metadata": {"resource_type": EmbeddingResourceType.DATABASE}
            }
        ]
        
        # Act
        grouped = unified_search_service._group_results_by_resource_type(results)
        
        # Assert
        assert EmbeddingResourceType.DATABASE in grouped
        assert EmbeddingResourceType.API in grouped
        assert len(grouped[EmbeddingResourceType.DATABASE]) == 2
        assert len(grouped[EmbeddingResourceType.API]) == 1

    @pytest.mark.asyncio
    async def test_error_handling_embedding_generation(self, unified_search_service, mock_embedding_adapter):
        """Test: Manejo de errores en generación de embedding"""
        # Arrange
        mock_embedding_adapter.generate_embedding = AsyncMock(
            side_effect=Exception("Embedding generation failed")
        )
        
        query = "test query"
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await unified_search_service._generate_query_embedding(query)
        
        assert "Embedding generation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_handling_vector_search(self, unified_search_service, mock_vector_service):
        """Test: Manejo de errores en búsqueda vectorial"""
        # Arrange
        mock_vector_service.search_similar = AsyncMock(
            side_effect=Exception("Vector search failed")
        )
        
        query = "test query"
        user_id = uuid4()
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await unified_search_service.search_database_schema(
                query, user_id, uuid4(), limit=5
            )
        
        assert "Vector search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_with_pagination(self, unified_search_service, mock_vector_service):
        """Test: Búsqueda con paginación"""
        # Arrange
        query = "usuarios"
        user_id = uuid4()
        page = 2
        page_size = 10
        
        mock_results = [
            {"similarity": 0.8, "content": f"result {i}"}
            for i in range(page_size)
        ]
        
        mock_vector_service.search_similar = AsyncMock(return_value=mock_results)
        
        # Act
        result = await unified_search_service.search_database_schema(
            query, user_id, uuid4(), limit=page_size, offset=page * page_size
        )
        
        # Assert
        assert result is not None
        assert len(result) == page_size
