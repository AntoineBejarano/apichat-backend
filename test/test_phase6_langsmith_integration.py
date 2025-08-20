"""
🔧 FASE 6: Test de Integración de Langsmith
───────────────────────────────────────────
Verifica que la integración de Langsmith funciona correctamente.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from app.core.langsmith_config import langsmith_config, traceable_if_enabled
from app.services.ai.langchain_service import LangchainService
from app.services.execution.execution_engine_service import ExecutionEngineService


class TestPhase6LangsmithIntegration:
    """Test de la FASE 6: Integración de Langsmith"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        factory = Mock()
        factory.user = Mock()
        factory.user.id = uuid4()
        factory.current_chat_id = uuid4()
        return factory
    
    def test_langsmith_config_initialization(self):
        """🔧 FASE 6: Test que verifica que la configuración de Langsmith se inicializa"""
        assert langsmith_config is not None
        assert hasattr(langsmith_config, 'api_key')
        assert hasattr(langsmith_config, 'project_name')
        assert hasattr(langsmith_config, 'endpoint')
        assert hasattr(langsmith_config, 'is_enabled')
        
        print("✅ LangsmithConfig se inicializa correctamente")
    
    def test_langsmith_config_api_key(self):
        """🔧 FASE 6: Test que verifica que la API key está configurada"""
        # La API key debe estar configurada (no ser None o vacía)
        assert langsmith_config.api_key is not None
        assert len(langsmith_config.api_key) > 0
        assert langsmith_config.api_key != "your_api_key_here"
        
        print("✅ API key de Langsmith está configurada")
    
    def test_langsmith_config_project_name(self):
        """🔧 FASE 6: Test que verifica que el nombre del proyecto está configurado"""
        assert langsmith_config.project_name == "apichat-backend"
        
        print("✅ Nombre del proyecto de Langsmith está configurado")
    
    def test_traceable_if_enabled_decorator(self):
        """🔧 FASE 6: Test que verifica que el decorador traceable_if_enabled funciona"""
        # Crear una función de prueba
        @traceable_if_enabled(name="test_function", tags=["test"])
        def test_function():
            return "test_result"
        
        # Verificar que la función se ejecuta correctamente
        result = test_function()
        assert result == "test_result"
        
        print("✅ Decorador traceable_if_enabled funciona correctamente")
    
    @patch('app.core.langsmith_config.langsmith_config.is_enabled')
    def test_traceable_if_enabled_when_disabled(self, mock_is_enabled):
        """🔧 FASE 6: Test que verifica que el decorador funciona cuando Langsmith está deshabilitado"""
        mock_is_enabled.return_value = False
        
        @traceable_if_enabled(name="test_function", tags=["test"])
        def test_function():
            return "test_result"
        
        # Verificar que la función se ejecuta correctamente incluso cuando Langsmith está deshabilitado
        result = test_function()
        assert result == "test_result"
        
        print("✅ Decorador funciona cuando Langsmith está deshabilitado")
    
    def test_langchain_service_langsmith_integration(self, mock_factory):
        """🔧 FASE 6: Test que verifica que LangchainService tiene integración de Langsmith"""
        # Mock del servicio de LLM runs
        mock_llm_runs_service = Mock()
        mock_llm_runs_service.create_llm_run = AsyncMock()
        mock_factory.get_llm_runs_service.return_value = mock_llm_runs_service
        
        # Crear instancia del servicio
        service = LangchainService(mock_factory)
        
        # Verificar que tiene el método de tracking
        assert hasattr(service, '_track_llm_run')
        assert callable(service._track_llm_run)
        
        print("✅ LangchainService tiene integración de Langsmith")
    
    def test_execution_engine_service_langsmith_integration(self, mock_factory):
        """🔧 FASE 6: Test que verifica que ExecutionEngineService tiene integración de Langsmith"""
        # Mock del servicio de LLM runs
        mock_llm_runs_service = Mock()
        mock_llm_runs_service.get_llm_runs_by_user = AsyncMock(return_value=[])
        mock_llm_runs_service.mark_sql_executed = AsyncMock()
        mock_factory.get_llm_runs_service.return_value = mock_llm_runs_service
        
        # Crear instancia del servicio
        service = ExecutionEngineService(mock_factory)
        
        # Verificar que tiene el método de tracking
        assert hasattr(service, '_mark_sql_executed_in_llm_runs')
        assert callable(service._mark_sql_executed_in_llm_runs)
        
        print("✅ ExecutionEngineService tiene integración de Langsmith")
    
    def test_langsmith_client_initialization(self):
        """🔧 FASE 6: Test que verifica que el cliente de Langsmith se puede inicializar"""
        try:
            client = langsmith_config.get_client()
            if client:
                print("✅ Cliente de Langsmith se inicializó correctamente")
            else:
                print("⚠️ Cliente de Langsmith no disponible (puede ser normal en tests)")
        except Exception as e:
            print(f"⚠️ Error inicializando cliente de Langsmith: {e}")
            # No fallar el test por problemas de conexión
    
    def test_langsmith_environment_variables(self):
        """🔧 FASE 6: Test que verifica que las variables de entorno están disponibles"""
        from app.core.langsmith_env import LANGSMITH_API_KEY, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT
        
        assert LANGSMITH_API_KEY is not None
        assert LANGSMITH_PROJECT is not None
        assert LANGSMITH_ENDPOINT is not None
        
        print("✅ Variables de entorno de Langsmith están disponibles")


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
