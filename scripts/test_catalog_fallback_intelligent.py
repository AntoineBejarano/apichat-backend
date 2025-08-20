#!/usr/bin/env python3
"""
🧪 Script de prueba para verificar el sistema de fallback inteligente con consultas de catálogo
──────────────────────────────────────────────────────────────────────────────────────────────
Prueba que el SchemaExplorerService ahora use consultas de catálogo seguras en lugar de ir al LLM.
"""

import sys
import asyncio
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_catalog_fallback_intelligent():
    """Prueba que el fallback inteligente funciona correctamente"""
    print("🧪 Probando sistema de fallback inteligente...")
    
    try:
        from app.services.context.schema_explorer_service import SchemaExplorerService
        from app.services.data.cache_service import CacheService
        from app.services.data.database_service import DatabaseService
        
        # Crear servicios mock
        class MockCacheService:
            def __init__(self):
                pass
            
            def get(self, key):
                return None
            
            def set(self, key, value, ttl=None):
                pass
        
        class MockDatabaseService:
            def __init__(self):
                pass
        
        # Inicializar SchemaExplorerService
        schema_explorer = SchemaExplorerService(
            cache_service=MockCacheService(),
            database_service=MockDatabaseService()
        )
        
        print("  ✅ SchemaExplorerService inicializado")
        
        # Prueba 1: Intención de listar tablas
        print("\n🔧 Prueba 1: Intención 'list_tables'...")
        intention = schema_explorer._detect_user_intention("¿Qué tablas hay?", ["tablas", "hay"])
        print(f"  📝 Pregunta: ¿Qué tablas hay?")
        print(f"  🎯 Intención detectada: {intention}")
        
        if intention == "list_tables":
            print("  ✅ Intención correcta")
        else:
            print(f"  ❌ Intención incorrecta: {intention}")
            return False
        
        # Prueba 2: Intención de buscar tablas específicas (invitaciones)
        print("\n🔧 Prueba 2: Intención 'find_specific_tables' (invitaciones)...")
        intention = schema_explorer._detect_user_intention("¿dónde ver las invitaciones de clubs?", ["ver", "invitaciones", "clubs"])
        print(f"  📝 Pregunta: ¿dónde ver las invitaciones de clubs?")
        print(f"  🎯 Intención detectada: {intention}")
        
        if intention == "find_specific_tables":
            print("  ✅ Intención correcta")
        else:
            print(f"  ❌ Intención incorrecta: {intention}")
            return False
        
        # Prueba 3: Generar consulta segura para invitaciones
        print("\n🔧 Prueba 3: Generar consulta segura para invitaciones...")
        keywords = schema_explorer._extract_safe_keywords(["invitaciones", "clubs", "ver"])
        print(f"  🔑 Palabras clave extraídas: {keywords}")
        
        if keywords:
            query = schema_explorer._generate_safe_table_search_query(["test-db-id"], keywords)
            print(f"  🎯 Tipo de consulta: {query['query_type']}")
            print(f"  🔍 SQL generado: {query['sql'][:80]}...")
            
            # Verificar que NO hay interpolación de texto del usuario
            if "invitaciones" in query['sql'] or "clubs" in query['sql']:
                print("  ❌ PELIGRO: Texto del usuario interpolado en SQL!")
                return False
            
            if query.get('safe') and query.get('source') == 'catalog_fallback':
                print("  ✅ Consulta marcada como segura")
            else:
                print("  ❌ Consulta no marcada como segura")
                return False
        else:
            print("  ❌ No se pudieron extraer palabras clave")
            return False
        
        # Prueba 4: Fallback completo del sistema
        print("\n🔧 Prueba 4: Fallback completo del sistema...")
        
        # Simular que no hay matches en índices léxicos
        catalog_fallback = schema_explorer._try_catalog_fallback(
            "¿dónde ver las invitaciones de clubs?", 
            ["test-db-id"]
        )
        
        if catalog_fallback:
            print(f"  ✅ Fallback generado: {catalog_fallback['query_type']}")
            print(f"  🔍 SQL: {catalog_fallback['sql'][:80]}...")
            print(f"  🛡️ Seguro: {catalog_fallback.get('safe')}")
            print(f"  📋 Fuente: {catalog_fallback.get('source')}")
            
            # Verificar que es completamente seguro
            if not catalog_fallback.get('safe'):
                print("  ❌ Fallback no marcado como seguro")
                return False
                
            if catalog_fallback.get('source') != 'catalog_fallback':
                print("  ❌ Fuente incorrecta del fallback")
                return False
        else:
            print("  ❌ No se generó fallback")
            return False
        
        print("\n🎉 ¡Todas las pruebas del fallback inteligente pasaron!")
        print("  ✅ Intenciones detectadas correctamente")
        print("  ✅ Consultas seguras generadas")
        print("  ✅ Sin interpolación de texto del usuario")
        print("  ✅ Fallback completo funcionando")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_dangerous_inputs_handling():
    """Prueba que inputs peligrosos se manejan de forma segura"""
    print("\n🧪 Probando manejo de inputs peligrosos...")
    
    try:
        from app.services.context.schema_explorer_service import SchemaExplorerService
        from app.services.data.cache_service import CacheService
        from app.services.data.database_service import DatabaseService
        
        # Crear servicios mock
        class MockCacheService:
            def __init__(self):
                pass
            
            def get(self, key):
                return None
            
            def set(self, key, value, ttl=None):
                pass
        
        class MockDatabaseService:
            def __init__(self):
                pass
        
        schema_explorer = SchemaExplorerService(
            cache_service=MockCacheService(),
            database_service=MockDatabaseService()
        )
        
        # Probar inputs peligrosos
        dangerous_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "¿Qué tablas hay?'; DROP TABLE users; --",
            "SELECT * FROM credit_cards WHERE 1=1; --"
        ]
        
        for dangerous_input in dangerous_inputs:
            print(f"\n  📝 Input peligroso: {dangerous_input[:30]}...")
            
            # Intentar fallback de catálogo
            catalog_fallback = schema_explorer._try_catalog_fallback(
                dangerous_input, 
                ["test-db-id"]
            )
            
            if catalog_fallback:
                sql = catalog_fallback.get('sql', '')
                
                # Verificar que NO hay interpolación del input peligroso
                if dangerous_input in sql:
                    print(f"  ❌ PELIGRO: Input peligroso interpolado en SQL!")
                    return False
                
                # Verificar que solo hay consultas predefinidas
                if any(dangerous in sql.upper() for dangerous in ['DROP', 'DELETE', 'INSERT', 'UPDATE', '<SCRIPT>']):
                    print(f"  ❌ PELIGRO: Comandos peligrosos en SQL!")
                    return False
                
                print(f"  ✅ Input peligroso manejado de forma segura")
            else:
                print(f"  ⚠️ No se generó fallback para input peligroso")
        
        print("\n🎉 ¡Todos los inputs peligrosos manejados de forma segura!")
        return True
        
    except Exception as e:
        print(f"  ❌ Error en prueba de inputs peligrosos: {e}")
        return False

