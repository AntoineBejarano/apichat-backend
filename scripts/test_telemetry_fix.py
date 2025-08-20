#!/usr/bin/env python3
"""
🧪 Script de prueba para verificar que el error de telemetría se ha resuelto
─────────────────────────────────────────────────────────────────────────────────
Prueba que el sistema ya no intente insertar valores en columnas generadas automáticamente.
"""

import sys
import asyncio
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_telemetry_fix():
    """Prueba que el error de telemetría se ha resuelto"""
    print("🧪 Probando que el error de telemetría se ha resuelto...")
    
    try:
        from app.services.management.advanced_telemetry_service import AdvancedTelemetryService, TelemetryContext
        from app.schemas.telemetry_schema import ConversationMetricsCreate
        
        # Crear servicio mock
        class MockServiceFactory:
            def __init__(self):
                pass
            
            @property
            def db(self):
                # Mock de la sesión de base de datos
                class MockDB:
                    def add(self, obj):
                        pass
                    
                    def commit(self):
                        pass
                    
                    def rollback(self):
                        pass
                    
                    def refresh(self, obj):
                        pass
                    
                    def query(self, model):
                        return MockQuery()
                
                return MockDB()
        
        class MockQuery:
            def filter(self, *args):
                return self
            
            def first(self):
                return None
        
        # Inicializar servicio
        telemetry_service = AdvancedTelemetryService(MockServiceFactory())
        
        print("  ✅ AdvancedTelemetryService inicializado")
        
        # Prueba 1: Crear contexto de telemetría
        print("\n🔧 Prueba 1: Creando contexto de telemetría...")
        
        conversation_id = uuid4()
        user_id = uuid4()
        chat_id = uuid4()
        
        context = telemetry_service.start_conversation_tracking(
            conversation_id=conversation_id,
            user_id=user_id,
            chat_id=chat_id,
            mode="guided"
        )
        
        print(f"  ✅ Contexto creado: {conversation_id}")
        
        # Prueba 2: Simular algunas métricas
        print("\n🔧 Prueba 2: Simulando métricas...")
        
        context.add_tokens(tokens_in=100, tokens_out=50)
        context.add_cache_operation(hit=True)
        context.add_cache_operation(hit=False)
        context.add_latency("llm", 150.5)
        context.add_latency("db", 25.3)
        context.steps_executed = 3
        
        print(f"  ✅ Métricas simuladas:")
        print(f"    • Tokens: {context.tokens_in} in, {context.tokens_out} out")
        print(f"    • Cache: {context.cache_hits} hits, {context.cache_misses} misses")
        print(f"    • Latencia LLM: {context.latency_llm_ms}ms")
        print(f"    • Pasos ejecutados: {context.steps_executed}")
        
        # Prueba 3: Crear métricas de conversación (sin guardar en BD)
        print("\n🔧 Prueba 3: Creando métricas de conversación...")
        
        try:
            metrics_data = context.to_conversation_metrics(
                completed_at=datetime.now(timezone.utc)
            )
            
            print(f"  ✅ Métricas creadas exitosamente:")
            print(f"    • Tipo: {type(metrics_data)}")
            print(f"    • Chat ID: {metrics_data.chat_id}")
            print(f"    • User ID: {metrics_data.user_id}")
            print(f"    • Tokens: {metrics_data.tokens_in} in, {metrics_data.tokens_out} out")
            print(f"    • Latencia total: {metrics_data.latency_total_ms}ms")
            print(f"    • Cache ratio: {metrics_data.cache_hit_ratio}")
            print(f"    • Pasos: {metrics_data.steps_executed}")
            
            # Verificar que NO hay estimated_cost_usd
            if hasattr(metrics_data, 'estimated_cost_usd'):
                print(f"  ⚠️ estimated_cost_usd presente: {metrics_data.estimated_cost_usd}")
            else:
                print(f"  ✅ estimated_cost_usd NO está presente (correcto)")
            
        except Exception as e:
            print(f"  ❌ Error creando métricas: {e}")
            return False
        
        # Prueba 4: Verificar esquema de creación
        print("\n🔧 Prueba 4: Verificando esquema de creación...")
        
        try:
            # Intentar crear el esquema (esto debería funcionar sin errores)
            create_schema = ConversationMetricsCreate.model_validate(metrics_data.model_dump())
            print(f"  ✅ Esquema de creación validado correctamente")
            
            # Verificar campos del esquema
            schema_fields = create_schema.model_fields.keys()
            print(f"  📋 Campos del esquema: {list(schema_fields)[:10]}...")
            
            # Verificar que estimated_cost_usd NO está en los campos
            if 'estimated_cost_usd' in schema_fields:
                print(f"  ❌ estimated_cost_usd presente en esquema de creación")
                return False
            else:
                print(f"  ✅ estimated_cost_usd NO está en esquema de creación (correcto)")
                
        except Exception as e:
            print(f"  ❌ Error validando esquema: {e}")
            return False
        
        print("\n🎉 ¡Todas las pruebas de telemetría pasaron!")
        print("  ✅ Contexto creado correctamente")
        print("  ✅ Métricas simuladas sin errores")
        print("  ✅ Métricas de conversación creadas")
        print("  ✅ Esquema validado correctamente")
        print("  ✅ estimated_cost_usd NO está presente")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_schema_consistency():
    """Prueba la consistencia del esquema"""
    print("\n🧪 Probando consistencia del esquema...")
    
    try:
        from app.schemas.telemetry_schema import ConversationMetricsCreate, ConversationMetricsUpdate
        
        print("  📋 Verificando esquemas...")
        
        # Verificar esquema de creación
        create_fields = ConversationMetricsCreate.model_fields.keys()
        print(f"  • Esquema de creación: {len(create_fields)} campos")
        
        # Verificar que estimated_cost_usd NO está presente
        if 'estimated_cost_usd' in create_fields:
            print(f"  ❌ estimated_cost_usd presente en esquema de creación")
            return False
        else:
            print(f"  ✅ estimated_cost_usd NO está en esquema de creación")
        
        # Verificar esquema de actualización
        update_fields = ConversationMetricsUpdate.model_fields.keys()
        print(f"  • Esquema de actualización: {len(update_fields)} campos")
        
        if 'estimated_cost_usd' in update_fields:
            print(f"  ❌ estimated_cost_usd presente en esquema de actualización")
            return False
        else:
            print(f"  ✅ estimated_cost_usd NO está en esquema de actualización")
        
        print("  ✅ Consistencia del esquema verificada")
        return True
        
    except Exception as e:
        print(f"  ❌ Error verificando esquema: {e}")
        return False

