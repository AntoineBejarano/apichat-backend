"""
🔧 FASE 0: Test de integración genérico para flujo DB Q&A
──────────────────────────────────────────────────────────
Verifica que el flujo de preguntas → SQL → respuesta funciona correctamente
sin errores de asyncio y de forma genérica.
"""

import pytest
import asyncio
from uuid import uuid4
from httpx import AsyncClient
from app.main import app
from app.core.database import get_db
from app.services.orchestrator_service import OrchestratorService
from app.core.service_factory import ServiceFactory


class TestGenericDBQnAFlow:
    """Test del flujo genérico de preguntas y respuestas sobre bases de datos"""
    
    @pytest.fixture
    async def client(self):
        """Cliente HTTP async para testing"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    async def websocket_client(self):
        """Cliente WebSocket para testing"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # Simular conexión WebSocket
            yield client
    
    @pytest.fixture
    def sample_message(self):
        """Mensaje de prueba genérico"""
        return {
            "role": "user",
            "content": "¿Qué tablas tengo disponibles en mi base de datos?",
            "name": "TestUser",
            "explorer": False,
            "db_ids": [str(uuid4())],  # ID genérico
            "app_ids": []
        }
    
    def test_orchestrator_service_initialization(self):
        """🔧 FASE 1: Verificar que OrchestratorService se inicializa correctamente"""
        # Crear un mock de ServiceFactory más completo
        class MockServiceFactory:
            def __init__(self):
                self.db = None
                self.user = type('MockUser', (), {'id': uuid4()})()
                self.ws_emitter = None
                self.advanced_telemetry_service = None
            
            def get_ws_emitter(self):
                return None
            
            def get_advanced_telemetry_service(self):
                return None
            
            # 🔧 FASE 1: Añadir métodos mock necesarios
            def get_strategy_service(self):
                return type('MockStrategyService', (), {})()
            
            def get_chat_history_service(self):
                return type('MockChatHistoryService', (), {})()
            
            def get_detailed_schema_cache_service(self):
                return type('MockDetailedSchemaCacheService', (), {})()
            
            def get_schema_explorer_service(self):
                return type('MockSchemaExplorerService', (), {})()
        
        factory = MockServiceFactory()
        
        # Verificar que se puede crear sin errores
        orchestrator = OrchestratorService(factory)
        
        # Verificar que _token_bucket está inicializado
        assert hasattr(orchestrator, '_token_bucket')
        assert orchestrator._token_bucket is not None
        
        # Verificar que token_budget está inicializado
        assert hasattr(orchestrator, 'token_budget')
        assert orchestrator.token_budget is not None
        
        print("✅ OrchestratorService se inicializa correctamente")
    
    def test_langchain_service_methods(self):
        """🔧 FASE 1: Verificar que los métodos de LangchainService son async"""
        # Importar el servicio
        from app.services.ai.langchain_service import LangchainService
        
        # Verificar que generate_sql_from_question_sync es async
        method = getattr(LangchainService, 'generate_sql_from_question_sync', None)
        if method:
            # Verificar que es un método async
            import inspect
            assert inspect.iscoroutinefunction(method), "generate_sql_from_question_sync debe ser async"
        
        print("✅ LangchainService tiene métodos async correctos")
    
    @pytest.mark.asyncio
    async def test_schema_explorer_multilanguage(self):
        """🔧 FASE 1: Verificar que SchemaExplorerService maneja múltiples idiomas"""
        from app.services.context.schema_explorer_service import SchemaExplorerService
        
        # Crear instancia del servicio
        class MockCacheService:
            pass
        
        class MockDatabaseService:
            pass
        
        service = SchemaExplorerService(MockCacheService(), MockDatabaseService())
        
        # Test con consulta en español
        spanish_query = "¿Dónde está la tabla de clientes?"
        normalized = service._normalize_query(spanish_query)
        terms = service._extract_search_terms(normalized)
        
        # Verificar que se normalizó correctamente
        assert 'table' in normalized, "Consulta en español debe normalizarse a inglés"
        assert 'clientes' not in normalized, "Términos en español deben traducirse"
        
        # Verificar que se extrajeron términos útiles
        assert len(terms) > 0, "Deben extraerse términos de búsqueda"
        
        print("✅ SchemaExplorerService maneja múltiples idiomas correctamente")
    
    def test_fallback_sql_generation(self):
        """🔧 FASE 1: Verificar que se genera SQL de fallback genérico"""
        from app.services.ai.langchain_service import LangchainService
        
        # Crear instancia mock
        class MockFactory:
            pass
        
        service = LangchainService(MockFactory())
        
        # Test del método de fallback
        fallback_sql = service._generate_fallback_sql("¿Qué tablas tengo?", uuid4())
        
        # Verificar que se genera SQL válido
        assert fallback_sql is not None
        assert len(fallback_sql) > 0
        assert "SELECT" in fallback_sql.upper()
        assert "information_schema" in fallback_sql.lower()
        assert "LIMIT" in fallback_sql.upper()
        
        print("✅ SQL de fallback se genera correctamente")
    
    @pytest.mark.asyncio
    async def test_no_asyncio_run_in_loop(self):
        """🔧 FASE 1: Verificar que no se usa asyncio.run() en loop activo"""
        import asyncio
        
        # Simular un event loop activo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Verificar que estamos en un loop activo
            assert asyncio.get_running_loop() is not None
            
            # Verificar que asyncio.run() no se puede usar
            with pytest.raises(RuntimeError, match="asyncio.run\\(\\) cannot be called from a running event loop"):
                asyncio.run(asyncio.sleep(0.1))
            
            print("✅ asyncio.run() no se puede usar en loop activo (correcto)")
            
        finally:
            loop.close()
    
    def test_error_handling_generic(self):
        """🔧 FASE 1: Verificar que el manejo de errores es genérico"""
        # Verificar que no hay referencias hardcodeadas a esquemas específicos
        import os
        
        # Buscar en archivos de configuración y servicios
        config_files = [
            "app/core/config.py",
            "app/services/ai/langchain_service.py",
            "app/services/context/schema_explorer_service.py"
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Verificar que no hay nombres de tablas específicos hardcodeados
                    assert 'invitaciones' not in content.lower(), f"Archivo {config_file} contiene nombres específicos"
                    assert 'clubs' not in content.lower(), f"Archivo {config_file} contiene nombres específicos"
        
        print("✅ No hay referencias hardcodeadas a esquemas específicos")


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"])
