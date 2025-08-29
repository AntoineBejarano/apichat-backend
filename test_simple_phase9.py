"""
🧪 Test Simple para la Fase 9
─────────────────────────────
Verifica que los módulos se importan correctamente
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test de importaciones básicas"""
    print("🧪 Test de Importaciones - Fase 9")
    print("=" * 50)
    
    try:
        # Test 1: Base Adapter
        print("📋 Test 1: Base Adapter")
        from app.core.adapters.base_adapter import BaseAdapter, AdapterType, AdapterConfig
        print("    ✅ Base Adapter importado")
        
        # Test 2: Cache Adapter
        print("📋 Test 2: Cache Adapter")
        from app.core.adapters.cache_adapter import CacheAdapter
        print("    ✅ Cache Adapter importado")
        
        # Test 3: LLM Adapter
        print("📋 Test 3: LLM Adapter")
        from app.core.adapters.llm_adapter import LLMAdapter, LLMRequest, LLMResponse
        print("    ✅ LLM Adapter importado")
        
        # Test 4: Adapter Factory
        print("📋 Test 4: Adapter Factory")
        from app.core.adapters.adapter_factory import AdapterFactory
        print("    ✅ Adapter Factory importado")
        
        # Test 5: Módulo completo
        print("📋 Test 5: Módulo completo")
        from app.core.adapters import adapter_factory
        print("    ✅ Módulo completo importado")
        
        print("\n🎉 TODAS LAS IMPORTACIONES FUNCIONARON")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR EN IMPORTACIÓN: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_imports()
