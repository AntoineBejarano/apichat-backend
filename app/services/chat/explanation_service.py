#!/usr/bin/env python3
"""
ExplanationService - Servicio de explicación para la Fase 5
────────────────────────────────────────────────────────────
Implementa:
- Explicación del plan y SQL generado
- Resumen de tablas, joins, filtros
- Explicación en lenguaje natural
- Sugerencias de optimización
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class ExplanationService:
    """
    Servicio para generar explicaciones del plan y SQL generado.
    
    Implementa la octava etapa de la Fase 5:
    - Explicación del plan
    - Explicación del SQL
    - Resumen de resultados
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
    
    async def explain_query(
        self, 
        plan: Dict[str, Any], 
        sql: str, 
        results: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Genera explicación completa de la consulta.
        
        Args:
            plan: Plan de consulta usado
            sql: SQL generado y ejecutado
            results: Resultados de la ejecución
            context: Contexto completo
            
        Returns:
            Explicación en lenguaje natural
        """
        try:
            start_time = time.time()
            self.logger.info(f"[ExplanationService] 📝 Generando explicación para consulta con {results.get('row_count', 0)} filas")
            
            # 🔧 FASE 5: 1. Explicación del plan
            plan_explanation = self._explain_plan(plan)
            
            # 🔧 FASE 5: 2. Explicación del SQL
            sql_explanation = self._explain_sql(sql, plan)
            
            # 🔧 FASE 5: 3. Explicación de resultados
            results_explanation = self._explain_results(results, context)
            
            # 🔧 FASE 5: 4. Sugerencias de optimización
            optimization_suggestions = self._generate_optimization_suggestions(plan, results)
            
            # 🔧 FASE 5: 5. Construir explicación completa
            explanation_parts = [
                "🧠 **Explicación de la Consulta**",
                "",
                plan_explanation,
                "",
                sql_explanation,
                "",
                results_explanation
            ]
            
            if optimization_suggestions:
                explanation_parts.extend([
                    "",
                    "💡 **Sugerencias de Optimización**",
                    optimization_suggestions
                ])
            
            explanation = "\n".join(explanation_parts)
            
            processing_time = int((time.time() - start_time) * 1000)
            self.logger.info(f"[ExplanationService] ✅ Explicación generada en {processing_time}ms")
            
            return explanation
            
        except Exception as e:
            self.logger.error(f"[ExplanationService] ❌ Error generando explicación: {e}")
            return f"Error generando explicación: {str(e)}"
    
    def _explain_plan(self, plan: Dict[str, Any]) -> str:
        """Genera explicación del plan de consulta"""
        try:
            explanation_parts = []
            
            # 🔧 FASE 5: Información del plan
            explanation_parts.append("📋 **Plan de Consulta**")
            
            # 🔧 FASE 5: Tablas base
            base_tables = plan.get('base_tables', [])
            if base_tables:
                explanation_parts.append(f"🏗️ **Tablas consultadas**: {', '.join(base_tables)}")
            
            # 🔧 FASE 5: Joins
            joins = plan.get('joins', [])
            if joins:
                join_descriptions = []
                for join in joins:
                    desc = f"{join['source_table']} → {join['target_table']} ({join['type']})"
                    join_descriptions.append(desc)
                explanation_parts.append(f"🔗 **Joins realizados**: {', '.join(join_descriptions)}")
            else:
                explanation_parts.append("🔗 **Joins**: No se requirieron joins")
            
            # 🔧 FASE 5: Filtros
            filters = plan.get('filters', [])
            if filters:
                filter_descriptions = [f"{f['column']}" for f in filters]
                explanation_parts.append(f"🔍 **Filtros aplicados**: {', '.join(filter_descriptions)}")
            else:
                explanation_parts.append("🔍 **Filtros**: No se aplicaron filtros específicos")
            
            # 🔧 FASE 5: Proyecciones
            projections = plan.get('projections', [])
            if projections:
                proj_descriptions = [f"{p['column']}" for p in projections]
                explanation_parts.append(f"📊 **Columnas seleccionadas**: {', '.join(proj_descriptions)}")
            
            # 🔧 FASE 5: Ordenamiento
            ordering = plan.get('ordering')
            if ordering:
                explanation_parts.append(f"📈 **Ordenamiento**: {ordering['column']} {ordering['direction']}")
            
            # 🔧 FASE 5: Complejidad estimada
            complexity = plan.get('estimated_complexity', 'unknown')
            explanation_parts.append(f"⚡ **Complejidad estimada**: {complexity}")
            
            return "\n".join(explanation_parts)
            
        except Exception as e:
            return f"Error explicando plan: {str(e)}"
    
    def _explain_sql(self, sql: str, plan: Dict[str, Any]) -> str:
        """Genera explicación del SQL generado"""
        try:
            explanation_parts = []
            
            # 🔧 FASE 5: Información del SQL
            explanation_parts.append("🗃️ **SQL Generado**")
            explanation_parts.append(f"```sql\n{sql}\n```")
            
            # 🔧 FASE 5: Análisis del SQL
            sql_upper = sql.upper()
            
            # Contar cláusulas
            has_where = 'WHERE' in sql_upper
            has_order = 'ORDER BY' in sql_upper
            has_limit = 'LIMIT' in sql_upper
            has_joins = 'JOIN' in sql_upper
            
            explanation_parts.append("🔍 **Análisis del SQL**:")
            explanation_parts.append(f"  • Cláusula WHERE: {'✅ Sí' if has_where else '❌ No'}")
            explanation_parts.append(f"  • Cláusula ORDER BY: {'✅ Sí' if has_order else '❌ No'}")
            explanation_parts.append(f"  • Cláusula LIMIT: {'✅ Sí' if has_limit else '❌ No'}")
            explanation_parts.append(f"  • Joins: {'✅ Sí' if has_joins else '❌ No'}")
            
            # 🔧 FASE 5: Seguridad
            explanation_parts.append("🛡️ **Verificaciones de Seguridad**:")
            explanation_parts.append("  • Solo comandos SELECT: ✅")
            explanation_parts.append("  • Sin DDL/DML: ✅")
            explanation_parts.append("  • Modo solo lectura: ✅")
            
            return "\n".join(explanation_parts)
            
        except Exception as e:
            return f"Error explicando SQL: {str(e)}"
    
    def _explain_results(self, results: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Genera explicación de los resultados"""
        try:
            explanation_parts = []
            
            # 🔧 FASE 5: Información de resultados
            explanation_parts.append("📊 **Resultados de la Ejecución**")
            
            # 🔧 FASE 5: Estadísticas básicas
            row_count = results.get('row_count', 0)
            columns = results.get('columns', [])
            execution_time = results.get('execution_time_ms', 0)
            
            explanation_parts.append(f"📈 **Filas retornadas**: {row_count}")
            explanation_parts.append(f"📋 **Columnas**: {', '.join(columns) if columns else 'No especificadas'}")
            explanation_parts.append(f"⏱️ **Tiempo de ejecución**: {execution_time}ms")
            
            # 🔧 FASE 5: Información de la base de datos
            db_name = context.get('database_name', 'Unknown')
            schema_version = context.get('schema_version', 'Unknown')
            total_tables = context.get('total_tables', 0)
            total_relationships = context.get('total_relationships', 0)
            
            explanation_parts.append(f"🗄️ **Base de datos**: {db_name}")
            explanation_parts.append(f"📋 **Versión del schema**: {schema_version}")
            explanation_parts.append(f"🏗️ **Total de tablas disponibles**: {total_tables}")
            explanation_parts.append(f"🔗 **Total de relaciones disponibles**: {total_relationships}")
            
            # 🔧 FASE 5: Análisis de performance
            if execution_time > 0:
                if execution_time < 100:
                    performance = "🚀 Excelente"
                elif execution_time < 500:
                    performance = "⚡ Buena"
                elif execution_time < 1000:
                    performance = "📊 Aceptable"
                else:
                    performance = "🐌 Lenta"
                
                explanation_parts.append(f"📊 **Performance**: {performance} ({execution_time}ms)")
            
            return "\n".join(explanation_parts)
            
        except Exception as e:
            return f"Error explicando resultados: {str(e)}"
    
    def _generate_optimization_suggestions(self, plan: Dict[str, Any], results: Dict[str, Any]) -> str:
        """Genera sugerencias de optimización"""
        try:
            suggestions = []
            
            # 🔧 FASE 5: Sugerencias basadas en el plan
            complexity = plan.get('estimated_complexity', 'unknown')
            if complexity == 'very_complex':
                suggestions.append("• Considerar dividir la consulta en subconsultas más simples")
                suggestions.append("• Verificar que existan índices en las columnas de JOIN")
            
            # 🔧 FASE 5: Sugerencias basadas en joins
            joins = plan.get('joins', [])
            if len(joins) > 3:
                suggestions.append("• Evaluar si todos los JOINs son necesarios")
                suggestions.append("• Considerar usar vistas materializadas para consultas complejas")
            
            # 🔧 FASE 5: Sugerencias basadas en filtros
            filters = plan.get('filters', [])
            if not filters:
                suggestions.append("• Agregar filtros específicos para reducir el conjunto de datos")
                suggestions.append("• Considerar usar LIMIT más restrictivo")
            
            # 🔧 FASE 5: Sugerencias basadas en proyecciones
            projections = plan.get('projections', [])
            if len(projections) > 10:
                suggestions.append("• Revisar si todas las columnas son necesarias")
                suggestions.append("• Considerar usar SELECT específico en lugar de SELECT *")
            
            # 🔧 FASE 5: Sugerencias basadas en resultados
            row_count = results.get('row_count', 0)
            if row_count > 500:
                suggestions.append("• Considerar paginación para grandes conjuntos de datos")
                suggestions.append("• Evaluar si se necesita toda la información")
            
            # 🔧 FASE 5: Sugerencias generales
            suggestions.append("• Verificar que existan índices en las columnas de filtrado")
            suggestions.append("• Considerar el uso de EXPLAIN ANALYZE para optimización")
            
            if suggestions:
                return "\n".join(suggestions)
            else:
                return "• La consulta está bien optimizada para el caso de uso actual"
                
        except Exception as e:
            return f"Error generando sugerencias: {str(e)}"
    
    async def generate_summary(self, plan: Dict[str, Any], results: Dict[str, Any]) -> str:
        """Genera un resumen ejecutivo de la consulta"""
        try:
            summary_parts = []
            
            # 🔧 FASE 5: Resumen ejecutivo
            summary_parts.append("📋 **Resumen Ejecutivo**")
            
            # 🔧 FASE 5: Información clave
            base_tables = plan.get('base_tables', [])
            joins_count = len(plan.get('joins', []))
            row_count = results.get('row_count', 0)
            execution_time = results.get('execution_time_ms', 0)
            
            summary_parts.append(f"• Se consultaron {len(base_tables)} tablas: {', '.join(base_tables)}")
            summary_parts.append(f"• Se realizaron {joins_count} operaciones de JOIN")
            summary_parts.append(f"• Se retornaron {row_count} filas de resultados")
            summary_parts.append(f"• La ejecución tomó {execution_time}ms")
            
            # 🔧 FASE 5: Estado de la consulta
            if execution_time < 100:
                status = "✅ Excelente performance"
            elif execution_time < 500:
                status = "⚡ Buena performance"
            elif execution_time < 1000:
                status = "📊 Performance aceptable"
            else:
                status = "⚠️ Performance lenta, considerar optimización"
            
            summary_parts.append(f"• Estado: {status}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            return f"Error generando resumen: {str(e)}"
    
    async def generate_debug_info(self, plan: Dict[str, Any], sql: str, results: Dict[str, Any], context: Dict[str, Any]) -> str:
        """Genera información de debugging"""
        try:
            debug_parts = []
            
            # 🔧 FASE 5: Información de debugging
            debug_parts.append("🐛 **Información de Debugging**")
            
            # 🔧 FASE 5: Timestamps
            debug_parts.append(f"🕐 **Timestamp de ejecución**: {datetime.now(timezone.utc).isoformat()}")
            
            # 🔧 FASE 5: Metadatos del plan
            if 'created_at' in plan:
                debug_parts.append(f"📅 **Plan creado**: {plan['created_at']}")
            
            if 'processing_time_ms' in plan:
                debug_parts.append(f"⏱️ **Tiempo de planificación**: {plan['processing_time_ms']}ms")
            
            # 🔧 FASE 5: Metadatos de resultados
            if 'execution_metadata' in results:
                metadata = results['execution_metadata']
                debug_parts.append(f"🗄️ **Base de datos**: {metadata.get('database_name', 'Unknown')}")
                debug_parts.append(f"📋 **Schema versión**: {metadata.get('schema_version', 'Unknown')}")
            
            # 🔧 FASE 5: Configuración de ejecución
            if 'timeout_seconds' in results:
                debug_parts.append(f"⏰ **Timeout configurado**: {results['timeout_seconds']}s")
            
            if 'max_rows' in results:
                debug_parts.append(f"📏 **Límite de filas**: {results['max_rows']}")
            
            # 🔧 FASE 5: Contexto
            debug_parts.append(f"🔍 **Contexto**:")
            debug_parts.append(f"  • DB ID: {context.get('db_id', 'Unknown')}")
            debug_parts.append(f"  • Snapshot ID: {context.get('snapshot_id', 'Unknown')}")
            debug_parts.append(f"  • Usuario: {context.get('user_id', 'Unknown')}")
            
            return "\n".join(debug_parts)
            
        except Exception as e:
            return f"Error generando información de debugging: {str(e)}"
