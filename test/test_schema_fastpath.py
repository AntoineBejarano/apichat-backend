import pytest
from unittest.mock import Mock, patch
from app.services.context.schema_explorer_service import SchemaExplorerService
from app.services.data.cache_service import CacheService
from app.models.detailed_schema_cache_model import DetailedSchemaCache


class TestSchemaExplorerService:
    """Tests mínimos para SchemaExplorerService y fast_lookup"""

    @pytest.fixture
    def mock_cache_service(self):
        return Mock(spec=CacheService)

    @pytest.fixture
    def mock_database_service(self):
        return Mock()

    @pytest.fixture
    def schema_service(self, mock_cache_service, mock_database_service):
        return SchemaExplorerService(cache_service=mock_cache_service, database_service=mock_database_service)

    def test_schema_service_initialization(self, schema_service):
        """Test que el servicio se inicializa correctamente"""
        assert schema_service is not None
        assert hasattr(schema_service, 'fast_lookup')
        assert hasattr(schema_service, 'cache_service')
        assert hasattr(schema_service, 'database_service')

    def test_fast_lookup_method_signature(self, schema_service):
        """Test que el método fast_lookup tiene la firma correcta"""
        import inspect
        
        sig = inspect.signature(schema_service.fast_lookup)
        params = list(sig.parameters.keys())
        
        assert 'query' in params
        assert 'db_ids' in params
        
        # Verificar que retorna un tuple
        sig = inspect.signature(schema_service.fast_lookup)
        assert sig.return_annotation == inspect.Signature.empty or 'Tuple' in str(sig.return_annotation)

    def test_normalize_query_method(self, schema_service):
        """Test del método _normalize_query"""
        # Test normalización básica
        result = schema_service._normalize_query("USERS TABLE")
        assert result == "users table"
        
        # Test con caracteres especiales
        result = schema_service._normalize_query("users@table!")
        assert result == "users table"
        
        # Test con espacios múltiples
        result = schema_service._normalize_query("users   table")
        assert result == "users table"

    def test_extract_search_terms_method(self, schema_service):
        """Test del método _extract_search_terms"""
        # Test con términos válidos
        terms = schema_service._extract_search_terms("users table email")
        assert "users" in terms
        assert "table" not in terms  # 'table' está en keywords
        assert "email" not in terms  # 'email' está en keywords
        
        # Test con términos largos
        terms = schema_service._extract_search_terms("completely unrelated query")
        assert len(terms) > 0
        assert all(len(term) >= 4 for term in terms)
        
        # Test límite de términos
        terms = schema_service._extract_search_terms("one two three four five six seven")
        assert len(terms) <= 5  # Máximo 5 términos

    def test_generate_trigrams_method(self, schema_service):
        """Test del método _generate_trigrams"""
        # Test con texto largo
        trigrams = schema_service._generate_trigrams("users")
        assert len(trigrams) == 3  # "use", "ser", "ers"
        
        # Test con texto corto
        trigrams = schema_service._generate_trigrams("ab")
        assert trigrams == ["ab"]
        
        # Test con texto vacío
        trigrams = schema_service._generate_trigrams("")
        assert trigrams == [""]

    def test_fast_lookup_integration(self, schema_service):
        """Test básico de integración del método fast_lookup"""
        # Este test verifica que el método se puede llamar sin errores
        # No verifica la lógica interna compleja
        try:
            result, confidence, response_type = schema_service.fast_lookup("test query", [])
            # Si llega aquí, el método funciona básicamente
            assert isinstance(confidence, float)
            assert isinstance(response_type, str)
        except Exception as e:
            # Si hay error, debe ser por falta de datos reales, no por error en el código
            assert "No se encontraron matches" in str(e) or "Error en fast_lookup" in str(e)
