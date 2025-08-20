#!/usr/bin/env python3
"""
🧪 Script de prueba para Detección de Intenciones Múltiples
────────────────────────────────────────────────────────────
Demuestra el problema actual: el sistema solo detecta UNA intención
cuando la consulta contiene MÚLTIPLES intenciones.
"""
import sys
import asyncio
from pathlib import Path
from uuid import uuid4

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.context.schema_explorer_service import SchemaExplorerService
from app.services.context.synonyms_config_service import SynonymsConfigService

class MockCacheService:
    def get(self, key):
        return None
    def set(self, key, value, ttl=None):
        pass

class MockDatabaseService:
    def get_record(self, *args, **kwargs):
        return None

def test_multi_intention_detection():
    """Prueba la detección de intenciones múltiples."""
    
    print("🧪 Probando Detección de Intenciones Múltiples")
    print("=" * 70)
    
    try:
        # Inicializar servicio con mocks
        cache_service = MockCacheService()
        database_service = MockDatabaseService()
        service = SchemaExplorerService(cache_service=cache_service, database_service=database_service)
        
        # 🧪 CONSULTA COMPLEJA: Múltiples intenciones
        complex_query = "Hola, sabes que tablas tiene mi db y donde puedo ver la invitaciones de clubs que solucita la gente?"
        
        print(f"🔍 CONSULTA COMPLEJA:")
        print(f"   '{complex_query}'")
        print()
        
        # Extraer términos de búsqueda
        query_terms = service._extract_search_terms(complex_query)
        print(f"🔤 Términos extraídos: {query_terms}")
        print()
        
        # 🧠 ANÁLISIS MANUAL DE INTENCIONES
        print("🧠 ANÁLISIS MANUAL DE INTENCIONES:")
        
        # Intención 1: "qué tablas tiene mi db"
        print("   1️⃣ 'qué tablas tiene mi db'")
        print("      → Palabras clave: 'tablas', 'db'")
        print("      → Intención esperada: list_tables")
        print("      → Contexto: Explorar esquema general")
        print()
        
        # Intención 2: "dónde puedo ver las invitaciones de clubs"
        print("   2️⃣ 'dónde puedo ver las invitaciones de clubs'")
        print("      → Palabras clave: 'dónde', 'ver', 'invitaciones', 'clubs'")
        print("      → Intención esperada: find_specific_tables")
        print("      → Contexto: Búsqueda específica de contenido")
        print()
        
        # 🎯 DETECCIÓN ACTUAL DEL SISTEMA
        print("🎯 DETECCIÓN ACTUAL DEL SISTEMA:")
        detected_intention = service._detect_user_intention(complex_query, query_terms)
        print(f"   Intención detectada: {detected_intention}")
        print()
        
        # 📊 ANÁLISIS DEL PROBLEMA
        print("📊 ANÁLISIS DEL PROBLEMA:")
        
        if detected_intention == "list_tables":
            print("   ✅ Detectó 'list_tables' (primera intención)")
            print("   ❌ NO detectó 'find_specific_tables' (segunda intención)")
            print("   ⚠️  PROBLEMA: Solo una intención detectada")
        elif detected_intention == "find_specific_tables":
            print("   ✅ Detectó 'find_specific_tables' (segunda intención)")
            print("   ❌ NO detectó 'list_tables' (primera intención)")
            print("   ⚠️  PROBLEMA: Solo una intención detectada")
        else:
            print(f"   ⚠️  Detectó '{detected_intention}' (intención inesperada)")
            print("   ❌ PROBLEMA: No detectó ninguna de las intenciones esperadas")
        
        print()
        
        # 🔍 VERIFICAR POR QUÉ SE DETECTÓ ESA INTENCIÓN
        print("🔍 VERIFICAR DETECCIÓN:")
        query_lower = complex_query.lower()
        
        # Verificar indicadores de list_tables
        list_indicators = ['tabla', 'tablas', 'db', 'database']
        list_matches = [ind for ind in list_indicators if ind in query_lower]
        print(f"   Indicadores de 'list_tables': {list_matches}")
        
        # Verificar indicadores de find_specific_tables
        search_indicators = ['donde', 'dónde', 'ver', 'invitaciones', 'clubs']
        search_matches = [ind for ind in search_indicators if ind in query_lower]
        print(f"   Indicadores de 'find_specific_tables': {search_matches}")
        
        print()
        
        # 🚀 SOLUCIÓN PROPUESTA
        print("🚀 SOLUCIÓN PROPUESTA:")
        print("   Para manejar consultas multi-intención, necesitamos:")
        print("   1. 🔍 Detectar TODAS las intenciones presentes")
        print("   2. 🎯 Priorizar la más específica o compleja")
        print("   3. 📋 Generar plan que satisfaga ambas intenciones")
        print("   4. 🔄 Ejecutar pasos para cada intención")
        print()
        
        # 📝 EJEMPLO DE PLAN MULTI-INTENCIÓN
        print("📝 EJEMPLO DE PLAN MULTI-INTENCIÓN:")
        print("   PASO 1: Listar todas las tablas disponibles")
        print("   PASO 2: Buscar tablas relacionadas con 'invitaciones' y 'clubs'")
        print("   PASO 3: Mostrar esquema de tablas relevantes")
        print("   PASO 4: Generar respuesta que satisfaga ambas consultas")
        print()
        
        # 🎯 RESULTADO ESPERADO
        print("🎯 RESULTADO ESPERADO:")
        print("   El usuario debería recibir:")
        print("   • 📋 Lista completa de tablas de la base de datos")
        print("   • 🔍 Ubicación específica de tablas de invitaciones de clubs")
        print("   • 📊 Información sobre cómo acceder a esos datos")
        
        print("\n" + "=" * 70)
        print("📋 RESUMEN:")
        print(f"   Consulta: {complex_query[:50]}...")
        print(f"   Intenciones esperadas: 2 (list_tables + find_specific_tables)")
        print(f"   Intenciones detectadas: 1 ({detected_intention})")
        print(f"   Estado: ❌ PROBLEMA IDENTIFICADO")
        print("   Solución: Implementar detección de intenciones múltiples")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_multi_intention_detection()
