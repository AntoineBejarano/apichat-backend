#!/usr/bin/env python3
"""
🔍 SQLValidationNode - Validación de SQL con Esquema Real
──────────────────────────────────────────────────────────
Valida que las queries SQL sean seguras y usen tablas reales
de la base de datos para evitar errores y alucinaciones.
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SQLValidationNode:
    """
    🔍 Nodo que valida SQL antes de ejecutar.
    
    Características:
    - Valida que SQL use tablas reales de la DB
    - Previene SQL injection
    - Verifica sintaxis básica
    - Reporta problemas de seguridad
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.schema_service = factory.get_schema_explorer_service()
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        🔍 Valida SQL del plan de ejecución.
        
        Args:
            state: Estado del grafo con plan y esquema
            
        Returns:
            Estado actualizado con validación SQL
        """
        start_time = datetime.now()
        
        try:
            # Extraer información del estado
            execution_plan = state.get("execution_plan", {})
            compact_schemas = state.get("compact_schemas", {})
            
            logger.info(f"[SQLValidationNode] 🔍 Iniciando validación SQL del plan")
            
            # 🛡️ VALIDAR PLAN COMPLETO
            validated_plan = await self._validate_execution_plan(execution_plan, compact_schemas)
            
            # 📊 METADATAS DE VALIDACIÓN
            validation_metadata = {
                "validation_type": "sql_security_and_schema",
                "validation_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "total_steps": len(validated_plan.get("steps", [])),
                "validated_steps": len([s for s in validated_plan.get("steps", []) if s.get("sql_validation") == "passed"]),
                "failed_steps": len([s for s in validated_plan.get("steps", []) if s.get("sql_validation") == "failed"]),
                "security_issues": self._count_security_issues(validated_plan),
                "next_phase": "plan_execution"
            }
            
            logger.info(f"[SQLValidationNode] ✅ Validación SQL completada en {validation_metadata['validation_time_ms']:.1f}ms")
            
            return {
                **state,
                "execution_plan": validated_plan,
                "sql_validation_metadata": validation_metadata,
                "current_phase": "sql_validation_completed"
            }
            
        except Exception as e:
            logger.error(f"[SQLValidationNode] ❌ Error en validación SQL: {e}")
            
            # 🆘 FALLBACK: Marcar todo como no validado
            fallback_plan = self._mark_plan_as_unvalidated(execution_plan)
            
            return {
                **state,
                "execution_plan": fallback_plan,
                "sql_validation_metadata": {
                    "validation_type": "fallback",
                    "validation_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "error": str(e),
                    "next_phase": "fallback_execution"
                },
                "current_phase": "sql_validation_failed"
            }
    
    async def _validate_execution_plan(self, plan: Dict[str, Any], compact_schemas: dict) -> Dict[str, Any]:
        """🔍 Valida cada paso del plan de ejecución."""
        
        if "steps" not in plan:
            return plan
        
        validated_steps = []
        
        for step in plan["steps"]:
            if step.get("action") == "db_query" and step.get("sql"):
                # Validar SQL del paso
                validation_result = await self._validate_sql_step(step["sql"], compact_schemas)
                step["sql_validation"] = validation_result
                
                if validation_result["status"] == "passed":
                    step["validated_sql"] = step["sql"]
                else:
                    step["validated_sql"] = None
                    step["validation_errors"] = validation_result["errors"]
            else:
                # Paso sin SQL, marcar como válido
                step["sql_validation"] = {"status": "no_sql", "message": "No requiere validación SQL"}
            
            validated_steps.append(step)
        
        plan["steps"] = validated_steps
        return plan
    
    async def _validate_sql_step(self, sql: str, compact_schemas: dict) -> Dict[str, Any]:
        """🔍 Valida un paso SQL específico."""
        
        validation_result = {
            "status": "pending",
            "errors": [],
            "warnings": [],
            "security_score": 0.0
        }
        
        try:
            # 🛡️ VALIDACIÓN DE SEGURIDAD
            security_validation = self._validate_sql_security(sql)
            validation_result["security_score"] = security_validation["score"]
            
            if security_validation["score"] < 0.7:
                validation_result["errors"].extend(security_validation["issues"])
                validation_result["status"] = "failed"
                return validation_result
            
            # 🏗️ VALIDACIÓN DE ESQUEMA
            schema_validation = await self._validate_sql_schema(sql, compact_schemas)
            
            if schema_validation["status"] == "failed":
                validation_result["errors"].extend(schema_validation["errors"])
                validation_result["status"] = "failed"
            else:
                validation_result["warnings"].extend(schema_validation["warnings"])
                validation_result["status"] = "passed"
            
            # 📝 VALIDACIÓN DE SINTAXIS
            syntax_validation = self._validate_sql_syntax(sql)
            if syntax_validation["status"] == "failed":
                validation_result["errors"].extend(syntax_validation["errors"])
                validation_result["status"] = "failed"
            
        except Exception as e:
            validation_result["errors"].append(f"Error durante validación: {str(e)}")
            validation_result["status"] = "failed"
        
        return validation_result
    
    def _validate_sql_security(self, sql: str) -> Dict[str, Any]:
        """🛡️ Valida seguridad del SQL (previene SQL injection)."""
        
        security_score = 1.0
        issues = []
        
        # 🚨 PATRONES PELIGROSOS
        dangerous_patterns = [
            r"'.*%s.*'",  # Interpolación de strings
            r"'.*\{.*\}.*'",  # F-strings
            r"'.*\+.*'",  # Concatenación de strings
            r"'.*format\(.*\)",  # Método format
            r"'.*eval\(.*\)",  # Función eval
            r"'.*exec\(.*\)",  # Función exec
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                security_score -= 0.3
                issues.append(f"Patrón peligroso detectado: {pattern}")
        
        # 🚨 PALABRAS CLAVE PELIGROSAS
        dangerous_keywords = [
            "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE"
        ]
        
        sql_upper = sql.upper()
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                # Solo permitir SELECT para consultas de lectura
                if keyword != "SELECT" and "SELECT" not in sql_upper:
                    security_score -= 0.2
                    issues.append(f"Palabra clave peligrosa: {keyword}")
        
        # 🚨 VALIDAR QUE SEA SOLO LECTURA
        if "SELECT" not in sql_upper:
            security_score -= 0.5
            issues.append("Solo se permiten consultas de lectura (SELECT)")
        
        return {
            "score": max(0.0, security_score),
            "issues": issues
        }
    
    async def _validate_sql_schema(self, sql: str, compact_schemas: dict) -> Dict[str, Any]:
        """🏗️ Valida que el SQL use tablas reales del esquema."""
        
        validation_result = {
            "status": "pending",
            "errors": [],
            "warnings": []
        }
        
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
                            elif ' ' in line:
                                # Buscar después de CREATE TABLE
                                parts = line.split()
                                for i, part in enumerate(parts):
                                    if part.upper() == 'TABLE' and i + 1 < len(parts):
                                        table_name = parts[i + 1].strip('`"')
                                        real_tables.add(table_name.lower())
                                        break
            
            # Buscar tablas en el SQL
            sql_lower = sql.lower()
            found_tables = []
            
            for table in real_tables:
                if table in sql_lower:
                    found_tables.append(table)
            
            if not found_tables:
                validation_result["status"] = "failed"
                validation_result["errors"].append("No se encontraron tablas reales en el SQL")
                validation_result["errors"].append(f"Tablas disponibles: {', '.join(list(real_tables)[:10])}")
            else:
                validation_result["status"] = "passed"
                validation_result["warnings"].append(f"Tablas validadas: {', '.join(found_tables)}")
            
        except Exception as e:
            validation_result["status"] = "failed"
            validation_result["errors"].append(f"Error validando esquema: {str(e)}")
        
        return validation_result
    
    def _validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """📝 Valida sintaxis básica del SQL."""
        
        validation_result = {
            "status": "passed",
            "errors": [],
            "warnings": []
        }
        
        try:
            # Verificar que termine con punto y coma
            if not sql.strip().endswith(';'):
                validation_result["warnings"].append("SQL no termina con punto y coma")
            
            # Verificar paréntesis balanceados
            open_parens = sql.count('(')
            close_parens = sql.count(')')
            if open_parens != close_parens:
                validation_result["errors"].append("Paréntesis no balanceados")
                validation_result["status"] = "failed"
            
            # Verificar comillas balanceadas
            single_quotes = sql.count("'")
            double_quotes = sql.count('"')
            if single_quotes % 2 != 0:
                validation_result["warnings"].append("Comillas simples no balanceadas")
            if double_quotes % 2 != 0:
                validation_result["warnings"].append("Comillas dobles no balanceadas")
            
        except Exception as e:
            validation_result["status"] = "failed"
            validation_result["errors"].append(f"Error validando sintaxis: {str(e)}")
        
        return validation_result
    
    def _count_security_issues(self, plan: Dict[str, Any]) -> int:
        """🔢 Cuenta problemas de seguridad en el plan."""
        
        security_issues = 0
        
        for step in plan.get("steps", []):
            validation = step.get("sql_validation", {})
            if validation.get("status") == "failed":
                security_issues += len(validation.get("errors", []))
        
        return security_issues
    
    def _mark_plan_as_unvalidated(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """🆘 Marca todo el plan como no validado en caso de error."""
        
        if "steps" not in plan:
            return plan
        
        for step in plan["steps"]:
            step["sql_validation"] = {
                "status": "unvalidated",
                "message": "No se pudo validar debido a error en el sistema",
                "errors": ["Error del sistema de validación"]
            }
        
        return plan
