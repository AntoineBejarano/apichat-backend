#!/usr/bin/env python3
"""
🛡️ Script de prueba para Guard Clauses
────────────────────────────────────────
Verifica que las guard clauses impidan que aparezca el stub temporal
cuando hay bases de datos presentes o planes ejecutados.
"""
import sys
import asyncio
from pathlib import Path
from uuid import uuid4

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.orchestrator_service import OrchestratorService
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

def test_guard_clauses():
    """Prueba que las guard clauses funcionen correctamente."""
    
    print("🛡️ Probando Guard Clauses")
    print("=" * 60)
    
    try:
        # Crear mocks
        mock_db = MockDatabase()
        mock_request = MockRequest()
        
        # Crear factory y orchestrator
        factory = ServiceFactory(db=mock_db, request=mock_request)
        orchestrator = OrchestratorService(factory)
        
        print("✅ OrchestratorService creado correctamente")
        
        # 🧪 PRUEBA 1: Plan ejecutado con variables
        print("\n🧪 PRUEBA 1: Plan ejecutado con variables")
        execution_results_with_plan = {
            "plan": {"id": "test-plan", "name": "Test Plan"},
            "variables": {
                "query_result": "Resultado real del plan ejecutado",
                "answer": "Respuesta del plan"
            },
            "assistant_response": "Este es un stub temporal. La funcionalidad completa estará disponible próximamente."
        }
        
        response1 = orchestrator._extract_assistant_response(execution_results_with_plan)
        print(f"   Respuesta: {response1}")
        
        if "stub temporal" in response1.lower():
            print("   ❌ FALLO: Devolvió stub temporal con plan ejecutado")
        else:
            print("   ✅ ÉXITO: Priorizó plan real sobre stub")
        
        # 🧪 PRUEBA 2: Bases de datos presentes
        print("\n🧪 PRUEBA 2: Bases de datos presentes")
        execution_results_with_db = {
            "db_ids": [uuid4()],
            "assistant_response": "Este es un stub temporal. La funcionalidad completa estará disponible próximamente."
        }
        
        response2 = orchestrator._extract_assistant_response(execution_results_with_db)
        print(f"   Respuesta: {response2}")
        
        if "stub temporal" in response2.lower():
            print("   ❌ FALLO: Devolvió stub temporal con DB presente")
        else:
            print("   ✅ ÉXITO: Evitó stub temporal con DB presente")
        
        # 🧪 PRUEBA 3: Variables con bases de datos
        print("\n🧪 PRUEBA 3: Variables con bases de datos")
        execution_results_vars_db = {
            "databases": [{"id": str(uuid4()), "name": "test_db"}],
            "variables": {
                "query_result": "Este es un stub temporal. No usar.",
                "answer": "Respuesta real de la base de datos"
            }
        }
        
        response3 = orchestrator._extract_assistant_response(execution_results_vars_db)
        print(f"   Respuesta: {response3}")
        
        if "stub temporal" in response3.lower():
            print("   ❌ FALLO: Devolvió variable con stub temporal")
        else:
            print("   ✅ ÉXITO: Evitó variable con stub temporal")
        
        # 🧪 PRUEBA 4: Sin bases de datos (stub permitido)
        print("\n🧪 PRUEBA 4: Sin bases de datos (fallback normal)")
        execution_results_no_db = {
            "assistant_response": "Este es un stub temporal. La funcionalidad completa estará disponible próximamente."
        }
        
        response4 = orchestrator._extract_assistant_response(execution_results_no_db)
        print(f"   Respuesta: {response4}")
        
        if "stub temporal" in response4.lower():
            print("   ✅ ESPERADO: Stub temporal permitido sin DB")
        else:
            print("   ⚠️  INESPERADO: No devolvió stub cuando debería (sin DB)")
        
        # 🧪 PRUEBA 5: Error con bases de datos
        print("\n🧪 PRUEBA 5: Error con bases de datos")
        execution_results_error_db = {
            "db_ids": [uuid4()],
            "error": "Error de prueba",
            "assistant_response": None
        }
        
        response5 = orchestrator._extract_assistant_response(execution_results_error_db)
        print(f"   Respuesta: {response5}")
        
        if "stub temporal" in response5.lower():
            print("   ❌ FALLO: Devolvió stub temporal en error con DB")
        elif "error" in response5.lower() or "procesando" in response5.lower():
            print("   ✅ ÉXITO: Generó respuesta específica de error")
        else:
            print("   ⚠️  PARCIAL: Respuesta no contiene stub pero tampoco indica error")
        
        # 📊 RESUMEN
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE PRUEBAS:")
        
        tests_passed = 0
        total_tests = 5
        
        if "stub temporal" not in response1.lower():
            tests_passed += 1
            print("   ✅ Plan ejecutado: PASS")
        else:
            print("   ❌ Plan ejecutado: FAIL")
        
        if "stub temporal" not in response2.lower():
            tests_passed += 1
            print("   ✅ DB presente: PASS")
        else:
            print("   ❌ DB presente: FAIL")
        
        if "stub temporal" not in response3.lower():
            tests_passed += 1
            print("   ✅ Variables con DB: PASS")
        else:
            print("   ❌ Variables con DB: FAIL")
        
        # Para la prueba 4, esperamos que SÍ devuelva stub (sin DB)
        if "stub temporal" in response4.lower():
            tests_passed += 1
            print("   ✅ Sin DB (stub permitido): PASS")
        else:
            print("   ❌ Sin DB (stub permitido): FAIL")
        
        if "stub temporal" not in response5.lower():
            tests_passed += 1
            print("   ✅ Error con DB: PASS")
        else:
            print("   ❌ Error con DB: FAIL")
        
        print(f"\n🎯 RESULTADO FINAL: {tests_passed}/{total_tests} pruebas pasaron")
        
        if tests_passed == total_tests:
            print("🎉 ¡Todas las guard clauses funcionan correctamente!")
        elif tests_passed >= 3:
            print("⚠️ La mayoría de guard clauses funcionan, revisar fallos")
        else:
            print("❌ Las guard clauses necesitan más trabajo")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_guard_clauses()