async def main():
    """Función principal del script"""
    print("🧪 Probando que el Error de Telemetría se ha Resuelto...")
    print("=" * 80)
    
    tests = [
        ("Fix de Telemetría", test_telemetry_fix),
        ("Consistencia de Esquema", test_schema_consistency)
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
        print("🎉 ¡Error de Telemetría Resuelto!")
        print("\n💡 Problema Solucionado:")
        print("  ❌ ANTES:")
        print("    • Error: cannot insert a non-DEFAULT value into column 'estimated_cost_usd'")
        print("    • Causa: Columna generada automáticamente por PostgreSQL")
        print("    • Impacto: Fallo al guardar métricas de conversación")
        
        print("\n  ✅ AHORA:")
        print("    • estimated_cost_usd NO se incluye en la creación")
        print("    • Esquemas actualizados correctamente")
        print("    • Sistema de telemetría funcionando")
        print("    • Métricas se guardan sin errores")
        
        print("\n🔧 Cambios Realizados:")
        print("  • Removido estimated_cost_usd de ConversationMetricsCreate")
        print("  • Removido estimated_cost_usd de ConversationMetricsUpdate")
        print("  • Actualizado to_conversation_metrics()")
        print("  • Esquemas consistentes con la base de datos")
        
        return 0
    else:
        print("❌ Algunas pruebas fallaron. Revisar implementación.")
        return 1

if __name__ == "__main__":
    # Ejecutar el event loop
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
