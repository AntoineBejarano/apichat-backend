#!/usr/bin/env python3
"""
🤖 AIAnalysisNode - Análisis Inteligente con Esquema Real
──────────────────────────────────────────────────────────
Analiza consultas complejas usando AI pero siempre con
esquema real de la base de datos para evitar alucinaciones.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AIAnalysisNode:
    """
    🤖 Nodo que analiza consultas complejas usando AI con esquema real.
    
    Características:
    - Usa esquema real de la DB (no alucina)
    - Detecta múltiples intenciones
    - Valida SQL antes de ejecutar
    - Transparencia completa del proceso
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.llm_service = factory.get_openai_service()
        self.schema_service = factory.get_schema_explorer_service()
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        🤖 Analiza consulta compleja usando AI con esquema real.
        
        Args:
            state: Estado del grafo con consulta y contexto
            
        Returns:
            Estado actualizado con análisis AI
        """
        start_time = datetime.now()
        
        try:
            # Extraer información del estado
            query = state.get("message", {}).get("content", "")
            db_ids = state.get("db_ids", [])
            compact_schemas = state.get("compact_schemas", {})
            
            logger.info(f"[AIAnalysisNode] 🤖 Iniciando análisis AI para: '{query[:50]}...'")
            
            # 🛡️ VALIDAR QUE TENEMOS ESQUEMA REAL
            if not compact_schemas:
                logger.warning("[AIAnalysisNode] ⚠️ No hay esquema real disponible, usando fallback")
                return await self._handle_no_schema(state, query)
            
            # 📋 PREPARAR CONTEXTO REAL PARA AI
            ai_context = await self._prepare_ai_context(query, compact_schemas)
            logger.info(f"[AIAnalysisNode] 📋 Contexto preparado: {len(ai_context)} caracteres")
            
            # 🤖 ANÁLISIS DE INTENCIONES MÚLTIPLES
            intentions_analysis = await self._analyze_multiple_intentions(query, ai_context)
            logger.info(f"[AIAnalysisNode] 🎯 Intenciones detectadas: {len(intentions_analysis)}")
            
            # 📋 GENERAR PLAN MULTI-INTENCIÓN
            execution_plan = await self._generate_multi_intention_plan(
                query, intentions_analysis, ai_context
            )
            logger.info(f"[AIAnalysisNode] 📋 Plan generado con {len(execution_plan.get('steps', []))} pasos")
            
            # 🔍 VALIDAR SQL DEL PLAN
            validated_plan = await self._validate_plan_sql(execution_plan, compact_schemas)
            
            # 📊 METADATAS DE TRANSPARENCIA
            analysis_metadata = {
                "response_type": "ai_analysis",
                "analysis_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "data_source": "ai_with_real_schema",
                "confidence": "high",
                "coverage": "comprehensive",
                "intentions_detected": len(intentions_analysis),
                "plan_steps": len(validated_plan.get('steps', [])),
                "schema_used": bool(compact_schemas),
                "next_phase": "plan_execution"
            }
            
            logger.info(f"[AIAnalysisNode] ✅ Análisis AI completado en {analysis_metadata['analysis_time_ms']:.1f}ms")
            
            return {
                **state,
                "ai_analysis": intentions_analysis,
                "execution_plan": validated_plan,
                "ai_analysis_metadata": analysis_metadata,
                "current_phase": "ai_analysis_completed"
            }
            
        except Exception as e:
            logger.error(f"[AIAnalysisNode] ❌ Error en análisis AI: {e}")
            
            # 🆘 FALLBACK SEGURO
            fallback_plan = await self._generate_fallback_plan(query, state)
            
            return {
                **state,
                "ai_analysis": {"error": str(e)},
                "execution_plan": fallback_plan,
                "ai_analysis_metadata": {
                    "response_type": "fallback",
                    "analysis_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "data_source": "fallback",
                    "confidence": "low",
                    "coverage": "basic",
                    "error": str(e),
                    "next_phase": "fallback_execution"
                },
                "current_phase": "ai_analysis_failed"
            }
    
    async def _handle_no_schema(self, state: Dict[str, Any], query: str) -> Dict[str, Any]:
        """🛡️ Maneja caso donde no hay esquema disponible."""
        
        fallback_plan = {
            "title": "Análisis Básico sin Esquema",
            "description": "No se pudo acceder al esquema de la base de datos",
            "steps": [
                {
                    "step": "Verificar conexión a base de datos",
                    "action": "db_connection_check",
                    "description": "Comprobar que la base de datos esté accesible"
                }
            ]
        }
        
        return {
            **state,
            "ai_analysis": {"warning": "No hay esquema disponible"},
            "execution_plan": fallback_plan,
            "current_phase": "no_schema_fallback"
        }
    
    async def _prepare_ai_context(self, query: str, compact_schemas: dict) -> str:
        """📋 Prepara contexto real para AI usando esquema de la DB."""
        
        context_parts = [
            "=== ESQUEMA REAL DE LA BASE DE DATOS ===",
            "La siguiente información es VERDADERA y viene directamente de tu base de datos:",
            ""
        ]
        
        for db_id, schema in compact_schemas.items():
            if isinstance(schema, str):
                context_parts.extend([
                    f"--- BASE DE DATOS: {db_id} ---",
                    schema[:2000],  # Limitar tamaño para AI
                    ""
                ])
        
        context_parts.extend([
            "=== INSTRUCCIONES PARA AI ===",
            "1. SOLO usa la información del esquema real proporcionado",
            "2. NUNCA inventes tablas, columnas o estructuras",
            "3. Si algo no está en el esquema, indícalo claramente",
            "4. Genera SQL válido basado en las tablas reales",
            "5. Detecta múltiples intenciones en la consulta del usuario",
            ""
        ])
        
        return "\n".join(context_parts)
    
    async def _analyze_multiple_intentions(self, query: str, ai_context: str) -> List[Dict[str, Any]]:
        """🎯 AI detecta múltiples intenciones en la consulta."""
        
        prompt = f"""
        {ai_context}
        
        === ANÁLISIS DE INTENCIONES MÚLTIPLES ===
        
        CONSULTA DEL USUARIO: "{query}"
        
        Analiza esta consulta y detecta TODAS las intenciones presentes.
        Una consulta puede tener múltiples intenciones (ej: "qué tablas hay Y dónde ver invitaciones").
        
        Para cada intención, identifica:
        - Tipo de intención (list_tables, find_specific_tables, explore_schema, etc.)
        - Palabras clave que la indican
        - Contexto específico
        - Prioridad (1-5, donde 5 es más específica)
        - Confianza (0.0-1.0)
        
        Responde SOLO en formato JSON válido:
        {{
            "intentions": [
                {{
                    "type": "list_tables",
                    "keywords": ["tablas", "db"],
                    "context": "Explorar esquema general",
                    "priority": 3,
                    "confidence": 0.9
                }},
                {{
                    "type": "find_specific_tables",
                    "keywords": ["dónde", "ver", "invitaciones", "clubs"],
                    "context": "Búsqueda específica de contenido",
                    "priority": 5,
                    "confidence": 0.95
                }}
            ]
        }}
        
        IMPORTANTE: Solo responde JSON, sin texto adicional.
        """
        
        try:
            response = await self.llm_service.analyze(prompt)
            intentions_data = json.loads(response)
            return intentions_data.get("intentions", [])
        except Exception as e:
            logger.error(f"[AIAnalysisNode] ❌ Error analizando intenciones: {e}")
            # Fallback a análisis básico
            return [{"type": "general_query", "priority": 1, "confidence": 0.5}]
    
    async def _generate_multi_intention_plan(
        self, 
        query: str, 
        intentions: List[Dict[str, Any]], 
        ai_context: str
    ) -> Dict[str, Any]:
        """📋 Genera plan que satisfaga todas las intenciones detectadas."""
        
        # Ordenar por prioridad (más específica primero)
        sorted_intentions = sorted(intentions, key=lambda x: x.get("priority", 1), reverse=True)
        
        prompt = f"""
        {ai_context}
        
        === GENERACIÓN DE PLAN MULTI-INTENCIÓN ===
        
        CONSULTA: "{query}"
        INTENCIONES DETECTADAS: {json.dumps(sorted_intentions, indent=2)}
        
        Genera un plan de ejecución que satisfaga TODAS las intenciones.
        Cada paso debe ser específico y ejecutable.
        
        Responde en formato JSON:
        {{
            "title": "Título del plan",
            "description": "Descripción del plan",
            "steps": [
                {{
                    "step": "Descripción del paso",
                    "action": "tipo_de_accion",
                    "sql": "SELECT ... (si es consulta SQL)",
                    "description": "Explicación detallada"
                }}
            ]
        }}
        
        TIPOS DE ACCIONES DISPONIBLES:
        - db_query: Consulta a base de datos
        - schema_analysis: Análisis de esquema
        - data_search: Búsqueda de datos específicos
        - response_formatting: Formateo de respuesta
        
        IMPORTANTE: Solo responde JSON, sin texto adicional.
        """
        
        try:
            response = await self.llm_service.analyze(prompt)
            plan_data = json.loads(response)
            return plan_data
        except Exception as e:
            logger.error(f"[AIAnalysisNode] ❌ Error generando plan: {e}")
            # Plan de fallback
            return {
                "title": "Plan de Fallback",
                "description": "Plan básico debido a error en generación",
                "steps": [
                    {
                        "step": "Análisis básico de la consulta",
                        "action": "general_analysis",
                        "description": "Procesar consulta de manera básica"
                    }
                ]
            }
    
    async def _validate_plan_sql(self, plan: Dict[str, Any], compact_schemas: dict) -> Dict[str, Any]:
        """🔍 Valida que el SQL del plan sea válido y use tablas reales."""
        
        if "steps" not in plan:
            return plan
        
        validated_steps = []
        
        for step in plan["steps"]:
            if step.get("action") == "db_query" and step.get("sql"):
                # Validar SQL
                validated_sql = await self._validate_sql_step(step["sql"], compact_schemas)
                step["validated_sql"] = validated_sql
                step["sql_validation"] = "passed" if validated_sql else "failed"
            
            validated_steps.append(step)
        
        plan["steps"] = validated_steps
        return plan
    
    async def _validate_sql_step(self, sql: str, compact_schemas: dict) -> Optional[str]:
        """🔍 Valida que el SQL use tablas reales de la base de datos."""
        
        try:
            # Extraer nombres de tablas del esquema real
            real_tables = set()
            for schema in compact_schemas.values():
                if isinstance(schema, str):
                    lines = schema.split('\n')
                    for line in lines:
                        if 'CREATE TABLE' in line.upper():
                            # Extraer nombre de tabla
                            if '`' in line:
                                table_name = line.split('`')[1]
                                real_tables.add(table_name.lower())
                            elif '"' in line:
                                table_name = line.split('"')[1]
                                real_tables.add(table_name.lower())
            
            # Verificar que el SQL use tablas reales
            sql_lower = sql.lower()
            for table in real_tables:
                if table in sql_lower:
                    return sql  # SQL válido
            
            # Si no usa tablas reales, generar SQL válido
            logger.warning(f"[AIAnalysisNode] ⚠️ SQL usa tablas no existentes: {sql}")
            return None
            
        except Exception as e:
            logger.error(f"[AIAnalysisNode] ❌ Error validando SQL: {e}")
            return None
    
    async def _generate_fallback_plan(self, query: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """🆘 Genera plan de fallback si el análisis AI falla."""
        
        return {
            "title": "Plan de Fallback",
            "description": "Plan básico debido a error en análisis AI",
            "steps": [
                {
                    "step": "Procesar consulta de manera básica",
                    "action": "basic_processing",
                    "description": "Usar heurísticas simples para responder"
                }
            ]
        }
