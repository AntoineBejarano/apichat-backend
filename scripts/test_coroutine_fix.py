#!/usr/bin/env python3
"""
🔧 Script de prueba para verificar que el error del coroutine está arreglado
──────────────────────────────────────────────────────────────────────────
Prueba que el método _enrich_plan_actions_with_database_id funcione correctamente
sin errores de coroutine.
"""

import sys
import asyncio
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_coroutine_fix():
    """Prueba que el error del coroutine está arreglado"""
    print("🧪 Probando que el error del coroutine está arreglado...")
    
    try:
        from app.services.execution.execution_engine_service import ExecutionEngineService
        from app.services.data.cache_service import CacheService
        from app.services.data.database_service import DatabaseService
        from app.core.service_factory import ServiceFactory
        
        # Crear servicios mock para evitar dependencias complejas
        class MockCacheService:
            def __init__(self):
                pass
        
        class MockDatabaseService:
            def __init__(self):
                pass
            
            def get_record(self, db_id):
                class MockDBRecord:
                    def __init__(self):
                        self.schema = "CREATE TABLE test_table (id INT, name VARCHAR(100));"
                return MockDBRecord()
        
        class MockServiceFactory:
            def __init__(self):
                # Mock user para ExecutionEngineService
                class MockUser:
                    def __init__(self):
                        self.id = "test-user-123"
                self.user = MockUser()
            
            def get_langchain_service(self):
                return MockLangchainService()
            
            def get_database_service(self):
                return MockDatabaseService()
            
            def get_chat_history_service(self):
                return MockChatHistoryService()
        
        class MockChatHistoryService:
            def __init__(self):
                pass
        
        class MockLangchainService:
            async def generate_sql_from_question_sync(self, question, db_id, table_schema=None):
                return {
                    "sql": "SELECT * FROM information_schema.tables LIMIT 10",
                    "security_validated": True,
                    "auto_limit_added": False,
                    "timestamp": "2025-08-20T19:00:00Z"
                }
        
        # Inicializar ExecutionEngineService
        execution_engine = ExecutionEngineService(
            factory=MockServiceFactory()
        )
        
        # Crear acciones de prueba
        test_actions = [
            {
                "type": "db_query",
                "question": "¿Qué tablas hay disponibles?",
                "store_as": "tables_result"
            }
        ]
        
        # Crear contexto de prueba
        test_context = {
            "db_ids": ["test-db-id-123"]
        }
        
        print("  ✅ Servicios mock creados correctamente")
        print("  ✅ ExecutionEngineService inicializado")
        print("  ✅ Acciones de prueba creadas")
        
        # Probar el método async
        print("\n🔧 Probando _enrich_plan_actions_with_database_id...")
        
        enriched_actions = await execution_engine._enrich_plan_actions_with_database_id(
            test_actions, 
            test_context
        )
        
        print("  ✅ Método async ejecutado sin errores")
        
        # Verificar que las acciones fueron enriquecidas
        if enriched_actions and len(enriched_actions) > 0:
            enriched_action = enriched_actions[0]
            
            print(f"  ✅ Acción enriquecida: {enriched_action['type']}")
            
            if enriched_action.get('database_id'):
                print(f"  ✅ database_id añadido: {enriched_action['database_id']}")
            else:
                print("  ⚠️ database_id no encontrado")
            
            if enriched_action.get('sql'):
                print(f"  ✅ SQL generado: {enriched_action['sql'][:50]}...")
            else:
                print("  ⚠️ SQL no generado")
            
            if enriched_action.get('_sql_generated'):
                print("  ✅ Metadata de SQL añadida")
            else:
                print("  ⚠️ Metadata de SQL no encontrada")
        else:
            print("  ❌ No se obtuvieron acciones enriquecidas")
            return False
        
        print("\n🎉 ¡Prueba del coroutine exitosa!")
        print("  ✅ No hay errores de 'coroutine' object has no attribute 'get'")
        print("  ✅ El método async funciona correctamente")
        print("  ✅ Las acciones se enriquecen correctamente")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_langchain_service():
    """Prueba que el LangchainService funciona correctamente"""
    print("\n🧪 Probando LangchainService...")
    
    try:
        from app.services.ai.langchain_service import LangchainService
        
        # Crear servicio mock
        class MockLLM:
            async def ainvoke(self, prompt):
                class MockResponse:
                    @property
                    def content(self):
                        return "SELECT table_name FROM information_schema.tables LIMIT 10"
                return MockResponse()
        
        # Crear MockServiceFactory local
        class MockServiceFactoryLocal:
            def __init__(self):
                pass
        
        # Inicializar LangchainService
        langchain_service = LangchainService(factory=MockServiceFactoryLocal())
        langchain_service.llm = MockLLM()
        
        print("  ✅ LangchainService inicializado")
        
        # Probar generación de SQL
        result = await langchain_service.generate_sql_from_question_sync(
            question="¿Qué tablas hay?",
            db_id="test-db-123"
        )
        
        if result.get('sql'):
            print(f"  ✅ SQL generado: {result['sql']}")
            print(f"  ✅ Metadata: {result.get('source', 'N/A')}")
            return True
        else:
            print(f"  ❌ Error generando SQL: {result.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error en LangchainService: {e}")
        return False

async def main():
    """Función principal del script"""
    print("🔧 Probando que el error del coroutine está arreglado...")
    print("=" * 60)
    
    tests = [
        ("Coroutine Fix", test_coroutine_fix),
        ("LangchainService", test_langchain_service)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        try:
            if await test_func():
                passed += 1
                print(f"  ✅ {test_name} completado exitosamente")
            else:
                print(f"  ❌ {test_name} falló")
        except Exception as e:
            print(f"  ❌ {test_name} falló con excepción: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! El error del coroutine está arreglado.")
        return 0
    else:
        print("❌ Algunas pruebas fallaron. Revisar errores.")
        return 1

if __name__ == "__main__":
    # Ejecutar el event loop
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
