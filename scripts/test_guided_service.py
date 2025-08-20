#!/usr/bin/env python3
"""
🧪 Script de prueba para GuidedService
────────────────────────────────────────
Verifica que GuidedService funcione correctamente y no devuelva mensajes de stub temporal.
"""
import sys
import asyncio
from pathlib import Path
from uuid import uuid4

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.execution.guided_service import GuidedService
from app.core.service_factory import ServiceFactory

class MockDatabase:
    def __init__(self):
        pass
    
    def add(self, *args, **kwargs):
        pass
    
    def commit(self):
        pass
    
    def rollback(self):
        pass
    
    def refresh(self, *args, **kwargs):
        pass
    
    def query(self, *args, **kwargs):
        return self
    
    def filter(self, *args, **kwargs):
        return self
    
    def first(self):
        return None

class MockRequest:
    def __init__(self):
        pass

async def test_guided_service():
    """Prueba que GuidedService funcione correctamente."""
    
    print("🧪 Probando GuidedService")
    print("=" * 50)
    
    try:
        # Crear mocks
        mock_db = MockDatabase()
        mock_request = MockRequest()
        
        # Crear factory
        factory = ServiceFactory(db=mock_db, request=mock_request)
        
        # Crear GuidedService
        guided_service = GuidedService(factory)
        
        print("✅ GuidedService creado correctamente")
        
        # Probar método de estado
        status = await guided_service.get_guided_graph_status()
        print(f"📊 Estado del servicio: {status}")
        
        # Verificar que no sea un stub
        if status.get("implementation") == "real":
            print("✅ ✅ Implementación REAL detectada")
        else:
            print("❌ ❌ Implementación STUB detectada")
        
        # Probar ejecución de grafo guiado
        chat_id = uuid4()
        user_message = "¿qué tablas hay en mi base de datos?"
        context = {
            "db_ids": [uuid4()],
            "app_ids": [uuid4()]
        }
        
        print(f"\n🚀 Probando ejecución de grafo guiado...")
        print(f"   Chat ID: {chat_id}")
        print(f"   Mensaje: {user_message}")
        
        result = await guided_service.run_guided_graph(chat_id, user_message, context)
        
        print(f"\n📋 Resultado:")
        print(f"   Status: {result.get('status')}")
        print(f"   Fallback: {result.get('fallback')}")
        print(f"   Message: {result.get('message')}")
        
        # Verificar que no sea fallback
        if result.get("fallback") == False:
            print("✅ ✅ NO es fallback - Implementación REAL")
        else:
            print("❌ ❌ ES fallback - Implementación STUB")
        
        # Verificar que no contenga el mensaje de stub temporal
        if "stub temporal" in str(result).lower():
            print("❌ ❌ Contiene mensaje de STUB TEMPORAL")
        else:
            print("✅ ✅ NO contiene mensaje de stub temporal")
        
        print("\n" + "=" * 50)
        print("🎯 RESULTADO FINAL:")
        
        if (status.get("implementation") == "real" and 
            result.get("fallback") == False and 
            "stub temporal" not in str(result).lower()):
            print("🎉 ¡GuidedService funcionando correctamente!")
            print("   ✅ Implementación REAL")
            print("   ✅ NO es fallback")
            print("   ✅ NO contiene mensajes de stub")
        else:
            print("❌ GuidedService aún tiene problemas")
            print("   ⚠️ Revisar implementación")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_guided_service())
