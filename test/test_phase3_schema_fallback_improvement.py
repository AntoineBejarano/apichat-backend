"""
🔧 FASE 3: Test de mejora del fallback de esquema
─────────────────────────────────────────────────
Verifica que el sistema proporcione mensajes útiles cuando no hay esquema
disponible y ofrezca opciones claras al usuario.
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4
from app.services.context.schema_explorer_service import SchemaExplorerService


class TestPhase3SchemaFallbackImprovement:
    """Test de la FASE 3: Mejora del fallback de esquema"""
    
    @pytest.fixture
    def mock_cache_service(self):
        """Cache service mock"""
        cache_service = Mock()
        cache_service.get.return_value = None  # No hay esquema en caché
        return cache_service
    
    @pytest.fixture
    def mock_database_service(self):
        """Database service mock"""
        return Mock()
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        factory = Mock()
        factory.get_detailed_schema_cache_service = Mock(return_value=Mock())
        return factory
    
    @pytest.fixture
    def schema_explorer(self, mock_cache_service, mock_database_service, mock_factory):
        """Instancia de SchemaExplorerService para testing"""
        return SchemaExplorerService(mock_cache_service, mock_database_service, mock_factory)
    
    def test_generate_direct_cache_response_with_missing_schema(self, schema_explorer):
        """🔧 FASE 3: Test que verifica el mensaje útil cuando no hay esquema"""
        # Simular que no hay esquema en caché
        schema_explorer._get_schema_from_cache = Mock(return_value=None)
        
        # Llamar a la función
        result = schema_explorer._generate_direct_cache_response([uuid4()], "list_tables")
        
        # Verificar que se devuelve el mensaje de esquema faltante
        assert result["type"] == "missing_schema_response"
        assert result["status"] == "missing_schema"
        assert result["response_type"] == "missing_schema"
        assert "⚠️ No tengo acceso al esquema de tu base de datos" in result["content"]
        assert "¿Quieres cargarlo primero?" in result["content"]
        assert "Recargar esquema de la base de datos" in result["content"]
        assert "Seleccionar una base de datos específica" in result["content"]
        assert "Probar con una tabla específica" in result["content"]
        
        # Verificar metadata
        assert result["metadata"]["requires_schema_load"] is True
        assert result["metadata"]["cache_hit"] is False
        assert result["metadata"]["total_tables"] == 0
        assert result["metadata"]["source"] == "missing_schema"
        
        print("✅ _generate_direct_cache_response devuelve mensaje útil cuando no hay esquema")
    
    def test_generate_direct_cache_response_with_available_schema(self, schema_explorer):
        """🔧 FASE 3: Test que verifica que funciona correctamente cuando hay esquema"""
        # Simular esquema disponible en caché
        mock_schema = {
            'tables': [
                {'name': 'users', 'columns': [{'name': 'id'}, {'name': 'name'}]},
                {'name': 'orders', 'columns': [{'name': 'id'}, {'name': 'user_id'}]}
            ]
        }
        schema_explorer._get_schema_from_cache = Mock(return_value=mock_schema)
        
        # Llamar a la función
        result = schema_explorer._generate_direct_cache_response([uuid4()], "list_tables")
        
        # Verificar que se genera la respuesta normal
        assert result["type"] == "direct_cache_response"
        assert result["response_type"] == "list_tables"
        assert "users" in result["content"]
        assert "orders" in result["content"]
        assert result["metadata"]["total_tables"] == 2
        assert result["metadata"]["cache_hit"] is True
        
        print("✅ _generate_direct_cache_response funciona correctamente cuando hay esquema disponible")
    
    def test_missing_schema_message_content(self, schema_explorer):
        """🔧 FASE 3: Test que verifica el contenido específico del mensaje de esquema faltante"""
        # Simular que no hay esquema en caché
        schema_explorer._get_schema_from_cache = Mock(return_value=None)
        
        # Llamar a la función
        result = schema_explorer._generate_direct_cache_response([uuid4()], "list_tables")
        
        # Verificar contenido específico del mensaje
        content = result["content"]
        
        # Verificar que contiene el emoji de advertencia
        assert "⚠️" in content
        
        # Verificar que contiene la pregunta principal
        assert "¿Quieres cargarlo primero?" in content
        
        # Verificar que contiene las opciones disponibles
        assert "**Opciones disponibles:**" in content
        assert "• Recargar esquema de la base de datos" in content
        assert "• Seleccionar una base de datos específica" in content
        assert "• Probar con una tabla específica" in content
        
        print("✅ Mensaje de esquema faltante contiene contenido útil y opciones claras")
    
    def test_missing_schema_response_structure(self, schema_explorer):
        """🔧 FASE 3: Test que verifica la estructura completa de la respuesta de esquema faltante"""
        # Simular que no hay esquema en caché
        schema_explorer._get_schema_from_cache = Mock(return_value=None)
        
        # Llamar a la función
        result = schema_explorer._generate_direct_cache_response([uuid4()], "list_tables")
        
        # Verificar estructura completa
        required_fields = [
            "type", "response_type", "content", "metadata", 
            "safe", "source", "status"
        ]
        
        for field in required_fields:
            assert field in result, f"Campo requerido '{field}' no encontrado en la respuesta"
        
        # Verificar estructura de metadata
        required_metadata_fields = [
            "total_tables", "source", "response_time_ms", 
            "no_llm_required", "cache_hit", "requires_schema_load"
        ]
        
        for field in required_metadata_fields:
            assert field in result["metadata"], f"Campo de metadata requerido '{field}' no encontrado"
        
        print("✅ Respuesta de esquema faltante tiene estructura completa y válida")
    
    def test_missing_schema_response_consistency(self, schema_explorer):
        """🔧 FASE 3: Test que verifica consistencia en diferentes tipos de respuesta"""
        # Simular que no hay esquema en caché
        schema_explorer._get_schema_from_cache = Mock(return_value=None)
        
        # Probar con diferentes tipos de respuesta
        response_types = ["list_tables", "explore_schema", "table_stats"]
        
        for response_type in response_types:
            result = schema_explorer._generate_direct_cache_response([uuid4()], response_type)
            
            # Verificar que todas las respuestas tienen la misma estructura cuando no hay esquema
            assert result["type"] == "missing_schema_response"
            assert result["status"] == "missing_schema"
            assert result["metadata"]["requires_schema_load"] is True
            assert result["metadata"]["cache_hit"] is False
            
            print(f"✅ Respuesta para '{response_type}' es consistente cuando no hay esquema")
    
    def test_missing_schema_performance(self, schema_explorer):
        """🔧 FASE 3: Test de rendimiento de la respuesta de esquema faltante"""
        import time
        
        # Simular que no hay esquema en caché
        schema_explorer._get_schema_from_cache = Mock(return_value=None)
        
        # Medir tiempo de ejecución
        start_time = time.time()
        for _ in range(100):
            schema_explorer._generate_direct_cache_response([uuid4()], "list_tables")
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"✅ 100 respuestas de esquema faltante generadas en {execution_time:.4f} segundos")
        
        # Verificar que es razonablemente rápido (< 1 segundo para 100 respuestas)
        assert execution_time < 1.0, f"Generación de respuestas demasiado lenta: {execution_time:.4f}s"


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
