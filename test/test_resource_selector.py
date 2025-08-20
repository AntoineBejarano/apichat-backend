#!/usr/bin/env python3
"""
Script de prueba para ResourceSelectorService.
Verifica que la selección automática de recursos funciona correctamente.
"""

import asyncio
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.execution.resource_selector_service import ResourceSelectorService


async def test_resource_selector():
    """Prueba básica del ResourceSelectorService."""
    print("🧪 Probando ResourceSelectorService...")
    
    # Crear instancia del servicio
    selector = ResourceSelectorService()
    
    # Datos de prueba
    test_prompt = "Necesito analizar las ventas del último mes y crear un reporte"
    
    test_dbs = [
        {
            "id": "db1",
            "name": "sales_database",
            "description": "Base de datos de ventas y transacciones",
            "table_count": 25,
            "last_updated": "2024-01-15T10:00:00Z",
            "size_mb": 500,
            "is_readonly": False,
            "has_comments": True,
            "has_constraints": True,
            "has_indexes": True
        },
        {
            "id": "db2", 
            "name": "analytics_db",
            "description": "Base de datos de análisis y métricas",
            "table_count": 15,
            "last_updated": "2024-01-10T08:00:00Z",
            "size_mb": 300,
            "is_readonly": True,
            "has_comments": False,
            "has_constraints": True,
            "has_indexes": False
        }
    ]
    
    test_apps = [
        {
            "id": "app1",
            "name": "sales_reporter",
            "description": "Aplicación para generar reportes de ventas",
            "api_count": 30,
            "last_updated": "2024-01-12T14:00:00Z",
            "rate_limit": 5000,
            "requires_auth": True,
            "has_rate_limiting": True,
            "has_openapi_spec": True,
            "has_examples": True,
            "has_descriptions": True
        },
        {
            "id": "app2",
            "name": "data_visualizer",
            "description": "Aplicación para visualización de datos",
            "api_count": 20,
            "last_updated": "2024-01-08T16:00:00Z",
            "rate_limit": 3000,
            "requires_auth": True,
            "has_rate_limiting": True,
            "has_openapi_spec": True,
            "has_examples": False,
            "has_descriptions": True
        }
    ]
    
    try:
        # Ejecutar selección
        print(f"📝 Prompt: '{test_prompt}'")
        print(f"🗄️  DBs candidatas: {len(test_dbs)}")
        print(f"📱 Apps candidatas: {len(test_apps)}")
        print()
        
        result = await selector.select_for_guided(test_prompt, test_dbs, test_apps)
        
        # Mostrar resultados
        print("🎯 RESULTADO DE SELECCIÓN:")
        print(f"  🗄️  DB seleccionada: {result.database.resource_name}")
        print(f"     Score: {result.database.score:.2f}")
        print(f"     Razones: {', '.join(result.database.reasons)}")
        print()
        
        print(f"  📱 App seleccionada: {result.application.resource_name}")
        print(f"     Score: {result.application.score:.2f}")
        print(f"     Razones: {', '.join(result.application.reasons)}")
        print()
        
        print(f"  🎯 Score combinado: {result.combined_score:.2f}")
        print(f"  🎯 Confianza: {result.confidence:.2f}")
        print(f"  📋 Razones de selección: {', '.join(result.selection_reasons)}")
        
        print("\n✅ Prueba completada exitosamente!")
        return True
        
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Iniciando prueba de ResourceSelectorService...")
    print("=" * 60)
    
    success = asyncio.run(test_resource_selector())
    
    print("=" * 60)
    if success:
        print("🎉 ¡Todas las pruebas pasaron!")
        sys.exit(0)
    else:
        print("💥 Algunas pruebas fallaron")
        sys.exit(1)
