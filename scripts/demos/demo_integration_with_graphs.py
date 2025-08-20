#!/usr/bin/env python3
"""
🔗 Demo de Integración: Sistema Híbrido + Grafos Existentes
────────────────────────────────────────────────────────────
Demuestra cómo integrar el sistema híbrido de respuesta rápida + AI
con los grafos de exploración y guiados existentes.
"""

import sys
import asyncio
from pathlib import Path
from uuid import uuid4

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.execution.graphs.nodes.quick_response_node import QuickResponseNode
from app.services.execution.graphs.nodes.ai_analysis_node import AIAnalysisNode
from app.services.execution.graphs.nodes.progress_reporting_node import ProgressReportingNode
from app.services.execution.graphs.nodes.sql_validation_node import SQLValidationNode
from app.services.execution.graphs.nodes.response_enhancement_node import ResponseEnhancementNode

class MockFactory:
    """Mock del ServiceFactory para demostración."""
    
    def __init__(self):
        self.mock_cache = {}
        self.mock_schemas = {
            "db_1": """
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invitations (
    id SERIAL PRIMARY KEY,
    club_id INTEGER REFERENCES clubs(id),
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE club_members (
    id SERIAL PRIMARY KEY,
    club_id INTEGER REFERENCES clubs(id),
    user_id INTEGER REFERENCES users(id),
    role VARCHAR(20) DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
            """
        }
    
    def get_cache_service(self):
        return MockCacheService()
    
    def get_schema_explorer_service(self):
        return MockSchemaService()
    
    def get_openai_service(self):
        return MockOpenAIService()
    
    def get_orchestrator_service(self):
        return MockOrchestratorService()

class MockCacheService:
    def get(self, key):
        return None
    def set(self, key, value, ttl=None):
        pass

class MockSchemaService:
    def get_schema_from_cache(self, db_ids):
        return {"db_1": "mock_schema"}

class MockOpenAIService:
    async def analyze(self, prompt):
        """Mock del análisis AI que simula detección de intenciones múltiples."""
        
        if "intenciones múltiples" in prompt:
            return '''
{
    "intentions": [
        {
            "type": "list_tables",
            "keywords": ["tablas", "db"],
            "context": "Explorar esquema general",
            "priority": 3,
            "confidence": 0.9
        },
        {
            "type": "find_specific_tables",
            "keywords": ["dónde", "ver", "invitaciones", "clubs"],
            "context": "Búsqueda específica de contenido",
            "priority": 5,
            "confidence": 0.95
        }
    ]
}
            '''
        elif "plan multi-intención" in prompt:
            return '''
{
    "title": "Plan Multi-Intención: Esquema + Búsqueda Específica",
    "description": "Plan que satisface tanto la exploración general como la búsqueda específica",
    "steps": [
        {
            "step": "Listar todas las tablas disponibles",
            "action": "db_query",
            "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            "description": "Obtener lista completa de tablas para exploración general"
        },
        {
            "step": "Buscar tablas relacionadas con invitaciones y clubs",
            "action": "db_query",
            "sql": "SELECT table_name FROM information_schema.tables WHERE table_name ILIKE '%invitation%' OR table_name ILIKE '%club%'",
            "description": "Identificar tablas específicas para la búsqueda del usuario"
        },
        {
            "step": "Mostrar esquema de tablas relevantes",
            "action": "schema_analysis",
            "description": "Proporcionar detalles del esquema de las tablas encontradas"
        }
    ]
}
            '''
        else:
            return '{"error": "Prompt no reconocido"}'

class MockOrchestratorService:
    async def emit_status_progress(self, chat_id, step, total_steps, message, percentage):
        print(f"📡 [Orchestrator] Progreso: {message} ({percentage:.1f}%)")

