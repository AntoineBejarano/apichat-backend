"""
🧪 Tests para la Fase 9: Sistema Provider-agnóstico
────────────────────────────────────────────────────
Valida la implementación completa del sistema provider-agnóstico:
- Cache Adapter (Redis/Upstash)
- LLM Adapter (OpenAI/Claude/Gemini/Cohere)
- Adapter Factory
- Configuración por ENV
- Health checks y métricas
"""

import os
import sys
import json
import time
from unittest.mock import patch, MagicMock

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_cache_adapter():
    """Test del Cache Adapter"""
    print("🧪 Test 1: Cache Adapter")
    print("=" * 50)
    
    try:
        from app.core.adapters import CacheAdapter, AdapterConfig, AdapterType
        
        # Test 1.1: Configuración por defecto (Redis)
        print("  📋 Test 1.1: Configuración por defecto")
        cache_adapter = CacheAdapter()
        assert cache_adapter.config.provider == "redis", "Provider por defecto debe ser redis"
        assert cache_adapter.config.url == "redis://localhost:6379/0", "URL por defecto incorrecta"
        print("    ✅ Configuración por defecto correcta")
        
        # Test 1.2: Configuración personalizada
        print("  📋 Test 1.2: Configuración personalizada")
        config = AdapterConfig(
            provider="redis",
            url="redis://test:6379/0",
            timeout=15,
            max_retries=5,
            batch_size=200
        )
        custom_cache = CacheAdapter(config)
        assert custom_cache.config.url == "redis://test:6379/0", "URL personalizada no aplicada"
        assert custom_cache.config.timeout == 15, "Timeout personalizado no aplicado"
        print("    ✅ Configuración personalizada correcta")
        
        # Test 1.3: Métodos básicos (mock)
        print("  📋 Test 1.3: Métodos básicos")
        with patch.object(custom_cache.provider, 'set') as mock_set:
            mock_set.return_value = True
            result = custom_cache.set("test_key", "test_value", ttl=60)
            assert result == True, "Set debe retornar True"
        
        with patch.object(custom_cache.provider, 'get') as mock_get:
            mock_get.return_value = "test_value"
            result = custom_cache.get("test_key")
            assert result == "test_value", "Get debe retornar el valor correcto"
        
        print("    ✅ Métodos básicos funcionando")
        
        # Test 1.4: Métodos batch
        print("  📋 Test 1.4: Métodos batch")
        test_data = {"key1": "value1", "key2": "value2"}
        with patch.object(custom_cache.provider, 'set') as mock_set:
            mock_set.return_value = True
            results = custom_cache.set_many(test_data, ttl=60)
            assert len(results) == 2, "set_many debe retornar resultados para todas las claves"
        
        print("    ✅ Métodos batch funcionando")
        
        print("  ✅ Cache Adapter: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"  ❌ Cache Adapter FAILED: {e}")
        return False


def test_llm_adapter():
    """Test del LLM Adapter"""
    print("\n🧪 Test 2: LLM Adapter")
    print("=" * 50)
    
    try:
        from app.core.adapters import LLMAdapter, LLMRequest, LLMResponse, AdapterConfig
        
        # Test 2.1: Configuración por defecto (OpenAI)
        print("  📋 Test 2.1: Configuración por defecto")
        # Mock para evitar errores de API key
        with patch.dict(os.environ, {"LLM_API_KEY": "test_key"}):
            llm_adapter = LLMAdapter()
            assert llm_adapter.config.provider == "openai", "Provider por defecto debe ser openai"
            assert llm_adapter.config.timeout == 60, "Timeout por defecto incorrecto"
            print("    ✅ Configuración por defecto correcta")
        
        # Test 2.2: Configuración personalizada
        print("  📋 Test 2.2: Configuración personalizada")
        config = AdapterConfig(
            provider="openai",
            api_key="test_key",
            timeout=120,
            max_retries=5,
            batch_size=1
        )
        custom_llm = LLMAdapter(config)
        assert custom_llm.config.provider == "openai", "Provider personalizado no aplicado"
        assert custom_llm.config.timeout == 120, "Timeout personalizado no aplicado"
        print("    ✅ Configuración personalizada correcta")
        
        # Test 2.3: LLMRequest y LLMResponse
        print("  📋 Test 2.3: LLMRequest y LLMResponse")
        request = LLMRequest(
            messages=[
                {"role": "system", "content": "Eres un asistente útil"},
                {"role": "user", "content": "Hola, ¿cómo estás?"}
            ],
            model="gpt-4",
            temperature=0.7,
            max_tokens=100
        )
        
        assert len(request.messages) == 2, "LLMRequest debe tener 2 mensajes"
        assert request.model == "gpt-4", "Modelo debe ser gpt-4"
        assert request.temperature == 0.7, "Temperature debe ser 0.7"
        
        response = LLMResponse(
            content="¡Hola! Estoy muy bien, gracias por preguntar.",
            model="gpt-4",
            usage={"input_tokens": 20, "output_tokens": 15},
            finish_reason="stop"
        )
        
        assert "gracias" in response.content, "Respuesta debe contener 'gracias'"
        assert response.model == "gpt-4", "Modelo de respuesta debe ser gpt-4"
        print("    ✅ LLMRequest y LLMResponse funcionando")
        
        # Test 2.4: Métodos del adapter (mock)
        print("  📋 Test 2.4: Métodos del adapter")
        with patch.object(custom_llm.provider, 'get_models') as mock_models:
            mock_models.return_value = ["claude-3-sonnet", "claude-3-haiku"]
            models = custom_llm.get_models()
            assert len(models) == 2, "get_models debe retornar 2 modelos"
        
        with patch.object(custom_llm.provider, 'health_check') as mock_health:
            mock_health.return_value = True
            health = custom_llm.health_check()
            assert health == True, "health_check debe retornar True"
        
        print("    ✅ Métodos del adapter funcionando")
        
        print("  ✅ LLM Adapter: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"  ❌ LLM Adapter FAILED: {e}")
        return False


def test_adapter_factory():
    """Test del Adapter Factory"""
    print("\n🧪 Test 3: Adapter Factory")
    print("=" * 50)
    
    try:
        from app.core.adapters import AdapterFactory, adapter_factory, AdapterType
        
        # Test 3.1: Instancia global
        print("  📋 Test 3.1: Instancia global")
        assert adapter_factory is not None, "adapter_factory debe existir"
        assert isinstance(adapter_factory, AdapterFactory), "adapter_factory debe ser AdapterFactory"
        print("    ✅ Instancia global correcta")
        
        # Test 3.2: Configuraciones cargadas
        print("  📋 Test 3.2: Configuraciones cargadas")
        assert len(adapter_factory._configs) == 4, "Debe haber 4 configuraciones"
        assert AdapterType.EMBEDDING in adapter_factory._configs, "Configuración de embedding faltante"
        assert AdapterType.VECTOR_STORE in adapter_factory._configs, "Configuración de vector store faltante"
        assert AdapterType.CACHE in adapter_factory._configs, "Configuración de cache faltante"
        assert AdapterType.LLM in adapter_factory._configs, "Configuración de LLM faltante"
        print("    ✅ Configuraciones cargadas correctamente")
        
        # Test 3.3: Métodos de obtención de adapters
        print("  📋 Test 3.3: Métodos de obtención")
        # Mock para evitar errores de conexión real
        with patch('app.core.adapters.embedding_adapter.EmbeddingAdapter.__init__') as mock_init:
            mock_init.return_value = None
            embedding_adapter = adapter_factory.get_embedding_adapter()
            assert embedding_adapter is not None, "get_embedding_adapter debe retornar un adapter"
        
        with patch('app.core.adapters.cache_adapter.CacheAdapter.__init__') as mock_init:
            mock_init.return_value = None
            cache_adapter = adapter_factory.get_cache_adapter()
            assert cache_adapter is not None, "get_cache_adapter debe retornar un adapter"
        
        print("    ✅ Métodos de obtención funcionando")
        
        # Test 3.4: Información del factory
        print("  📋 Test 3.4: Información del factory")
        summary = adapter_factory.get_factory_summary()
        assert summary["factory_type"] == "AdapterFactory", "Tipo de factory incorrecto"
        assert summary["total_adapters"] == 4, "Total de adapters incorrecto"
        assert "embedding" in summary["adapter_info"], "Info de embedding faltante"
        assert "cache" in summary["adapter_info"], "Info de cache faltante"
        print("    ✅ Información del factory correcta")
        
        print("  ✅ Adapter Factory: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"  ❌ Adapter Factory FAILED: {e}")
        return False


def test_environment_configuration():
    """Test de configuración por variables de entorno"""
    print("\n🧪 Test 4: Configuración por ENV")
    print("=" * 50)
    
    try:
        # Test 4.1: Variables de entorno para cache
        print("  📋 Test 4.1: Variables de entorno para cache")
        test_env = {
            "CACHE_PROVIDER": "redis",
            "CACHE_URL": "redis://test:6379/0",
            "CACHE_API_KEY": "test_key",
            "CACHE_TIMEOUT": "20",
            "CACHE_MAX_RETRIES": "5"
        }
        
        with patch.dict(os.environ, test_env):
            from app.core.adapters import CacheAdapter
            cache_adapter = CacheAdapter()
            assert cache_adapter.config.provider == "redis", "Provider debe ser redis"
            assert cache_adapter.config.url == "redis://test:6379/0", "URL debe ser la configurada"
            assert cache_adapter.config.timeout == 20, "Timeout debe ser 20"
            assert cache_adapter.config.max_retries == 5, "Max retries debe ser 5"
        
        print("    ✅ Variables de entorno para cache funcionando")
        
        # Test 4.2: Variables de entorno para LLM
        print("  📋 Test 4.2: Variables de entorno para LLM")
        test_env_llm = {
            "LLM_PROVIDER": "openai",
            "LLM_API_KEY": "test_llm_key",
            "LLM_TIMEOUT": "90",
            "LLM_MAX_RETRIES": "4"
        }
        
        with patch.dict(os.environ, test_env_llm):
            from app.core.adapters import LLMAdapter
            llm_adapter = LLMAdapter()
            assert llm_adapter.config.provider == "openai", "Provider debe ser openai"
            assert llm_adapter.config.timeout == 90, "Timeout debe ser 90"
            assert llm_adapter.config.max_retries == 4, "Max retries debe ser 4"
        
        print("    ✅ Variables de entorno para LLM funcionando")
        
        print("  ✅ Configuración por ENV: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"  ❌ Configuración por ENV FAILED: {e}")
        return False


def test_integration():
    """Test de integración completa"""
    print("\n🧪 Test 5: Integración Completa")
    print("=" * 50)
    
    try:
        from app.core.adapters import adapter_factory, LLMRequest
        
        # Test 5.1: Crear todos los adapters
        print("  📋 Test 5.1: Crear todos los adapters")
        
        # Mock para evitar errores de conexión real
        with patch('app.core.adapters.embedding_adapter.EmbeddingAdapter.__init__') as mock_emb:
            mock_emb.return_value = None
            embedding = adapter_factory.get_embedding_adapter()
            assert embedding is not None, "Embedding adapter debe crearse"
        
        with patch('app.core.adapters.vector_store_adapter.VectorStoreAdapter.__init__') as mock_vec:
            mock_vec.return_value = None
            vector = adapter_factory.get_vector_store_adapter()
            assert vector is not None, "Vector store adapter debe crearse"
        
        with patch('app.core.adapters.cache_adapter.CacheAdapter.__init__') as mock_cache:
            mock_cache.return_value = None
            cache = adapter_factory.get_cache_adapter()
            assert cache is not None, "Cache adapter debe crearse"
        
        with patch('app.core.adapters.llm_adapter.LLMAdapter.__init__') as mock_llm:
            mock_llm.return_value = None
            llm = adapter_factory.get_llm_adapter()
            assert llm is not None, "LLM adapter debe crearse"
        
        print("    ✅ Todos los adapters creados correctamente")
        
        # Test 5.2: Health check de todos los adapters
        print("  📋 Test 5.2: Health check completo")
        health_status = adapter_factory.health_check_all()
        assert len(health_status) == 4, "Debe haber 4 health checks"
        assert "embedding" in health_status, "Health check de embedding faltante"
        assert "vector_store" in health_status, "Health check de vector store faltante"
        assert "cache" in health_status, "Health check de cache faltante"
        assert "llm" in health_status, "Health check de LLM faltante"
        print("    ✅ Health checks completos")
        
        # Test 5.3: Métricas agregadas
        print("  📋 Test 5.3: Métricas agregadas")
        metrics = adapter_factory.get_all_metrics()
        assert len(metrics) == 4, "Debe haber métricas de 4 adapters"
        print("    ✅ Métricas agregadas correctas")
        
        # Test 5.4: Información completa del factory
        print("  📋 Test 5.4: Información completa")
        summary = adapter_factory.get_factory_summary()
        assert summary["initialized_adapters"] == 4, "Debe haber 4 adapters inicializados"
        assert summary["total_adapters"] == 4, "Total de adapters debe ser 4"
        print("    ✅ Información completa correcta")
        
        print("  ✅ Integración Completa: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"  ❌ Integración Completa FAILED: {e}")
        return False


def main():
    """Función principal de testing"""
    print("🚀 INICIANDO TESTS DE LA FASE 9: SISTEMA PROVIDER-AGNÓSTICO")
    print("=" * 80)
    
    tests = [
        ("Cache Adapter", test_cache_adapter),
        ("LLM Adapter", test_llm_adapter),
        ("Adapter Factory", test_adapter_factory),
        ("Configuración por ENV", test_environment_configuration),
        ("Integración Completa", test_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🎯 Ejecutando: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASÓ")
            else:
                print(f"❌ {test_name}: FALLÓ")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 80)
    print(f"📊 RESUMEN DE TESTS: {passed}/{total} PASARON")
    
    if passed == total:
        print("🎉 ¡TODOS LOS TESTS DE LA FASE 9 PASARON!")
        print("✅ Sistema Provider-agnóstico implementado correctamente")
    else:
        print(f"⚠️  {total - passed} tests fallaron")
        print("🔧 Revisar implementación antes de continuar")
    
    return passed == total


if __name__ == "__main__":
    main()