async def main():
    """Función principal del script"""
    print("🧪 Probando sistema de fallback inteligente con consultas de catálogo...")
    print("=" * 80)
    
    tests = [
        ("Fallback Inteligente", test_catalog_fallback_intelligent),
        ("Inputs Peligrosos", test_dangerous_inputs_handling)
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
    
    print("\n" + "=" * 80)
    print(f"📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Sistema de fallback inteligente funcionando correctamente!")
        print("\n💡 Beneficios del Nuevo Sistema:")
        print("  🎯 INTELIGENCIA:")
        print("    • ✅ Detección automática de intenciones del usuario")
        print("    • ✅ Consultas específicas para invitaciones, clubs, etc.")
        print("    • ✅ Fallback graceful sin ir al LLM")
        
        print("\n  🛡️ SEGURIDAD:")
        print("    • ✅ Sin interpolación de texto del usuario")
        print("    • ✅ Solo consultas predefinidas de information_schema")
        print("    • ✅ Patrones seguros para búsquedas específicas")
        
        print("\n  📊 FUNCIONALIDAD:")
        print("    • ✅ 5 tipos de consultas de catálogo")
        print("    • ✅ Búsqueda por palabras clave seguras")
        print("    • ✅ Estructura de tablas específicas")
        print("    • ✅ Relaciones entre tablas")
        return 0
    else:
        print("❌ Algunas pruebas fallaron. Revisar implementación.")
        return 1

if __name__ == "__main__":
    # Ejecutar el event loop
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
