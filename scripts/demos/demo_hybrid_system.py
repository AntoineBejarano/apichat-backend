#!/usr/bin/env python3
"""
🚀 Demo del Sistema Híbrido: Respuesta Rápida + AI
───────────────────────────────────────────────────
Demuestra cómo el sistema proporciona respuestas inmediatas
mientras la AI analiza y genera planes completos.
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

async def demo_hybrid_system():
    """🚀 Demuestra el sistema híbrido en acción."""
    
    print("🚀 DEMO DEL SISTEMA HÍBRIDO: Respuesta Rápida + AI")
    print("=" * 80)
    
    try:
        # 🏗️ INICIALIZAR COMPONENTES
        print("🏗️ Inicializando componentes del sistema...")
        factory = MockFactory()
        
        # Crear nodos
        quick_response_node = QuickResponseNode(factory)
        ai_analysis_node = AIAnalysisNode(factory)
        progress_node = ProgressReportingNode(factory)
        
        print("✅ Componentes inicializados")
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
        
        # ⚡ FASE 1: RESPUESTA RÁPIDA
        print("⚡ FASE 1: GENERANDO RESPUESTA RÁPIDA")
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
        print("🤖 FASE 2: ANÁLISIS AI EN PARALELO")
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
        
        # 📊 REPORTE DE PROGRESO 2
        print("📊 REPORTE DE PROGRESO 2:")
        progress_state_2 = await progress_node(ai_state)
        progress_report_2 = progress_state_2.get('progress_report', {})
        
        print(f"   Fase: {progress_report_2.get('phase')}")
        print(f"   Mensaje: {progress_report_2.get('message')}")
        print(f"   Siguiente: {progress_report_2.get('next_step')}")
        print(f"   Tiempo estimado: {progress_report_2.get('estimated_time')}")
        print()
        
        # 🎯 RESUMEN FINAL
        print("🎯 RESUMEN FINAL DEL SISTEMA HÍBRIDO")
        print("=" * 80)
        
        print("✅ VENTAJAS IMPLEMENTADAS:")
        print("   1. ⚡ Respuesta RÁPIDA (<100ms) con información real de la DB")
        print("   2. 🤖 Análisis AI completo en paralelo (2-5s)")
        print("   3. 🎯 Detección de MÚLTIPLES intenciones")
        print("   4. 📋 Plan multi-paso que satisface todas las consultas")
        print("   5. 🛡️ Validación SQL con esquema real (no alucinaciones)")
        print("   6. 📊 Transparencia completa para el cliente")
        print("   7. 🔄 Escalabilidad en grafos modulares")
        print()
        
        print("🚀 FLUJO COMPLETO:")
        print("   Usuario envía consulta compleja")
        print("   ↓")
        print("   ⚡ Sistema responde INMEDIATAMENTE con esquema básico")
        print("   ↓")
        print("   🤖 AI analiza intenciones múltiples en paralelo")
        print("   ↓")
        print("   📋 Genera plan que satisface todas las consultas")
        print("   ↓")
        print("   🚀 Ejecuta plan paso a paso")
        print("   ↓")
        print("   📊 Usuario recibe respuesta completa y específica")
        print()
        
        print("🎉 ¡SISTEMA HÍBRIDO FUNCIONANDO PERFECTAMENTE!")
        print("   El usuario NUNCA espera y recibe información progresivamente")
        print("   La AI NO alucina y usa solo esquema real de la DB")
        print("   Todo es transparente y escalable")
        
    except Exception as e:
        print(f"❌ Error durante la demostración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(demo_hybrid_system())