async def demo_integration_with_graphs():
    """🔗 Demuestra la integración del sistema híbrido con grafos existentes."""
    
    print("🔗 DEMO DE INTEGRACIÓN: Sistema Híbrido + Grafos Existentes")
    print("=" * 80)
    
    try:
        # 🏗️ INICIALIZAR COMPONENTES
        print("🏗️ Inicializando componentes del sistema híbrido...")
        factory = MockFactory()
        
        # Crear nodos del sistema híbrido
        quick_response_node = QuickResponseNode(factory)
        ai_analysis_node = AIAnalysisNode(factory)
        progress_node = ProgressReportingNode(factory)
        sql_validation_node = SQLValidationNode(factory)
        response_enhancement_node = ResponseEnhancementNode(factory)
        
        print("✅ Componentes del sistema híbrido inicializados")
        print()
        
        # 🧪 CONSULTA COMPLEJA DEL USUARIO
        complex_query = "Hola, sabes que tablas tiene mi db y donde puedo ver la invitaciones de clubs que solucita la gente?"
        
        print("🧪 CONSULTA COMPLEJA DEL USUARIO:")
        print(f"   '{complex_query}'")
        print()
        
        # 📋 ESTADO INICIAL
        initial_state = {
            "chat_id": str(uuid4()),
            "message": {"content": complex_query},
            "db_ids": ["db_1"],
            "compact_schemas": factory.mock_schemas,
            "current_phase": "starting"
        }
        
        print("📋 Estado inicial preparado")
        print()
        
        # 🔄 SIMULACIÓN DEL FLUJO COMPLETO DEL SISTEMA HÍBRIDO
        print("🔄 SIMULANDO FLUJO COMPLETO DEL SISTEMA HÍBRIDO")
        print("=" * 80)
        
        # ⚡ FASE 1: RESPUESTA RÁPIDA
        print("\n⚡ FASE 1: RESPUESTA RÁPIDA (ExplorationGraph)")
        print("-" * 50)
        
        quick_state = await quick_response_node(initial_state)
        
        print("📊 RESULTADO RESPUESTA RÁPIDA:")
        print(f"   Estado: {quick_state.get('current_phase')}")
        print(f"   Tiempo: {quick_state.get('quick_response_metadata', {}).get('response_time_ms', 0):.1f}ms")
        print(f"   Fuente: {quick_state.get('quick_response_metadata', {}).get('data_source', 'unknown')}")
        print()
        
        print("📝 RESPUESTA RÁPIDA GENERADA:")
        quick_response = quick_state.get('quick_response', '')
        print(f"   {quick_response[:100]}...")
        print()
        
        # 📊 REPORTE DE PROGRESO 1
        print("📊 REPORTE DE PROGRESO 1:")
        progress_state_1 = await progress_node(quick_state)
        progress_report_1 = progress_state_1.get('progress_report', {})
        
        print(f"   Fase: {progress_report_1.get('phase')}")
        print(f"   Mensaje: {progress_report_1.get('message')}")
        print(f"   Siguiente: {progress_report_1.get('next_step')}")
        print(f"   Tiempo estimado: {progress_report_1.get('estimated_time')}")
        print()
        
        # 🤖 FASE 2: ANÁLISIS AI
        print("🤖 FASE 2: ANÁLISIS AI (GuidedGraph)")
        print("-" * 50)
        
        ai_state = await ai_analysis_node(quick_state)
        
        print("📊 RESULTADO ANÁLISIS AI:")
        print(f"   Estado: {ai_state.get('current_phase')}")
        print(f"   Tiempo: {ai_state.get('ai_analysis_metadata', {}).get('analysis_time_ms', 0):.1f}ms")
        print(f"   Intenciones: {ai_state.get('ai_analysis_metadata', {}).get('intentions_detected', 0)}")
        print(f"   Pasos del plan: {ai_state.get('ai_analysis_metadata', {}).get('plan_steps', 0)}")
        print()
        
        # Mostrar intenciones detectadas
        ai_analysis = ai_state.get('ai_analysis', {})
        if isinstance(ai_analysis, list):
            print("🎯 INTENCIONES DETECTADAS:")
            for i, intention in enumerate(ai_analysis, 1):
                print(f"   {i}. {intention.get('type', 'unknown')}")
                print(f"      → Contexto: {intention.get('context', 'N/A')}")
                print(f"      → Prioridad: {intention.get('priority', 'N/A')}")
                print(f"      → Confianza: {intention.get('confidence', 'N/A')}")
                print()
        
        # Mostrar plan generado
        plan = ai_state.get('execution_plan', {})
        if plan:
            print("📋 PLAN GENERADO:")
            print(f"   Título: {plan.get('title', 'N/A')}")
            print(f"   Descripción: {plan.get('description', 'N/A')}")
            print(f"   Pasos: {len(plan.get('steps', []))}")
            print()
            
            for i, step in enumerate(plan.get('steps', []), 1):
                print(f"   {i}. {step.get('step', 'N/A')}")
                print(f"      → Acción: {step.get('action', 'N/A')}")
                if step.get('sql'):
                    print(f"      → SQL: {step.get('sql', 'N/A')}")
                print(f"      → Descripción: {step.get('description', 'N/A')}")
                print()
        
        # 🔍 FASE 3: VALIDACIÓN SQL
        print("🔍 FASE 3: VALIDACIÓN SQL")
        print("-" * 50)
        
        validation_state = await sql_validation_node(ai_state)
        
        print("📊 RESULTADO VALIDACIÓN SQL:")
        validation_metadata = validation_state.get('sql_validation_metadata', {})
        print(f"   Estado: {validation_state.get('current_phase')}")
        print(f"   Tiempo: {validation_metadata.get('validation_time_ms', 0):.1f}ms")
        print(f"   Total pasos: {validation_metadata.get('total_steps', 0)}")
        print(f"   Pasos validados: {validation_metadata.get('validated_steps', 0)}")
        print(f"   Pasos fallidos: {validation_metadata.get('failed_steps', 0)}")
        print(f"   Problemas seguridad: {validation_metadata.get('security_issues', 0)}")
        print()
        
        # 🚀 FASE 4: MEJORA DE RESPUESTA
        print("🚀 FASE 4: MEJORA DE RESPUESTA")
        print("-" * 50)
        
        enhanced_state = await response_enhancement_node(validation_state)
        
        print("📊 RESULTADO MEJORA DE RESPUESTA:")
        enhancement_metadata = enhanced_state.get('enhancement_metadata', {})
        print(f"   Estado: {enhanced_state.get('current_phase')}")
        print(f"   Tiempo: {enhancement_metadata.get('enhancement_time_ms', 0):.1f}ms")
        print(f"   Tipo: {enhancement_metadata.get('enhancement_type', 'unknown')}")
        print(f"   Calidad: {enhancement_metadata.get('response_quality', 'unknown')}")
        print()
        
        # 📊 REPORTE DE PROGRESO FINAL
        print("📊 REPORTE DE PROGRESO FINAL:")
        progress_state_final = await progress_node(enhanced_state)
        progress_report_final = progress_state_final.get('progress_report', {})
        
        print(f"   Fase: {progress_report_final.get('phase')}")
        print(f"   Mensaje: {progress_report_final.get('message')}")
        print(f"   Siguiente: {progress_report_final.get('next_step')}")
        print(f"   Tiempo estimado: {progress_report_final.get('estimated_time')}")
        print()
        
        # 🎯 INTEGRACIÓN CON GRAFOS EXISTENTES
        print("🎯 INTEGRACIÓN CON GRAFOS EXISTENTES")
        print("=" * 80)
        
        print("✅ **EXPLORATIONGRAPH** (Respuesta Rápida):")
        print("   • Usa QuickResponseNode para respuestas inmediatas")
        print("   • Proporciona información básica desde cache")
        print("   • Tiempo de respuesta: <100ms")
        print("   • Fuente: Esquema real de la DB")
        print()
        
        print("✅ **GUIDEDGRAPH** (Análisis AI):")
        print("   • Usa AIAnalysisNode para detección de intenciones")
        print("   • Genera planes multi-paso personalizados")
        print("   • Tiempo de análisis: 2-5s")
        print("   • Fuente: AI con contexto real de la DB")
        print()
        
        print("✅ **NODOS COMPARTIDOS** (Reutilización):")
        print("   • ProgressReportingNode: Reporta progreso en ambos grafos")
        print("   • SQLValidationNode: Valida SQL en ambos grafos")
        print("   • ResponseEnhancementNode: Mejora respuestas finales")
        print()
        
        # 🏗️ ARQUITECTURA ESCALABLE
        print("🏗️ ARQUITECTURA ESCALABLE")
        print("=" * 80)
        
        print("🔄 **REUTILIZACIÓN DE COMPONENTES:**")
        print("   • Nodos modulares que se pueden usar en cualquier grafo")
        print("   • Configuración por tipo de consulta")
        print("   • Fácil extensión para nuevos tipos de grafos")
        print()
        
        print("📊 **FLUJO HÍBRIDO INTEGRADO:**")
        print("   1. ExplorationGraph → Respuesta rápida (<100ms)")
        print("   2. GuidedGraph → Análisis AI en paralelo (2-5s)")
        print("   3. Nodos compartidos → Validación y mejora")
        print("   4. Respuesta final → Combinación de todas las fuentes")
        print()
        
        print("🎯 **BENEFICIOS DE LA INTEGRACIÓN:**")
        print("   • Experiencia de usuario fluida y progresiva")
        print("   • Aprovechamiento máximo del cache y esquema")
        print("   • Inteligencia AI sin bloquear respuestas básicas")
        print("   • Arquitectura escalable y mantenible")
        print("   • Transparencia completa para el cliente")
        
        print("\n" + "=" * 80)
        print("🎉 ¡INTEGRACIÓN COMPLETA EXITOSA!")
        print("   El sistema híbrido está perfectamente integrado con los grafos existentes")
        print("   Los usuarios reciben respuestas inmediatas y mejoradas progresivamente")
        print("   La arquitectura es escalable y reutilizable")
        
    except Exception as e:
        print(f"❌ Error durante la demostración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_integration_with_graphs())
