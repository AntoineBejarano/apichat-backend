# app/services/query_validation_service.py
"""
QueryValidationService - Nivel Unicornio 🦄
────────────────────────────────────────────
Servicio de validación inteligente de queries SQL.
Combina validación sintáctica, semántica y de rendimiento.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
import sqlparse
from sqlparse.sql import Token, TokenList, Identifier, Function, Where, Comparison

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de validación de query"""
    is_valid: bool
    confidence_score: float
    errors: List[str]
    warnings: List[str]
    suggestions: List[str]
    performance_score: float
    security_score: float
    complexity_level: str


@dataclass
class QueryAnalysis:
    """Análisis detallado de una query"""
    tables_used: List[str]
    columns_used: List[str]
    functions_used: List[str]
    joins_count: int
    where_conditions: List[str]
    aggregation_functions: List[str]
    subqueries_count: int
    estimated_complexity: str


class QueryValidationService:
    """
    Servicio de validación inteligente de queries SQL.
    """
    
    def __init__(self):
        self.validation_rules = self._load_validation_rules()
        self.performance_patterns = self._load_performance_patterns()
        self.security_patterns = self._load_security_patterns()
        self.validation_stats = {
            "total_validations": 0,
            "valid_queries": 0,
            "invalid_queries": 0,
            "avg_confidence": 0.0,
            "avg_performance_score": 0.0
        }
        
        logger.info("[QueryValidationService] 🦄 Inicializado con validación inteligente")
    
    def _load_validation_rules(self) -> Dict[str, Any]:
        """Cargar reglas de validación"""
        return {
            "syntax_rules": {
                "required_keywords": ["SELECT", "FROM"],
                "forbidden_keywords": ["DROP", "DELETE", "TRUNCATE", "ALTER"],
                "balanced_parentheses": True,
                "valid_operators": ["=", "!=", "<", ">", "<=", ">=", "LIKE", "IN", "BETWEEN"]
            },
            "semantic_rules": {
                "max_tables": 10,
                "max_columns_per_select": 50,
                "max_where_conditions": 20,
                "max_joins": 8
            },
            "performance_rules": {
                "max_subqueries": 3,
                "max_nested_levels": 2,
                "preferred_functions": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
                "avoid_functions": ["SELECT *", "CROSS JOIN"]
            }
        }
    
    def _load_performance_patterns(self) -> Dict[str, List[str]]:
        """Cargar patrones de performance"""
        return {
            "good_patterns": [
                "WHERE id =",
                "INDEX",
                "LIMIT",
                "ORDER BY id",
                "GROUP BY"
            ],
            "bad_patterns": [
                "SELECT *",
                "CROSS JOIN",
                "WHERE column LIKE '%value%'",
                "ORDER BY RAND()",
                "SELECT DISTINCT *"
            ]
        }
    
    def _load_security_patterns(self) -> Dict[str, List[str]]:
        """Cargar patrones de seguridad"""
        return {
            "dangerous_patterns": [
                "DROP",
                "DELETE FROM",
                "TRUNCATE",
                "ALTER TABLE",
                "CREATE TABLE",
                "INSERT INTO"
            ],
            "injection_patterns": [
                "'; DROP",
                "'; INSERT",
                "'; UPDATE",
                "UNION SELECT",
                "OR 1=1",
                "OR '1'='1'"
            ]
        }
    
    def validate_query(
        self, 
        query: str, 
        schema_context: Dict[str, Any],
        user_permissions: List[str] = None
    ) -> ValidationResult:
        """
        Validar una query SQL completa.
        
        Args:
            query: Query SQL a validar
            schema_context: Contexto del esquema
            user_permissions: Permisos del usuario
            
        Returns:
            Resultado de validación detallado
        """
        start_time = datetime.now()
        
        try:
            # 1. Validación sintáctica básica
            syntax_valid, syntax_errors = self._validate_syntax(query)
            
            # 2. Análisis de la query
            query_analysis = self._analyze_query(query)
            
            # 3. Validación semántica
            semantic_valid, semantic_errors = self._validate_semantic(query_analysis, schema_context)
            
            # 4. Validación de performance
            performance_score, performance_warnings = self._validate_performance(query, query_analysis)
            
            # 5. Validación de seguridad
            security_score, security_errors = self._validate_security(query, user_permissions)
            
            # 6. Calcular score de confianza
            confidence_score = self._calculate_confidence_score(
                syntax_valid, semantic_valid, performance_score, security_score
            )
            
            # 7. Generar sugerencias
            suggestions = self._generate_suggestions(query_analysis, performance_warnings)
            
            # 8. Determinar nivel de complejidad
            complexity_level = self._determine_complexity(query_analysis)
            
            # Consolidar errores y warnings
            all_errors = syntax_errors + semantic_errors + security_errors
            all_warnings = performance_warnings
            
            # Determinar si la query es válida
            is_valid = syntax_valid and semantic_valid and security_score > 0.5
            
            validation_result = ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                errors=all_errors,
                warnings=all_warnings,
                suggestions=suggestions,
                performance_score=performance_score,
                security_score=security_score,
                complexity_level=complexity_level
            )
            
            # Actualizar estadísticas
            self._update_stats(validation_result)
            
            response_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[QueryValidationService] ✅ Query validada en {response_time:.2f}s (confianza: {confidence_score:.2f})")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"[QueryValidationService] ❌ Error validando query: {e}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                errors=[f"Error de validación: {str(e)}"],
                warnings=[],
                suggestions=["Revisar sintaxis de la query"],
                performance_score=0.0,
                security_score=0.0,
                complexity_level="unknown"
            )
    
    def _validate_syntax(self, query: str) -> Tuple[bool, List[str]]:
        """Validar sintaxis básica de la query"""
        errors = []
        
        try:
            # Parsear la query
            parsed = sqlparse.parse(query)
            
            # Verificar que se puede parsear
            if not parsed:
                errors.append("No se pudo parsear la query")
                return False, errors
            
            # Verificar keywords requeridos
            query_upper = query.upper()
            for keyword in self.validation_rules["syntax_rules"]["required_keywords"]:
                if keyword not in query_upper:
                    errors.append(f"Falta keyword requerido: {keyword}")
            
            # Verificar keywords prohibidos
            for keyword in self.validation_rules["syntax_rules"]["forbidden_keywords"]:
                if keyword in query_upper:
                    errors.append(f"Keyword prohibido detectado: {keyword}")
            
            # Verificar paréntesis balanceados
            if self.validation_rules["syntax_rules"]["balanced_parentheses"]:
                if query.count('(') != query.count(')'):
                    errors.append("Paréntesis no balanceados")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Error de sintaxis: {str(e)}")
            return False, errors
    
    def _analyze_query(self, query: str) -> QueryAnalysis:
        """Analizar la query para extraer información detallada"""
        try:
            parsed = sqlparse.parse(query)[0]
            
            # Extraer tablas usadas
            tables_used = self._extract_tables(parsed)
            
            # Extraer columnas usadas
            columns_used = self._extract_columns(parsed)
            
            # Extraer funciones usadas
            functions_used = self._extract_functions(parsed)
            
            # Contar JOINs
            joins_count = query.upper().count("JOIN")
            
            # Extraer condiciones WHERE
            where_conditions = self._extract_where_conditions(parsed)
            
            # Extraer funciones de agregación
            aggregation_functions = self._extract_aggregation_functions(parsed)
            
            # Contar subqueries
            subqueries_count = query.count("SELECT") - 1  # Aproximación
            
            # Determinar complejidad estimada
            estimated_complexity = self._estimate_complexity(
                len(tables_used), joins_count, len(where_conditions), subqueries_count
            )
            
            return QueryAnalysis(
                tables_used=tables_used,
                columns_used=columns_used,
                functions_used=functions_used,
                joins_count=joins_count,
                where_conditions=where_conditions,
                aggregation_functions=aggregation_functions,
                subqueries_count=subqueries_count,
                estimated_complexity=estimated_complexity
            )
            
        except Exception as e:
            logger.error(f"[QueryValidationService] ❌ Error analizando query: {e}")
            return QueryAnalysis(
                tables_used=[],
                columns_used=[],
                functions_used=[],
                joins_count=0,
                where_conditions=[],
                aggregation_functions=[],
                subqueries_count=0,
                estimated_complexity="unknown"
            )
    
    def _extract_tables(self, parsed_query) -> List[str]:
        """Extraer tablas mencionadas en la query"""
        tables = []
        
        def extract_from_tokens(tokens):
            for token in tokens:
                if hasattr(token, 'tokens'):
                    extract_from_tokens(token.tokens)
                elif token.ttype is None and token.value.upper() in ['FROM', 'JOIN']:
                    # Buscar el siguiente token como tabla
                    pass  # Implementación simplificada
        
        # Implementación simplificada - buscar patrones
        query_str = str(parsed_query).upper()
        table_patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'UPDATE\s+(\w+)',
            r'INSERT\s+INTO\s+(\w+)'
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, query_str)
            tables.extend(matches)
        
        return list(set(tables))
    
    def _extract_columns(self, parsed_query) -> List[str]:
        """Extraer columnas mencionadas en la query"""
        columns = []
        
        # Buscar patrones de columnas
        query_str = str(parsed_query)
        column_patterns = [
            r'SELECT\s+(.*?)\s+FROM',
            r'WHERE\s+(\w+)\s*[=<>]',
            r'ORDER\s+BY\s+(\w+)',
            r'GROUP\s+BY\s+(\w+)'
        ]
        
        for pattern in column_patterns:
            matches = re.findall(pattern, query_str, re.IGNORECASE)
            for match in matches:
                # Separar columnas por comas
                cols = [col.strip() for col in match.split(',')]
                columns.extend(cols)
        
        return list(set(columns))
    
    def _extract_functions(self, parsed_query) -> List[str]:
        """Extraer funciones usadas en la query"""
        functions = []
        
        query_str = str(parsed_query).upper()
        function_patterns = [
            r'COUNT\s*\(',
            r'SUM\s*\(',
            r'AVG\s*\(',
            r'MAX\s*\(',
            r'MIN\s*\(',
            r'CONCAT\s*\(',
            r'DATE\s*\('
        ]
        
        for pattern in function_patterns:
            if re.search(pattern, query_str):
                func_name = re.search(pattern, query_str).group().split('(')[0]
                functions.append(func_name)
        
        return functions
    
    def _extract_where_conditions(self, parsed_query) -> List[str]:
        """Extraer condiciones WHERE de la query"""
        conditions = []
        
        query_str = str(parsed_query)
        where_pattern = r'WHERE\s+(.*?)(?:\s+ORDER\s+BY|\s+GROUP\s+BY|\s+LIMIT|$)'
        where_match = re.search(where_pattern, query_str, re.IGNORECASE)
        
        if where_match:
            where_clause = where_match.group(1)
            # Separar por AND/OR
            conditions = re.split(r'\s+AND\s+|\s+OR\s+', where_clause, flags=re.IGNORECASE)
            conditions = [cond.strip() for cond in conditions if cond.strip()]
        
        return conditions
    
    def _extract_aggregation_functions(self, parsed_query) -> List[str]:
        """Extraer funciones de agregación"""
        aggregations = []
        
        query_str = str(parsed_query).upper()
        agg_patterns = ['COUNT', 'SUM', 'AVG', 'MAX', 'MIN']
        
        for pattern in agg_patterns:
            if f"{pattern}(" in query_str:
                aggregations.append(pattern)
        
        return aggregations
    
    def _estimate_complexity(self, tables: int, joins: int, conditions: int, subqueries: int) -> str:
        """Estimar complejidad de la query"""
        complexity_score = tables * 0.5 + joins * 1.0 + conditions * 0.3 + subqueries * 2.0
        
        if complexity_score < 3:
            return "simple"
        elif complexity_score < 7:
            return "medium"
        else:
            return "complex"
    
    def _validate_semantic(self, analysis: QueryAnalysis, schema_context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validar semántica de la query contra el esquema"""
        errors = []
        
        # Verificar límites de complejidad
        if len(analysis.tables_used) > self.validation_rules["semantic_rules"]["max_tables"]:
            errors.append(f"Demasiadas tablas ({len(analysis.tables_used)} > {self.validation_rules['semantic_rules']['max_tables']})")
        
        if len(analysis.columns_used) > self.validation_rules["semantic_rules"]["max_columns_per_select"]:
            errors.append(f"Demasiadas columnas ({len(analysis.columns_used)} > {self.validation_rules['semantic_rules']['max_columns_per_select']})")
        
        if analysis.joins_count > self.validation_rules["semantic_rules"]["max_joins"]:
            errors.append(f"Demasiados JOINs ({analysis.joins_count} > {self.validation_rules['semantic_rules']['max_joins']})")
        
        if len(analysis.where_conditions) > self.validation_rules["semantic_rules"]["max_where_conditions"]:
            errors.append(f"Demasiadas condiciones WHERE ({len(analysis.where_conditions)} > {self.validation_rules['semantic_rules']['max_where_conditions']})")
        
        # Verificar tablas contra esquema
        if schema_context.get("tables"):
            available_tables = set(schema_context["tables"].keys())
            used_tables = set(analysis.tables_used)
            
            invalid_tables = used_tables - available_tables
            if invalid_tables:
                errors.append(f"Tablas no encontradas en esquema: {', '.join(invalid_tables)}")
        
        return len(errors) == 0, errors
    
    def _validate_performance(self, query: str, analysis: QueryAnalysis) -> Tuple[float, List[str]]:
        """Validar performance de la query"""
        warnings = []
        score = 1.0
        
        query_upper = query.upper()
        
        # Verificar patrones malos
        for pattern in self.performance_patterns["bad_patterns"]:
            if pattern.upper() in query_upper:
                warnings.append(f"Patrón de performance problemático: {pattern}")
                score -= 0.2
        
        # Verificar patrones buenos
        for pattern in self.performance_patterns["good_patterns"]:
            if pattern.upper() in query_upper:
                score += 0.1
        
        # Penalizar complejidad alta
        if analysis.estimated_complexity == "complex":
            warnings.append("Query muy compleja - considerar optimización")
            score -= 0.3
        
        if analysis.subqueries_count > self.validation_rules["performance_rules"]["max_subqueries"]:
            warnings.append(f"Demasiadas subqueries ({analysis.subqueries_count})")
            score -= 0.2
        
        # Verificar SELECT *
        if "SELECT *" in query_upper:
            warnings.append("Evitar SELECT * - especificar columnas")
            score -= 0.4
        
        return max(score, 0.0), warnings
    
    def _validate_security(self, query: str, user_permissions: List[str] = None) -> Tuple[float, List[str]]:
        """Validar seguridad de la query"""
        errors = []
        score = 1.0
        
        query_upper = query.upper()
        
        # Verificar patrones peligrosos
        for pattern in self.security_patterns["dangerous_patterns"]:
            if pattern.upper() in query_upper:
                errors.append(f"Operación peligrosa detectada: {pattern}")
                score -= 0.5
        
        # Verificar patrones de inyección
        for pattern in self.security_patterns["injection_patterns"]:
            if pattern.upper() in query_upper:
                errors.append(f"Posible inyección SQL detectada: {pattern}")
                score -= 0.8
        
        # Verificar permisos del usuario
        if user_permissions:
            # Implementar verificación de permisos
            pass
        
        return max(score, 0.0), errors
    
    def _calculate_confidence_score(
        self, 
        syntax_valid: bool, 
        semantic_valid: bool, 
        performance_score: float, 
        security_score: float
    ) -> float:
        """Calcular score de confianza general"""
        score = 0.0
        
        if syntax_valid:
            score += 0.3
        if semantic_valid:
            score += 0.3
        score += performance_score * 0.2
        score += security_score * 0.2
        
        return min(score, 1.0)
    
    def _generate_suggestions(self, analysis: QueryAnalysis, warnings: List[str]) -> List[str]:
        """Generar sugerencias de optimización"""
        suggestions = []
        
        # Sugerencias basadas en análisis
        if analysis.estimated_complexity == "complex":
            suggestions.append("💡 Considerar dividir la query en partes más simples")
        
        if analysis.joins_count > 5:
            suggestions.append("🔗 Demasiados JOINs - revisar normalización")
        
        if "SELECT *" in str(analysis):
            suggestions.append("📋 Especificar columnas en lugar de usar SELECT *")
        
        if analysis.subqueries_count > 2:
            suggestions.append("🔄 Considerar usar CTEs en lugar de subqueries")
        
        # Sugerencias basadas en warnings
        for warning in warnings:
            if "performance" in warning.lower():
                suggestions.append("⚡ Optimizar para mejor rendimiento")
            elif "complex" in warning.lower():
                suggestions.append("🧠 Simplificar la lógica de la query")
        
        return suggestions
    
    def _determine_complexity(self, analysis: QueryAnalysis) -> str:
        """Determinar nivel de complejidad"""
        return analysis.estimated_complexity
    
    def _update_stats(self, result: ValidationResult) -> None:
        """Actualizar estadísticas de validación"""
        self.validation_stats["total_validations"] += 1
        
        if result.is_valid:
            self.validation_stats["valid_queries"] += 1
        else:
            self.validation_stats["invalid_queries"] += 1
        
        # Actualizar promedios
        current_avg = self.validation_stats["avg_confidence"]
        total_validations = self.validation_stats["total_validations"]
        
        self.validation_stats["avg_confidence"] = (
            (current_avg * (total_validations - 1) + result.confidence_score) / total_validations
        )
        
        current_perf_avg = self.validation_stats["avg_performance_score"]
        self.validation_stats["avg_performance_score"] = (
            (current_perf_avg * (total_validations - 1) + result.performance_score) / total_validations
        )
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de validación"""
        return {
            "total_validations": self.validation_stats["total_validations"],
            "valid_queries": self.validation_stats["valid_queries"],
            "invalid_queries": self.validation_stats["invalid_queries"],
            "success_rate": self.validation_stats["valid_queries"] / max(self.validation_stats["total_validations"], 1),
            "avg_confidence": self.validation_stats["avg_confidence"],
            "avg_performance_score": self.validation_stats["avg_performance_score"]
        }
