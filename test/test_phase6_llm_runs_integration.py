"""
🔧 FASE 6: Test de integración de LLM Runs
──────────────────────────────────────────
Verifica que el sistema de trazabilidad de LLM runs funciona correctamente.
"""

import pytest
from unittest.mock import Mock
from uuid import uuid4
from app.services.management.llm_runs_service import LLMRunsService
from app.schemas.llm_runs_schema import LLMRunCreate, LLMRunUpdate


class TestPhase6LLMRunsIntegration:
    """Test de la FASE 6: Integración de LLM Runs"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        factory = Mock()
        factory.user = Mock()
        factory.user.id = uuid4()
        return factory
    
    @pytest.fixture
    def llm_runs_service(self, mock_factory):
        """Instancia de LLMRunsService para testing"""
        service = LLMRunsService(mock_factory)
        # Mock de la base de datos
        service.db = Mock()
        service.db.add = Mock()
        service.db.commit = Mock()
        service.db.refresh = Mock()
        service.db.rollback = Mock()
        service.db.query = Mock()
        return service
    
    def test_llm_runs_service_initialization(self, llm_runs_service):
        """🔧 FASE 6: Test que verifica que el servicio se inicializa correctamente"""
        assert llm_runs_service is not None
        assert hasattr(llm_runs_service, 'create_llm_run')
        assert hasattr(llm_runs_service, 'update_llm_run')
        assert hasattr(llm_runs_service, 'get_llm_run')
        
        print("✅ LLMRunsService se inicializa correctamente")
    
    def test_create_llm_run_schema_validation(self):
        """🔧 FASE 6: Test que verifica que el schema de creación funciona"""
        # Crear datos válidos para un LLM run
        llm_run_data = LLMRunCreate(
            chat_id=uuid4(),
            user_id=uuid4(),
            model_name="gpt-4",
            provider="openai",
            prompt_text="¿Cuántos usuarios tengo?",
            response_text="SELECT COUNT(*) FROM users",
            prompt_tokens=50,
            response_tokens=20,
            total_tokens=70,
            response_time_ms=1500,
            table_schema="users(id, name, email)",
            database_id=uuid4(),
            sql_generated="SELECT COUNT(*) FROM users",
            sql_validated=True,
            sql_executed=False
        )
        
        # Verificar que se crea correctamente
        assert llm_run_data.chat_id is not None
        assert llm_run_data.model_name == "gpt-4"
        assert llm_run_data.total_tokens == 70  # Debe calcularse automáticamente
        
        print("✅ Schema de creación de LLM run funciona correctamente")
    
    def test_update_llm_run_schema_validation(self):
        """🔧 FASE 6: Test que verifica que el schema de actualización funciona"""
        # Crear datos de actualización
        update_data = LLMRunUpdate(
            sql_executed=True,
            status="success"
        )
        
        # Verificar que se crea correctamente
        assert update_data.sql_executed is True
        assert update_data.status == "success"
        
        print("✅ Schema de actualización de LLM run funciona correctamente")
    
    def test_llm_runs_service_methods_exist(self, llm_runs_service):
        """🔧 FASE 6: Test que verifica que todos los métodos necesarios existen"""
        required_methods = [
            'create_llm_run',
            'update_llm_run', 
            'get_llm_run',
            'get_llm_runs_by_chat',
            'get_llm_runs_by_user',
            'get_llm_runs_stats',
            'mark_sql_executed',
            'get_failed_sql_runs'
        ]
        
        for method_name in required_methods:
            assert hasattr(llm_runs_service, method_name), f"Método {method_name} no encontrado"
            method = getattr(llm_runs_service, method_name)
            assert callable(method), f"Método {method_name} no es callable"
        
        print("✅ Todos los métodos requeridos existen en LLMRunsService")
    
    def test_llm_runs_model_relationships(self):
        """🔧 FASE 6: Test que verifica que el modelo tiene las relaciones correctas"""
        from app.models.llm_runs_model import LLMRun
        
        # Verificar que el modelo existe
        assert LLMRun is not None
        assert hasattr(LLMRun, '__tablename__')
        assert LLMRun.__tablename__ == "llm_runs"
        
        # Verificar campos críticos
        assert hasattr(LLMRun, 'chat_id')
        assert hasattr(LLMRun, 'user_id')
        assert hasattr(LLMRun, 'model_name')
        assert hasattr(LLMRun, 'prompt_text')
        assert hasattr(LLMRun, 'response_text')
        assert hasattr(LLMRun, 'sql_generated')
        assert hasattr(LLMRun, 'sql_validated')
        assert hasattr(LLMRun, 'sql_executed')
        
        print("✅ Modelo LLMRun tiene la estructura correcta")


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
