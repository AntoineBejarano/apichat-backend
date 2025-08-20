#!/usr/bin/env python3
"""
🔧 Script de prueba para la integración del sistema de sinónimos
─────────────────────────────────────────────────────────────────
Prueba que el SynonymsConfigService y SchemaExplorerService funcionen correctamente juntos.
"""

import sys
import os
from pathlib import Path

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_synonyms_service():
    """Prueba el servicio de sinónimos"""
    print("🧪 Probando SynonymsConfigService...")
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        # Inicializar servicio
        service = SynonymsConfigService()
        
        # Obtener estadísticas
        stats = service.get_config_stats()
        print(f"  ✅ Estadísticas del servicio: {stats}")
        
        # Probar sinónimos de campos
        email_synonyms = service.get_field_synonyms("email")
        print(f"  ✅ Sinónimos de 'email': {email_synonyms}")
        
        # Probar sinónimos de tablas
        users_synonyms = service.get_table_synonyms("users")
        print(f"  ✅ Sinónimos de 'users': {users_synonyms}")
        
        # Probar traducciones
        translation = service.get_translation("tabla", "es", "en")
        print(f"  ✅ Traducción 'tabla' → 'table': {translation}")
        
        # Probar sinónimos de dominio
        ecommerce_synonyms = service.get_domain_synonyms("products", "ecommerce")
        print(f"  ✅ Sinónimos de 'products' en ecommerce: {ecommerce_synonyms}")
        
        # Probar todos los sinónimos para un término
        all_synonyms = service.get_all_synonyms_for_term("correo")
        print(f"  ✅ Todos los sinónimos de 'correo': {all_synonyms}")
        
        print("  🎉 SynonymsConfigService funciona correctamente!")
        return True
        
    except Exception as e:
        print(f"  ❌ Error en SynonymsConfigService: {e}")
        return False

def test_schema_explorer_integration():
    """Prueba la integración con SchemaExplorerService"""
    print("\n🧪 Probando integración con SchemaExplorerService...")
    
    try:
        from app.services.context.schema_explorer_service import SchemaExplorerService
        from app.services.data.cache_service import CacheService
        from app.services.data.database_service import DatabaseService
        
        # Crear servicios mock simples para evitar dependencias complejas
        class MockCacheService:
            def __init__(self):
                pass
        
        class MockDatabaseService:
            def __init__(self):
                pass
        
        # Inicializar SchemaExplorerService con mocks
        explorer = SchemaExplorerService(MockCacheService(), MockDatabaseService())
        
        # Probar que el servicio de sinónimos está disponible
        if hasattr(explorer, 'synonyms_service'):
            print("  ✅ SynonymsConfigService integrado correctamente")
            
            # Probar algunas funciones que usan sinónimos
            synonyms = explorer._get_synonyms("email")
            print(f"  ✅ Sinónimos obtenidos desde explorer: {synonyms}")
            
            related = explorer._get_related_terms("table", "table")
            print(f"  ✅ Términos relacionados obtenidos: {related}")
            
            print("  🎉 Integración funciona correctamente!")
            return True
        else:
            print("  ❌ SynonymsConfigService no está integrado")
            return False
            
    except Exception as e:
        print(f"  ❌ Error en integración: {e}")
        return False

def test_config_files():
    """Prueba que los archivos de configuración estén disponibles"""
    print("\n🧪 Probando archivos de configuración...")
    
    config_dir = Path("config")
    required_files = [
        "synonyms.json",
        "translations.json", 
        "domain_synonyms.json",
        "synonyms_config.json"
    ]
    
    all_files_exist = True
    for file_name in required_files:
        file_path = config_dir / file_name
        if file_path.exists():
            print(f"  ✅ {file_name} encontrado")
        else:
            print(f"  ❌ {file_name} NO encontrado")
            all_files_exist = False
    
    if all_files_exist:
        print("  🎉 Todos los archivos de configuración están disponibles!")
        return True
    else:
        print("  ❌ Faltan algunos archivos de configuración")
        return False

def test_synonyms_loading():
    """Prueba que los sinónimos se cargan correctamente"""
    print("\n🧪 Probando carga de sinónimos...")
    
    try:
        from app.services.context.synonyms_config_service import SynonymsConfigService
        
        service = SynonymsConfigService()
        
        # Probar que se cargaron configuraciones
        if service.config_cache:
            print(f"  ✅ Configuraciones cargadas: {list(service.config_cache.keys())}")
            
            # Verificar contenido de sinónimos
            synonyms_data = service.config_cache.get("synonyms.json", {})
            if synonyms_data:
                field_count = len(synonyms_data.get("field_synonyms", {}))
                table_count = len(synonyms_data.get("table_synonyms", {}))
                print(f"  ✅ Sinónimos de campos: {field_count}")
                print(f"  ✅ Sinónimos de tablas: {table_count}")
            
            # Verificar traducciones
            translations_data = service.config_cache.get("translations.json", {})
            if translations_data:
                es_to_en_count = len(translations_data.get("es_to_en", {}))
                en_to_es_count = len(translations_data.get("en_to_es", {}))
                print(f"  ✅ Traducciones ES→EN: {es_to_en_count}")
                print(f"  ✅ Traducciones EN→ES: {en_to_es_count}")
            
            # Verificar dominios
            domains_data = service.config_cache.get("domain_synonyms.json", {})
            if domains_data:
                domain_count = len(domains_data)
                print(f"  ✅ Dominios disponibles: {domain_count}")
            
            print("  🎉 Carga de sinónimos exitosa!")
            return True
        else:
            print("  ❌ No se cargaron configuraciones")
            return False
            
    except Exception as e:
        print(f"  ❌ Error cargando sinónimos: {e}")
        return False

def main():
    """Función principal del script"""
    print("🔧 Probando integración del sistema de sinónimos...")
    print("=" * 60)
    
    tests = [
        ("Archivos de configuración", test_config_files),
        ("Servicio de sinónimos", test_synonyms_service),
        ("Carga de sinónimos", test_synonyms_loading),
        ("Integración con SchemaExplorer", test_schema_explorer_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"  ❌ {test_name} falló")
    
    print("\n" + "=" * 60)
    print(f"📊 Resultados: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! El sistema está listo para usar.")
        return 0
    else:
        print("❌ Algunas pruebas fallaron. Revisar errores antes de usar.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
