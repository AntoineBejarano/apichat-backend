#!/usr/bin/env python3
"""
SQLValidatorService - Servicio de validación SQL para la Fase 5
────────────────────────────────────────────────────────────────
Implementa:
- Validación SQL con parser + catálogo
- Verificación de tablas y columnas
- Validación de joins permitidos
- Sugerencias de corrección
"""

import asyncio
import logging
import time
import re
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class SQLValidatorService:
    """
    Servicio para validar SQL generado contra el catálogo.
    
    Implementa la sexta etapa de la Fase 5:
    - Validación con parser SQL
    - Verificación contra catálogo
    - Validación de relaciones permitidas
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 5: Patrones de validación SQL
        self.sql_patterns = {
            'select': r'SELECT\s+(.+?)\s+FROM',
            'from': r'FROM\s+(\w+)',
            'join': r'JOIN\s+(\w+)\s+ON',
            'where': r'WHERE\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)',
            'order_by': r'ORDER\s+BY\s+(.+?)(?:\s+LIMIT|$)',
            'limit': r'LIMIT\s+(\d+)'
        }
        
        # 🔧 FASE 5: Palabras clave SQL permitidas
        self.allowed_keywords = [
            'SELECT', 'FROM', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
            'WHERE', 'AND', 'OR', 'NOT', 'ORDER', 'BY', 'ASC', 'DESC',
            'LIMIT', 'OFFSET', 'AS', 'ON', 'IS', 'NULL', 'LIKE', 'IN',
            'BETWEEN', 'EXISTS', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX'
        ]
    
    async def validate_sql(
        self, 
        sql: str, 
        context: Dict[str, Any], 
        plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Valida SQL generado contra el catálogo.
        
        Args:
            sql: SQL a validar
            context: Contexto completo
            plan: Plan de consulta usado
            
        Returns:
            Resultado de la validación
        """
        try:
            start_time = time.time()
            self.logger.info(f"[SQLValidatorService] ✅ Validando SQL: '{sql[:50]}...'")
            
            # 🔧 FASE 5: 1. Validación básica de sintaxis
            syntax_validation = self._validate_sql_syntax(sql)
            if not syntax_validation['is_valid']:
                return {
                    "is_valid": False,
                    "errors": syntax_validation['errors'],
                    "suggestions": syntax_validation['suggestions'],
                    "validation_time_ms": int((time.time() - start_time) * 1000)
                }
            
            # 🔧 FASE 5: 2. Extraer elementos del SQL
            sql_elements = self._extract_sql_elements(sql)
            
            # 🔧 FASE 5: 3. Validar tablas contra catálogo
            table_validation = await self._validate_tables(sql_elements, context)
            
            # 🔧 FASE 5: 4. Validar columnas contra catálogo
            column_validation = await self._validate_columns(sql_elements, context)
            
            # 🔧 FASE 5: 5. Validar joins contra plan
            join_validation = await self._validate_joins(sql_elements, plan)
            
            # 🔧 FASE 5: 6. Consolidar resultados
            all_errors = []
            all_suggestions = []
            
            if not table_validation['is_valid']:
                all_errors.extend(table_validation['errors'])
                all_suggestions.extend(table_validation['suggestions'])
            
            if not column_validation['is_valid']:
                all_errors.extend(column_validation['errors'])
                all_suggestions.extend(column_validation['suggestions'])
            
            if not join_validation['is_valid']:
                all_errors.extend(join_validation['errors'])
                all_suggestions.extend(join_validation['suggestions'])
            
            # 🔧 FASE 5: 7. Determinar validez general
            is_valid = (
                syntax_validation['is_valid'] and
                table_validation['is_valid'] and
                column_validation['is_valid'] and
                join_validation['is_valid']
            )
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                "is_valid": is_valid,
                "errors": all_errors,
                "suggestions": all_suggestions,
                "validation_details": {
                    "syntax": syntax_validation,
                    "tables": table_validation,
                    "columns": column_validation,
                    "joins": join_validation
                },
                "sql_elements": sql_elements,
                "validation_time_ms": processing_time
            }
            
            if is_valid:
                self.logger.info(f"[SQLValidatorService] ✅ SQL validado exitosamente en {processing_time}ms")
            else:
                self.logger.warning(f"[SQLValidatorService] ⚠️ SQL tiene {len(all_errors)} errores de validación")
            
            return result
            
        except Exception as e:
            self.logger.error(f"[SQLValidatorService] ❌ Error validando SQL: {e}")
            return {
                "is_valid": False,
                "errors": [f"Error interno de validación: {str(e)}"],
                "suggestions": ["Contactar soporte si el problema persiste"],
                "validation_time_ms": 0
            }
    
    def _validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """Valida la sintaxis básica del SQL"""
        try:
            errors = []
            suggestions = []
            
            # 🔧 FASE 5: Verificar que comience con SELECT
            if not sql.strip().upper().startswith('SELECT'):
                errors.append("SQL debe comenzar con SELECT")
                suggestions.append("Asegúrate de que la consulta sea de solo lectura")
            
            # 🔧 FASE 5: Verificar que termine con punto y coma
            if not sql.strip().endswith(';'):
                errors.append("SQL debe terminar con punto y coma (;)")
                suggestions.append("Agrega ';' al final de la consulta")
            
            # 🔧 FASE 5: Verificar palabras clave prohibidas
            sql_upper = sql.upper()
            forbidden_keywords = [
                'DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE',
                'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'xp_', 'sp_'
            ]
            
            for keyword in forbidden_keywords:
                if keyword in sql_upper:
                    errors.append(f"Palabra clave prohibida: {keyword}")
                    suggestions.append("Solo se permiten consultas SELECT de solo lectura")
            
            # 🔧 FASE 5: Verificar estructura básica
            if 'FROM' not in sql_upper:
                errors.append("SQL debe contener cláusula FROM")
                suggestions.append("Agrega la tabla de la que quieres obtener datos")
            
            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "suggestions": suggestions
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Error validando sintaxis: {str(e)}"],
                "suggestions": ["Error interno de validación"]
            }
    
    def _extract_sql_elements(self, sql: str) -> Dict[str, Any]:
        """Extrae elementos del SQL para validación"""
        try:
            sql_upper = sql.upper()
            elements = {}
            
            # 🔧 FASE 5: Extraer tablas
            from_match = re.search(self.sql_patterns['from'], sql_upper)
            if from_match:
                elements['tables'] = [from_match.group(1)]
            
            # 🔧 FASE 5: Extraer JOINs
            join_matches = re.findall(self.sql_patterns['join'], sql_upper)
            if join_matches:
                if 'tables' not in elements:
                    elements['tables'] = []
                elements['tables'].extend(join_matches)
            
            # 🔧 FASE 5: Extraer columnas del SELECT
            select_match = re.search(self.sql_patterns['select'], sql_upper)
            if select_match:
                select_clause = select_match.group(1)
                # Parsear columnas básico
                columns = []
                for col in select_clause.split(','):
                    col = col.strip()
                    if 'AS' in col:
                        col = col.split('AS')[0].strip()
                    if '.' in col:
                        col = col.split('.')[1]
                    columns.append(col)
                elements['columns'] = columns
            
            # 🔧 FASE 5: Extraer condiciones WHERE
            where_match = re.search(self.sql_patterns['where'], sql_upper)
            if where_match:
                where_clause = where_match.group(1)
                # Extraer columnas mencionadas en WHERE
                where_columns = []
                for word in where_clause.split():
                    if '.' in word and word.count('.') == 1:
                        col = word.split('.')[1]
                        where_columns.append(col)
                elements['where_columns'] = where_columns
            
            # 🔧 FASE 5: Extraer ORDER BY
            order_match = re.search(self.sql_patterns['order_by'], sql_upper)
            if order_match:
                order_clause = order_match.group(1)
                if '.' in order_clause:
                    col = order_clause.split('.')[1]
                    elements['order_column'] = col
            
            # 🔧 FASE 5: Extraer LIMIT
            limit_match = re.search(self.sql_patterns['limit'], sql_upper)
            if limit_match:
                elements['limit'] = int(limit_match.group(1))
            
            return elements
            
        except Exception as e:
            self.logger.error(f"[SQLValidatorService] ❌ Error extrayendo elementos SQL: {e}")
            return {}
    
    async def _validate_tables(self, sql_elements: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que las tablas existan en el catálogo"""
        try:
            errors = []
            suggestions = []
            
            schema = context.get('schema', {})
            available_tables = set(schema.get('tables', {}).keys())
            
            if 'tables' not in sql_elements:
                return {
                    "is_valid": False,
                    "errors": ["No se pudieron identificar tablas en el SQL"],
                    "suggestions": ["Verificar que el SQL contenga cláusula FROM"]
                }
            
            sql_tables = set(sql_elements['tables'])
            missing_tables = sql_tables - available_tables
            
            if missing_tables:
                errors.append(f"Tablas no encontradas en el catálogo: {', '.join(missing_tables)}")
                suggestions.append(f"Tablas disponibles: {', '.join(sorted(available_tables))}")
            
            return {
                "is_valid": len(missing_tables) == 0,
                "errors": errors,
                "suggestions": suggestions,
                "tables_found": len(sql_tables - missing_tables),
                "tables_missing": len(missing_tables)
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Error validando tablas: {str(e)}"],
                "suggestions": ["Error interno de validación"]
            }
    
    async def _validate_columns(self, sql_elements: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que las columnas existan en las tablas"""
        try:
            errors = []
            suggestions = []
            
            schema = context.get('schema', {})
            tables = schema.get('tables', {})
            
            if 'columns' not in sql_elements:
                return {
                    "is_valid": True,  # SELECT * es válido
                    "errors": [],
                    "suggestions": [],
                    "columns_validated": 0
                }
            
            # 🔧 FASE 5: Validar columnas del SELECT
            sql_columns = sql_elements.get('columns', [])
            if '*' in sql_columns:
                return {
                    "is_valid": True,  # SELECT * es válido
                    "errors": [],
                    "suggestions": [],
                    "columns_validated": 0
                }
            
            # 🔧 FASE 5: Validar columnas específicas
            invalid_columns = []
            for col in sql_columns:
                col_found = False
                for table_name, table_info in tables.items():
                    table_columns = table_info.get('columns', {})
                    if col in table_columns:
                        col_found = True
                        break
                
                if not col_found:
                    invalid_columns.append(col)
            
            if invalid_columns:
                errors.append(f"Columnas no encontradas: {', '.join(invalid_columns)}")
                suggestions.append("Verificar nombres de columnas en el catálogo")
            
            # 🔧 FASE 5: Validar columnas del WHERE
            where_columns = sql_elements.get('where_columns', [])
            for col in where_columns:
                col_found = False
                for table_name, table_info in tables.items():
                    table_columns = table_info.get('columns', {})
                    if col in table_columns:
                        col_found = True
                        break
                
                if not col_found:
                    invalid_columns.append(col)
            
            return {
                "is_valid": len(invalid_columns) == 0,
                "errors": errors,
                "suggestions": suggestions,
                "columns_validated": len(sql_columns) + len(where_columns),
                "columns_invalid": len(invalid_columns)
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Error validando columnas: {str(e)}"],
                "suggestions": ["Error interno de validación"]
            }
    
    async def _validate_joins(self, sql_elements: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que los JOINs sean permitidos según el plan"""
        try:
            errors = []
            suggestions = []
            
            if 'tables' not in sql_elements or len(sql_elements['tables']) <= 1:
                return {
                    "is_valid": True,  # No hay JOINs
                    "errors": [],
                    "suggestions": [],
                    "joins_validated": 0
                }
            
            # 🔧 FASE 5: Verificar que las tablas del JOIN estén en el plan
            plan_tables = set(plan.get('base_tables', []))
            sql_tables = set(sql_elements['tables'])
            
            # 🔧 FASE 5: Verificar que todas las tablas del SQL estén en el plan
            extra_tables = sql_tables - plan_tables
            if extra_tables:
                errors.append(f"Tablas no incluidas en el plan: {', '.join(extra_tables)}")
                suggestions.append("Verificar que el plan incluya todas las tablas necesarias")
            
            # 🔧 FASE 5: Verificar que los JOINs del plan cubran las tablas del SQL
            plan_joins = plan.get('joins', [])
            plan_join_tables = set()
            for join in plan_joins:
                plan_join_tables.add(join.get('source_table'))
                plan_join_tables.add(join.get('target_table'))
            
            missing_joins = sql_tables - plan_join_tables
            if missing_joins and len(sql_tables) > 1:
                errors.append(f"Faltan JOINs para conectar las tablas: {', '.join(missing_joins)}")
                suggestions.append("Verificar que el plan incluya todos los JOINs necesarios")
            
            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "suggestions": suggestions,
                "joins_validated": len(plan_joins),
                "tables_in_plan": len(plan_tables),
                "tables_in_sql": len(sql_tables)
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Error validando JOINs: {str(e)}"],
                "suggestions": ["Error interno de validación"]
            }
    
    async def generate_validation_report(self, validation_result: Dict[str, Any]) -> str:
        """Genera un reporte de validación legible"""
        try:
            if validation_result.get('is_valid'):
                return "✅ **SQL válido**: La consulta cumple con todos los criterios de validación."
            
            report_parts = ["❌ **SQL inválido**: Se encontraron los siguientes problemas:"]
            
            # 🔧 FASE 5: Errores por categoría
            details = validation_result.get('validation_details', {})
            
            if 'syntax' in details and not details['syntax']['is_valid']:
                report_parts.append("\n🔤 **Errores de sintaxis:**")
                for error in details['syntax']['errors']:
                    report_parts.append(f"  • {error}")
            
            if 'tables' in details and not details['tables']['is_valid']:
                report_parts.append("\n📊 **Errores de tablas:**")
                for error in details['tables']['errors']:
                    report_parts.append(f"  • {error}")
            
            if 'columns' in details and not details['columns']['is_valid']:
                report_parts.append("\n📋 **Errores de columnas:**")
                for error in details['columns']['errors']:
                    report_parts.append(f"  • {error}")
            
            if 'joins' in details and not details['joins']['is_valid']:
                report_parts.append("\n🔗 **Errores de JOINs:**")
                for error in details['joins']['errors']:
                    report_parts.append(f"  • {error}")
            
            # 🔧 FASE 5: Sugerencias generales
            all_suggestions = validation_result.get('suggestions', [])
            if all_suggestions:
                report_parts.append("\n💡 **Sugerencias:**")
                for suggestion in all_suggestions[:5]:  # Limitar a 5 sugerencias
                    report_parts.append(f"  • {suggestion}")
            
            return "\n".join(report_parts)
            
        except Exception as e:
            return f"Error generando reporte de validación: {str(e)}"
