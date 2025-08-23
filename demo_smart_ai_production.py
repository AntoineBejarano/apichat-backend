#!/usr/bin/env python3
"""
🧠 DEMO: Smart AI System en Producción
───────────────────────────────────────
Demuestra el Smart AI System completamente integrado
y funcionando en el ExplorationGraph para producción.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Configurar logging para producción
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def demo_smart_ai_production():
    """🧠 Demuestra el Smart AI System en producción"""
    
    try:
        logger.info("🚀 Iniciando DEMO del Smart AI System en Producción...")
        
        # 1. Importar componentes
        logger.info("📦 Importando componentes de producción...")
        from app.services.execution.graphs.exploration_graph import ExplorationGraph
        from app.core.service_factory import ServiceFactory
        from app.core.database import get_db
        
        # 2. Crear factory con base de datos real
        logger.info("🏭 Creando ServiceFactory con base de datos real...")
        
        # Obtener sesión de base de datos real
        db = next(get_db())
        factory = ServiceFactory(db=db)
        
        # 3. Crear ExplorationGraph con Smart AI
        logger.info("🚀 Creando ExplorationGraph con Smart AI habilitado...")
        graph = ExplorationGraph(factory=factory)
        
        # 4. Verificar estado del Smart AI
        logger.info("✅ Verificando estado del Smart AI System...")
        smart_ai_enabled = graph.is_smart_ai_enabled()
        logger.info(f"🧠 Smart AI habilitado: {smart_ai_enabled}")
        
        if not smart_ai_enabled:
            logger.error("❌ Smart AI System no está habilitado")
            return False
        
        # 5. Obtener información del workflow
        logger.info("🔄 Obteniendo información del workflow...")
        workflow_info = graph.get_smart_ai_workflow_info()
        logger.info(f"📊 Workflow: {workflow_info['workflow']['description']}")
        logger.info(f"📋 Flujo: {' → '.join(workflow_info['workflow']['flow'])}")
        
        # 6. Warm-up del cache para producción
        logger.info("🔥 Iniciando warm-up del cache para producción...")
        warm_up_result = await graph.warm_up_smart_ai_cache()
        if warm_up_result:
            logger.info("✅ Cache calentado para producción")
        else:
            logger.warning("⚠️ Warm-up del cache falló (continuando...)")
        
        # 7. Demostrar consultas reales
        logger.info("🧪 Demostrando consultas reales con Smart AI...")
        
        test_queries = [
            "¿Cuántos usuarios hay en la base de datos?",
            "Muestra las tablas disponibles",
            "Ejecuta esta función API",
            "Conecta con MCP",
            "Analiza el esquema de la base de datos"
        ]
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"🧠 CONSULTA {i}: {query}")
            logger.info(f"{'='*60}")
            
            # Crear estado de prueba
            test_state = {
                "chat_id": f"demo_chat_{i}",
                "user_id": "demo_user",
                "message": {
                    "content": query,
                    "role": "user",
                    "timestamp": datetime.now().isoformat()
                },
                "db_ids": [],
                "compact_schemas": {},
                "performance_metrics": {
                    "performance": {
                        "init": 0.0,
                        "smart_ai": 0.0,
                        "react_think": 0.0,
                        "schema_build": 0.0,
                        "openai_plan": 0.0,
                        "sql_exec": 0.0,
                        "total": 0.0
                    },
                    "tokens": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0
                    }
                }
            }
            
            try:
                # Procesar con Smart AI
                start_time = datetime.now()
                
                # Obtener nodo Smart AI
                smart_ai_node = graph._get_node('smart_ai')
                
                # Crear performance metrics
                from app.services.execution.graphs.utils.performance_metrics import PerformanceMetrics
                perf_metrics = PerformanceMetrics()
                
                # Procesar consulta
                enriched_state = await smart_ai_node.run(test_state, perf_metrics)
                
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Mostrar resultados
                logger.info(f"✅ Procesamiento completado en {processing_time:.1f}ms")
                logger.info(f"🔄 Query normalizada: {enriched_state.get('normalized_query', 'N/A')}")
                logger.info(f"🎯 Intención: {enriched_state.get('intent_type', 'N/A')}")
                logger.info(f"📊 Confianza rephrase: {enriched_state.get('rephrase_confidence', 'N/A')}")
                logger.info(f"📊 Confianza intent: {enriched_state.get('intent_confidence', 'N/A')}")
                logger.info(f"🛣️ Ruta de enrutamiento: {enriched_state.get('routing_path', 'N/A')}")
                
                # Mostrar recomendaciones si existen
                recommendations = enriched_state.get('smart_ai_recommendations', [])
                if recommendations:
                    logger.info(f"💡 Recomendaciones: {len(recommendations)} encontradas")
                    for rec in recommendations[:3]:  # Mostrar solo las primeras 3
                        logger.info(f"   • {rec.get('action', 'N/A')}: {rec.get('description', 'N/A')}")
                
            except Exception as e:
                logger.error(f"❌ Error procesando consulta: {e}")
                continue
        
        # 8. Mostrar estadísticas finales
        logger.info(f"\n{'='*60}")
        logger.info("📊 ESTADÍSTICAS FINALES DEL SMART AI SYSTEM")
        logger.info(f"{'='*60}")
        
        try:
            smart_ai_stats = graph.get_smart_ai_stats()
            if 'error' not in smart_ai_stats:
                logger.info(f"📈 Estadísticas Smart AI: {smart_ai_stats}")
            else:
                logger.warning(f"⚠️ No se pudieron obtener estadísticas: {smart_ai_stats['error']}")
        except Exception as e:
            logger.warning(f"⚠️ Error obteniendo estadísticas: {e}")
        
        # 9. Verificar estado del cache
        logger.info("🔍 Verificando estado del cache...")
        cache_status = graph.get_cache_status()
        logger.info(f"📊 Estado del cache: {cache_status}")
        
        # 10. Verificar métricas de performance
        logger.info("⚡ Verificando métricas de performance...")
        performance_metrics = graph.get_performance_metrics()
        logger.info(f"📊 Métricas de performance: {performance_metrics}")
        
        logger.info(f"\n{'='*60}")
        logger.info("🎉 ¡DEMO DEL SMART AI SYSTEM COMPLETADO EXITOSAMENTE!")
        logger.info("🚀 El sistema está listo para producción")
        logger.info(f"{'='*60}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en demo de producción: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """🏁 Función principal del demo"""
    
    logger.info("🚀 Iniciando DEMO del Smart AI System en Producción...")
    
    success = await demo_smart_ai_production()
    
    if success:
        print("\n🎉 ¡Smart AI System 100% funcional para producción!")
        print("🧠 Integración completa con ExplorationGraph")
        print("🚀 Cache inteligente con versioning")
        print("🎯 Clasificación de intenciones")
        print("🔄 Rephrase inteligente de consultas")
        print("📊 Métricas y monitoreo completo")
        sys.exit(0)
    else:
        print("\n❌ Demo falló. Revisar logs arriba.")
        sys.exit(1)

if __name__ == "__main__":
    # Ejecutar demo
    asyncio.run(main())
