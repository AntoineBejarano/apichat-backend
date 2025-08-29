#!/usr/bin/env python3
"""
SQLGeneratorService - Servicio de generación SQL para la Fase 5
────────────────────────────────────────────────────────────────
Implementa:
- Generación SQL estricto, solo SELECT
- Con LIMIT y TIMEOUT
- Basado en el plan validado
- Formateo del SQL generado
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class SQLGeneratorService:
    """
    Servicio para generar SQL estricto basado en el plan de consulta.
    
    Implementa la quinta etapa de la Fase 5:
    - Generación SQL estricto
    - Solo SELECT permitido
    - LIMIT y TIMEOUT configurables
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 5: Configuración por defecto
        self.default_limit = 1000
        self.max_limit = 10000
        self.default_timeout = 30
        
        # 🔧 FASE 5: Palabras clave prohibidas
        self.forbidden_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE',
            'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'xp_', 'sp_', 'MERGE', 'UPSERT'
        ]
    
    async def generate_sql(
        self, 
        plan: Dict[str, Any], 
        context: Dict[str, Any], 
        query: str
    ) -> Dict[str, Any]:
        """
        Genera SQL estricto basado en el plan de consulta.
        
        Args:
            plan: Plan de consulta validado
            context: Contexto completo
            query: Consulta original del usuario
            
        Returns:
            SQL generado con metadatos
        """
        try:
            start_time = time.time()
            self.logger.info(f"[SQLGeneratorService] 🗃️ Generando SQL para plan con {len(plan.get('base_tables', []))} tablas")
            
            # 🔧 FASE 5: 1. Validar plan
            if not self._validate_plan(plan):
                return {
                    "status": "cannot_generate",
                    "reason": "Plan inválido o incompleto",
                    "suggestions": [
                        "Verificar que el plan contenga tablas base",
                        "Asegurar que las entidades estén correctamente identificadas"
                    ]
                }
            
            # 🔧 FASE 5: 2. Generar SELECT básico
            select_clause = self._generate_select_clause(plan)
            if not select_clause:
                return {
                    "status": "cannot_generate",
                    "reason": "No se pudieron identificar columnas para seleccionar",
                    "suggestions": [
                        "Especificar qué columnas quieres ver",
                        "Usar nombres de columnas específicos"
                    ]
                }
            
            # 🔧 FASE 5: 3. Generar FROM con tablas base
            from_clause = self._generate_from_clause(plan)
            if not from_clause:
                return {
                    "status": "cannot_generate",
                    "reason": "No se pudieron identificar tablas base",
                    "suggestions": [
                        "Especificar qué tablas quieres consultar",
                        "Usar nombres de tablas específicos"
                    ]
                }
            
            # 🔧 FASE 5: 4. Generar JOINs
            join_clause = self._generate_join_clause(plan)
            
            # 🔧 FASE 5: 5. Generar WHERE
            where_clause = self._generate_where_clause(plan)
            
            # 🔧 FASE 5: 6. Generar ORDER BY
            order_clause = self._generate_order_clause(plan)
            
            # 🔧 FASE 5: 7. Generar LIMIT
            limit_clause = self._generate_limit_clause(plan)
            
            # 🔧 FASE 5: 8. Construir SQL completo
            sql_parts = [select_clause, from_clause]
            
            if join_clause:
                sql_parts.append(join_clause)
            
            if where_clause:
                sql_parts.append(where_clause)
            
            if order_clause:
                sql_parts.append(order_clause)
            
            if limit_clause:
                sql_parts.append(limit_clause)
            
            # 🔧 FASE 5: Unir todas las cláusulas
            sql = " ".join(sql_parts) + ";"
            
            # 🔧 FASE 5: Validar SQL generado
            if not self._validate_generated_sql(sql):
                return {
                    "status": "cannot_generate",
                    "reason": "SQL generado contiene elementos prohibidos",
                    "suggestions": [
                        "Reformular la consulta de forma más específica",
                        "Evitar comandos de modificación de datos"
                    ]
                }
            
            # 🔧 FASE 5: Formatear SQL
            sql_formatted = self._format_sql(sql)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                "status": "success",
                "sql": sql,
                "sql_formatted": sql_formatted,
                "plan_used": plan,
                "generation_time_ms": processing_time,
                "sql_metadata": {
                    "tables_used": plan.get('base_tables', []),
                    "joins_count": len(plan.get('joins', [])),
                    "filters_count": len(plan.get('filters', [])),
                    "projections_count": len(plan.get('projections', [])),
                    "has_ordering": bool(order_clause),
                    "has_limit": bool(limit_clause)
                }
            }
            
            self.logger.info(f"[SQLGeneratorService] ✅ SQL generado exitosamente en {processing_time}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando SQL: {e}")
            return {
                "status": "error",
                "reason": f"Error interno generando SQL: {str(e)}",
                "suggestions": [
                    "Intentar reformular la consulta",
                    "Contactar soporte si el problema persiste"
                ]
            }
    
    def _validate_plan(self, plan: Dict[str, Any]) -> bool:
        """Valida que el plan sea válido para generar SQL"""
        try:
            # 🔧 FASE 5: Verificar campos requeridos
            required_fields = ['base_tables', 'projections']
            
            for field in required_fields:
                if field not in plan:
                    self.logger.warning(f"[SQLGeneratorService] ⚠️ Campo requerido faltante: {field}")
                    return False
            
            # 🔧 FASE 5: Verificar que haya tablas base
            base_tables = plan.get('base_tables', [])
            if not base_tables:
                self.logger.warning("[SQLGeneratorService] ⚠️ No hay tablas base en el plan")
                return False
            
            # 🔧 FASE 5: Verificar que haya proyecciones
            projections = plan.get('projections', [])
            if not projections:
                self.logger.warning("[SQLGeneratorService] ⚠️ No hay proyecciones en el plan")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error validando plan: {e}")
            return False
    
    def _generate_select_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula SELECT"""
        try:
            projections = plan.get('projections', [])
            
            if not projections:
                return "SELECT *"
            
            # 🔧 FASE 5: Construir lista de columnas
            select_columns = []
            for proj in projections:
                column = proj.get('column', '')
                alias = proj.get('alias', '')
                
                if column:
                    if alias and alias != column.split('.')[-1]:
                        select_columns.append(f"{column} AS {alias}")
                    else:
                        select_columns.append(column)
            
            if not select_columns:
                return "SELECT *"
            
            return f"SELECT {', '.join(select_columns)}"
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando SELECT: {e}")
            return "SELECT *"
    
    def _generate_from_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula FROM"""
        try:
            base_tables = plan.get('base_tables', [])
            
            if not base_tables:
                return ""
            
            # 🔧 FASE 5: Usar la primera tabla como tabla principal
            main_table = base_tables[0]
            return f"FROM {main_table}"
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando FROM: {e}")
            return ""
    
    def _generate_join_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula JOIN"""
        try:
            joins = plan.get('joins', [])
            
            if not joins:
                return ""
            
            # 🔧 FASE 5: Generar JOINs
            join_clauses = []
            for join_info in joins:
                source_table = join_info.get('source_table', '')
                target_table = join_info.get('target_table', '')
                source_column = join_info.get('source_column', '')
                target_column = join_info.get('target_column', '')
                join_type = join_info.get('join_type', 'INNER')
                
                if source_table and target_table and source_column and target_column:
                    join_clause = f"{join_type} JOIN {target_table} ON {source_table}.{source_column} = {target_table}.{target_column}"
                    join_clauses.append(join_clause)
            
            return " ".join(join_clauses)
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando JOIN: {e}")
            return ""
    
    def _generate_where_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula WHERE"""
        try:
            filters = plan.get('filters', [])
            
            if not filters:
                return ""
            
            # 🔧 FASE 5: Generar filtros básicos
            where_conditions = []
            for filter_info in filters:
                column = filter_info.get('column', '')
                operator = filter_info.get('suggested_operator', '=')
                value = filter_info.get('suggested_value', 'placeholder')
                
                if column:
                    if value == 'placeholder':
                        # 🔧 FASE 5: Generar filtro genérico
                        where_conditions.append(f"{column} IS NOT NULL")
                    else:
                        where_conditions.append(f"{column} {operator} {value}")
            
            if not where_conditions:
                return ""
            
            return f"WHERE {' AND '.join(where_conditions)}"
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando WHERE: {e}")
            return ""
    
    def _generate_order_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula ORDER BY"""
        try:
            ordering = plan.get('ordering')
            
            if not ordering:
                return ""
            
            column = ordering.get('column', '')
            direction = ordering.get('direction', 'ASC')
            
            if column:
                return f"ORDER BY {column} {direction}"
            
            return ""
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando ORDER BY: {e}")
            return ""
    
    def _generate_limit_clause(self, plan: Dict[str, Any]) -> str:
        """Genera la cláusula LIMIT"""
        try:
            # 🔧 FASE 5: Usar límite por defecto
            limit = self.default_limit
            
            # 🔧 FASE 5: Verificar si hay límite en el plan
            if 'limit' in plan:
                plan_limit = plan.get('limit')
                if plan_limit and isinstance(plan_limit, int):
                    limit = min(plan_limit, self.max_limit)
            
            return f"LIMIT {limit}"
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error generando LIMIT: {e}")
            return f"LIMIT {self.default_limit}"
    
    def _validate_generated_sql(self, sql: str) -> bool:
        """Valida que el SQL generado no contenga elementos prohibidos"""
        try:
            sql_upper = sql.upper()
            
            # 🔧 FASE 5: Verificar palabras clave prohibidas
            for keyword in self.forbidden_keywords:
                if keyword in sql_upper:
                    self.logger.warning(f"[SQLGeneratorService] ⚠️ Palabra clave prohibida detectada: {keyword}")
                    return False
            
            # 🔧 FASE 5: Verificar que solo sea SELECT
            if not sql_upper.strip().startswith('SELECT'):
                self.logger.warning("[SQLGeneratorService] ⚠️ SQL no comienza con SELECT")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error validando SQL: {e}")
            return False
    
    def _format_sql(self, sql: str) -> str:
        """Formatea el SQL para mejor legibilidad"""
        try:
            # 🔧 FASE 5: Formateo básico
            formatted = sql.replace('SELECT', '\nSELECT')
            formatted = formatted.replace('FROM', '\nFROM')
            formatted = formatted.replace('JOIN', '\nJOIN')
            formatted = formatted.replace('WHERE', '\nWHERE')
            formatted = formatted.replace('ORDER BY', '\nORDER BY')
            formatted = formatted.replace('LIMIT', '\nLIMIT')
            
            # 🔧 FASE 5: Limpiar espacios extra
            formatted = '\n'.join(line.strip() for line in formatted.split('\n') if line.strip())
            
            return formatted
            
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error formateando SQL: {e}")
            return sql
    
    async def explain_sql(self, sql: str, plan: Dict[str, Any]) -> str:
        """Genera una explicación del SQL generado"""
        try:
            explanation_parts = []
            
            # 🔧 FASE 5: Explicar tablas usadas
            tables = plan.get('base_tables', [])
            if tables:
                explanation_parts.append(f"📊 **Tablas consultadas**: {', '.join(tables)}")
            
            # 🔧 FASE 5: Explicar joins
            joins = plan.get('joins', [])
            if joins:
                join_descriptions = []
                for join in joins:
                    desc = f"{join['source_table']} → {join['target_table']} ({join['type']})"
                    join_descriptions.append(desc)
                explanation_parts.append(f"🔗 **Joins realizados**: {', '.join(join_descriptions)}")
            
            # 🔧 FASE 5: Explicar filtros
            filters = plan.get('filters', [])
            if filters:
                filter_descriptions = [f"{f['column']}" for f in filters]
                explanation_parts.append(f"🔍 **Filtros aplicados**: {', '.join(filter_descriptions)}")
            
            # 🔧 FASE 5: Explicar proyecciones
            projections = plan.get('projections', [])
            if projections:
                proj_descriptions = [f"{p['column']}" for p in projections]
                explanation_parts.append(f"📋 **Columnas seleccionadas**: {', '.join(proj_descriptions)}")
            
            # 🔧 FASE 5: Explicar ordenamiento
            ordering = plan.get('ordering')
            if ordering:
                explanation_parts.append(f"📈 **Ordenamiento**: {ordering['column']} {ordering['direction']}")
            
            # 🔧 FASE 5: Explicar límite
            explanation_parts.append(f"⏱️ **Límite**: {self.default_limit} filas máximo")
            
            if explanation_parts:
                return "\n\n".join(explanation_parts)
            else:
                return "Consulta SQL generada automáticamente basada en el plan de consulta."
                
        except Exception as e:
            self.logger.error(f"[SQLGeneratorService] ❌ Error explicando SQL: {e}")
            return "Error generando explicación del SQL."
