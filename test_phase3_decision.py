#!/usr/bin/env python3
"""
Test básico para la Fase 3 - Confirmación amable en Guided.
"""

import asyncio
import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.orchestrator.decision_manager import DecisionManager


async def test_decision_manager():
    """Test básico del DecisionManager."""
    print("🧪 Probando DecisionManager...")
    
    # Crear instancia
    decision_manager = DecisionManager()
    
    # Test 1: Crear una decisión
    print("\n📝 Test 1: Crear decisión...")
    
    options = [
        {"id": "confirm", "label": "✅ Confirmar", "description": "Continuar con la operación"},
        {"id": "cancel", "label": "❌ Cancelar", "description": "Abortar la operación"}
    ]
    
    # Crear tarea de decisión
    decision_task = asyncio.create_task(
        decision_manager.request_decision(
            title="Test de confirmación",
            description="¿Deseas continuar con la operación?",
            options=options,
            timeout_seconds=5,
            default_action="cancel"
        )
    )
    
    # Simular respuesta del usuario después de 1 segundo
    await asyncio.sleep(1)
    
    # Simular respuesta de confirmación
    success = decision_manager.submit_decision_response(
        decision_id="test_id",  # Este ID no existe, debería fallar
        action="confirm"
    )
    
    print(f"   Respuesta simulada (ID inexistente): {success}")
    
    # Esperar a que termine la tarea (timeout)
    try:
        result = await asyncio.wait_for(decision_task, timeout=6)
        print(f"   Resultado de la decisión: {result}")
    except asyncio.TimeoutError:
        print("   ⏰ Timeout alcanzado")
    
    # Test 2: Verificar estado
    print(f"\n📊 Estado del DecisionManager:")
    print(f"   Decisiones pendientes: {decision_manager.get_pending_decisions_count()}")
    
    print("\n✅ Test del DecisionManager completado")


async def test_decision_with_valid_id():
    """Test con ID válido."""
    print("\n🧪 Test 2: Decisión con ID válido...")
    
    decision_manager = DecisionManager()
    
    # Crear tarea de decisión
    decision_task = asyncio.create_task(
        decision_manager.request_decision(
            title="Test con ID válido",
            description="Test de confirmación con ID válido",
            options=[{"id": "confirm", "label": "Confirmar"}],
            timeout_seconds=10,
            default_action="cancel"
        )
    )
    
    # Esperar un poco para que se cree la decisión
    await asyncio.sleep(0.1)
    
    # Obtener el primer ID pendiente
    pending_decisions = list(decision_manager.pending_decisions.keys())
    if pending_decisions:
        decision_id = pending_decisions[0]
        print(f"   ID de decisión creado: {decision_id}")
        
        # Simular respuesta inmediata
        success = decision_manager.submit_decision_response(
            decision_id=decision_id,
            action="confirm"
        )
        print(f"   Respuesta enviada: {success}")
        
        # Esperar resultado
        result = await decision_task
        print(f"   Resultado: {result}")
    else:
        print("   ❌ No se crearon decisiones pendientes")
    
    print("✅ Test con ID válido completado")


async def main():
    """Función principal de test."""
    print("🚀 Iniciando tests de la Fase 3 - Confirmación amable en Guided")
    print("=" * 60)
    
    try:
        await test_decision_manager()
        await test_decision_with_valid_id()
        
        print("\n" + "=" * 60)
        print("🎉 Todos los tests completados exitosamente!")
        
    except Exception as e:
        print(f"\n❌ Error en los tests: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
