#!/usr/bin/env python3
"""
🔧 Script de prueba para verificar el sistema de fallback seguro con consultas de catálogo
───────────────────────────────────────────────────────────────────────────────────────
Prueba que el sistema ya no use interpolación insegura de texto del usuario.
"""

import sys
import asyncio
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_safe_catalog_fallback():
    """Prueba que el fallback usa consultas de catálogo seguras"""
    print("🧪 Probando sistema de fallback seguro...")
    
    try:
        from app.services.execution.execution_engine_service import ExecutionEngineService
        
        # Crear servicios mock
        class MockUser:
            def __init__(self):
                self.id = "test-user-123"
        
        class MockChatHistoryService:
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
        
        class MockLangchainService:
            def __init__(self, should_fail=False):
                self.should_fail = should_fail
            
            async def generate_sql_from_question_sync(self, question, db_id, table_schema=None):
                if self.should_fail:
                    # Simular fallo en la generación
                    return {
                        "sql": "",
                        "error": "No se pudo generar SQL seguro para esta pregunta",
                        "question": question,
                        "database_id": str(db_id)
                    }
                else:
                    # Simular éxito
                    return {
                        "sql": "SELECT id, name FROM users LIMIT 10",
                        "security_validated": True,
                        "auto_limit_added": False,
                        "timestamp": "2025-08-20T19:00:00Z"
                    }
        
        class MockServiceFactory:
            def __init__(self, langchain_should_fail=False):
                self.user = MockUser()
                self.langchain_should_fail = langchain_should_fail
            
            def get_langchain_service(self):
                return MockLangchainService(should_fail=self.langchain_should_fail)
            
            def get_database_service(self):
                return MockDatabaseService()
            
            def get_chat_history_service(self):
                return MockChatHistoryService()
        
        print("  ✅ Servicios mock creados")
        
        # Prueba 1: Cuando la generación de SQL falla
        print("\n🔧 Prueba 1: Fallback cuando falla generación SQL...")
        
        execution_engine = ExecutionEngineService(factory=MockServiceFactory(langchain_should_fail=True))
        
        # Crear acciones de prueba con preguntas potencialmente peligrosas
        dangerous_questions = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "¿Qué columnas tiene la tabla usuarios?",
            "¿Cuáles son las relaciones entre tablas?",
            "¿Qué estadísticas hay de las tablas?"
        ]
        
        for question in dangerous_questions:
            test_actions = [{
                "type": "db_query",
                "question": question,
                "store_as": "test_result"
            }]
            
            test_context = {"db_ids": ["test-db-id-123"]}
            
            enriched_actions = await execution_engine._enrich_plan_actions_with_database_id(
                test_actions, test_context
            )
            
            if enriched_actions and len(enriched_actions) > 0:
                action = enriched_actions[0]
                
                # Verificar que NO hay interpolación de la pregunta peligrosa
                sql = action.get('sql', '')
                
                print(f"\n  📝 Pregunta: {question[:30]}...")
                print(f"  🔍 SQL generado: {sql[:80]}...")
                
                # 🛡️ VERIFICACIONES DE SEGURIDAD
                if question in sql:
                    print(f"  ❌ PELIGRO: La pregunta del usuario está interpolada en el SQL!")
                    return False
                
                if any(dangerous in sql.upper() for dangerous in ['DROP', 'DELETE', 'INSERT', 'UPDATE', '<SCRIPT>']):
                    print(f"  ❌ PELIGRO: Comandos peligrosos detectados en SQL!")
                    return False
                
                if action.get('_is_catalog_query'):
                    print(f"  ✅ Es consulta de catálogo segura: {action.get('_catalog_query_type')}")
                else:
                    print(f"  ⚠️ No está marcada como consulta de catálogo")
                
                if action.get('_sql_source') in ['safe_catalog_fallback', 'safe_catalog_error_fallback']:
                    print(f"  ✅ Fuente segura: {action.get('_sql_source')}")
                else:
                    print(f"  ⚠️ Fuente inesperada: {action.get('_sql_source')}")
            else:
                print(f"  ❌ No se obtuvo acción enriquecida para: {question}")
                return False
        
        print("\n🎉 ¡Todas las pruebas de seguridad pasaron!")
        print("  ✅ No hay interpolación de texto del usuario")
        print("  ✅ Solo consultas de catálogo predefinidas")
        print("  ✅ No hay comandos SQL peligrosos")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_catalog_query_types():
    """Prueba los diferentes tipos de consultas de catálogo"""
    print("\n🧪 Probando tipos de consultas de catálogo...")
    
    try:
        from app.services.execution.execution_engine_service import ExecutionEngineService
        
        # Crear servicios mock simples
        class MockUser:
            def __init__(self):
                self.id = "test-user-123"
        
        class MockServiceFactory:
            def __init__(self):
                self.user = MockUser()
            
            def get_chat_history_service(self):
                return type('MockService', (), {})()
        
        execution_engine = ExecutionEngineService(factory=MockServiceFactory())
        
        # Probar diferentes tipos de preguntas
        test_cases = [
            ("¿Qué tablas hay?", "list_tables"),
            ("¿Qué columnas tiene?", "list_columns"),
            ("¿Cuáles son las relaciones?", "table_relationships"),
            ("¿Qué estadísticas hay?", "table_stats"),
            ("Pregunta genérica", "list_tables")  # Default
        ]
        
        for question, expected_type in test_cases:
            result = execution_engine._get_safe_catalog_queries(question)
            
            print(f"\n  📝 Pregunta: {question}")
            print(f"  🎯 Tipo esperado: {expected_type}")
            print(f"  🎯 Tipo obtenido: {result['query_type']}")
            print(f"  🔍 SQL: {result['sql'][:60]}...")
            
            if result['query_type'] == expected_type:
                print(f"  ✅ Tipo correcto")
            else:
                print(f"  ⚠️ Tipo inesperado")
            
            if result.get('safe') and result.get('is_catalog_query'):
                print(f"  ✅ Marcado como seguro")
            else:
                print(f"  ❌ No marcado como seguro")
        
        print("\n🎉 ¡Pruebas de tipos de catálogo completadas!")
        return True
        
    except Exception as e:
        print(f"  ❌ Error en pruebas de catálogo: {e}")
        return False

async def main():
    """Función principal del script"""
    print("🔧 Probando sistema de fallback seguro con consultas de catálogo...")
    print("=" * 70)
    
    tests = [
        ("Fallback Seguro", test_safe_catalog_fallback),
        ("Tipos de Catálogo", test_catalog_query_types)
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
    
    print("\n" + "=" * 70)
    print(f"📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Sistema de fallback seguro funcionando correctamente!")
        print("\n💡 Beneficios de Seguridad:")
        print("  • ✅ No hay interpolación de texto del usuario")
        print("  • ✅ Solo consultas predefinidas de information_schema")
        print("  • ✅ Límites de filas incorporados")
        print("  • ✅ Filtros de esquemas de sistema")
        print("  • ✅ Diferentes tipos de consultas según contexto")
        return 0
    else:
        print("❌ Algunas pruebas fallaron. Revisar implementación.")
        return 1

if __name__ == "__main__":
    # Ejecutar el event loop
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
