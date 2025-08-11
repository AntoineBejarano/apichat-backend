"""
Servicio de guardrails para operaciones SQL.
Bloquea operaciones destructivas y limita el impacto.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Niveles de riesgo para operaciones SQL."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SQLOperation(str, Enum):
    """Tipos de operaciones SQL."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DROP = "DROP"
    TRUNCATE = "TRUNCATE"
    ALTER = "ALTER"
    CREATE = "CREATE"


class GuardrailViolation(BaseModel):
    """Violación de guardrail detectada."""
    operation: SQLOperation
    risk_level: RiskLevel
    message: str
    blocked: bool = True
    requires_confirmation: bool = False


class SQLGuardrailsService:
    """Servicio para aplicar guardrails de seguridad en operaciones SQL."""
    
    def __init__(self):
        # Operaciones de alto riesgo que siempre requieren confirmación
        self.high_risk_operations = {
            SQLOperation.DELETE,
            SQLOperation.UPDATE,
            SQLOperation.DROP,
            SQLOperation.TRUNCATE,
            SQLOperation.ALTER
        }
        
        # Límites por defecto
        self.default_limits = {
            SQLOperation.DELETE: 100,  # Máximo 100 filas eliminadas
            SQLOperation.UPDATE: 1000,  # Máximo 1000 filas actualizadas
            SQLOperation.SELECT: 10000,  # Máximo 10k filas retornadas
        }
        
        # Patrones peligrosos
        self.dangerous_patterns = [
            r"DELETE\s+FROM\s+\w+\s*(?!WHERE)",  # DELETE sin WHERE
            r"UPDATE\s+\w+\s+SET\s+(?!WHERE)",   # UPDATE sin WHERE
            r"DROP\s+(TABLE|DATABASE|SCHEMA)",    # DROP de estructuras
            r"TRUNCATE\s+TABLE",                  # TRUNCATE
            r"ALTER\s+TABLE\s+\w+\s+DROP",       # ALTER DROP
        ]
    
    def analyze_sql_query(self, sql_query: str) -> GuardrailViolation:
        """
        Analiza una consulta SQL y retorna información sobre su nivel de riesgo.
        
        Args:
            sql_query: Consulta SQL a analizar
            
        Returns:
            GuardrailViolation con el análisis de riesgo
        """
        if not sql_query:
            return GuardrailViolation(
                operation=SQLOperation.SELECT,
                risk_level=RiskLevel.LOW,
                message="Consulta vacía",
                blocked=False
            )
        
        # Normalizar la consulta
        normalized_query = sql_query.strip().upper()
        
        # Detectar operación principal
        operation = self._detect_operation(normalized_query)
        
        # Verificar patrones peligrosos
        dangerous_violation = self._check_dangerous_patterns(normalized_query)
        if dangerous_violation:
            return dangerous_violation
        
        # Verificar límites de filas
        limit_violation = self._check_row_limits(normalized_query, operation)
        if limit_violation:
            return limit_violation
        
        # Determinar nivel de riesgo
        risk_level = self._determine_risk_level(operation, normalized_query)
        
        # Verificar si requiere confirmación
        requires_confirmation = risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]
        
        return GuardrailViolation(
            operation=operation,
            risk_level=risk_level,
            message=f"Operación {operation.value} analizada",
            blocked=False,
            requires_confirmation=requires_confirmation
        )
    
    def _detect_operation(self, normalized_query: str) -> SQLOperation:
        """Detecta el tipo de operación SQL."""
        if normalized_query.startswith("SELECT"):
            return SQLOperation.SELECT
        elif normalized_query.startswith("INSERT"):
            return SQLOperation.INSERT
        elif normalized_query.startswith("UPDATE"):
            return SQLOperation.UPDATE
        elif normalized_query.startswith("DELETE"):
            return SQLOperation.DELETE
        elif normalized_query.startswith("DROP"):
            return SQLOperation.DROP
        elif normalized_query.startswith("TRUNCATE"):
            return SQLOperation.TRUNCATE
        elif normalized_query.startswith("ALTER"):
            return SQLOperation.ALTER
        elif normalized_query.startswith("CREATE"):
            return SQLOperation.CREATE
        else:
            return SQLOperation.SELECT  # Por defecto
    
    def _check_dangerous_patterns(self, normalized_query: str) -> Optional[GuardrailViolation]:
        """Verifica patrones peligrosos en la consulta."""
        for pattern in self.dangerous_patterns:
            if re.search(pattern, normalized_query, re.IGNORECASE):
                operation = self._detect_operation(normalized_query)
                return GuardrailViolation(
                    operation=operation,
                    risk_level=RiskLevel.HIGH,
                    message=f"Patrón peligroso detectado: {pattern}",
                    blocked=True,
                    requires_confirmation=True
                )
        return None
    
    def _check_row_limits(self, normalized_query: str, operation: SQLOperation) -> Optional[GuardrailViolation]:
        """Verifica límites de filas para operaciones destructivas."""
        if operation not in self.default_limits:
            return None
        
        limit = self.default_limits[operation]
        
        # Buscar LIMIT en la consulta
        limit_match = re.search(r"LIMIT\s+(\d+)", normalized_query, re.IGNORECASE)
        if limit_match:
            requested_limit = int(limit_match.group(1))
            if requested_limit > limit:
                return GuardrailViolation(
                    operation=operation,
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Límite de {requested_limit} filas excede el máximo permitido de {limit}",
                    blocked=False,
                    requires_confirmation=True
                )
        
        # Para operaciones sin LIMIT explícito, verificar si podrían afectar muchas filas
        if operation in [SQLOperation.DELETE, SQLOperation.UPDATE]:
            # Si no hay WHERE específico, podría afectar toda la tabla
            if "WHERE" not in normalized_query:
                return GuardrailViolation(
                    operation=operation,
                    risk_level=RiskLevel.HIGH,
                    message=f"Operación {operation.value} sin cláusula WHERE específica",
                    blocked=True,
                    requires_confirmation=True
                )
        
        return None
    
    def _determine_risk_level(self, operation: SQLOperation, normalized_query: str) -> RiskLevel:
        """Determina el nivel de riesgo de la operación."""
        if operation in self.high_risk_operations:
            return RiskLevel.HIGH
        elif operation == SQLOperation.INSERT:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def get_safe_alternatives(self, violation: GuardrailViolation) -> List[str]:
        """Retorna alternativas seguras para operaciones bloqueadas."""
        alternatives = []
        
        if violation.operation == SQLOperation.DELETE:
            alternatives.extend([
                "Usar SELECT para verificar qué se eliminaría",
                "Añadir cláusula WHERE específica",
                "Usar LIMIT para limitar el número de filas",
                "Considerar soft delete (marcar como inactivo)"
            ])
        
        elif violation.operation == SQLOperation.UPDATE:
            alternatives.extend([
                "Usar SELECT para verificar qué se actualizaría",
                "Añadir cláusula WHERE específica",
                "Usar LIMIT para limitar el número de filas",
                "Verificar con SELECT antes de actualizar"
            ])
        
        elif violation.operation == SQLOperation.DROP:
            alternatives.extend([
                "Usar DROP CASCADE solo si es necesario",
                "Verificar dependencias antes de eliminar",
                "Considerar renombrar en lugar de eliminar",
                "Hacer backup antes de proceder"
            ])
        
        return alternatives
    
    def validate_and_apply_guardrails(
        self, 
        sql_query: str, 
        user_risk_tolerance: RiskLevel = RiskLevel.MEDIUM
    ) -> Tuple[bool, GuardrailViolation, List[str]]:
        """
        Valida y aplica guardrails a una consulta SQL.
        
        Args:
            sql_query: Consulta SQL a validar
            user_risk_tolerance: Tolerancia al riesgo del usuario
            
        Returns:
            Tuple con (permitido, violación, alternativas)
        """
        violation = self.analyze_sql_query(sql_query)
        
        # Si está bloqueado, no permitir
        if violation.blocked:
            alternatives = self.get_safe_alternatives(violation)
            return False, violation, alternatives
        
        # Si requiere confirmación y el usuario tiene baja tolerancia, bloquear
        if (violation.requires_confirmation and 
            user_risk_tolerance == RiskLevel.LOW and 
            violation.risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH]):
            
            violation.blocked = True
            alternatives = self.get_safe_alternatives(violation)
            return False, violation, alternatives
        
        # Permitir la operación
        alternatives = []
        return True, violation, alternatives

    def validate_and_fix_query(
        self,
        query: str,
        user_id: UUID,
        db_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str], bool]:
        """
        Valida y corrige una consulta SQL aplicando guardrails.
        
        Args:
            query: Consulta SQL a validar
            user_id: ID del usuario que ejecuta la consulta
            db_id: ID de la base de datos
            context: Contexto adicional
            
        Returns:
            Tuple con (query_corregida, warnings, es_segura)
        """
        try:
            # Analizar la consulta
            violation = self.analyze_sql_query(query)
            
            warnings = []
            is_safe = True
            
            # Si está bloqueada, marcar como no segura
            if violation.blocked:
                is_safe = False
                warnings.append(f"🚫 Operación bloqueada: {violation.message}")
                return query, warnings, is_safe
            
            # Si requiere confirmación, marcar como no segura
            if violation.requires_confirmation:
                is_safe = False
                warnings.append(f"⏸️ Requiere confirmación: {violation.message}")
                return query, warnings, is_safe
            
            # Aplicar correcciones automáticas si es posible
            fixed_query = self._apply_automatic_fixes(query, violation)
            
            # Si se aplicaron correcciones, añadir warning
            if fixed_query != query:
                warnings.append("🔧 Consulta corregida automáticamente por guardrails")
                warnings.append(f"Original: {query}")
                warnings.append(f"Corregida: {fixed_query}")
            
            # Verificar límites de filas
            row_limit_warning = self._check_row_limits_warning(fixed_query, violation.operation)
            if row_limit_warning:
                warnings.append(row_limit_warning)
            
            return fixed_query, warnings, is_safe
            
        except Exception as e:
            logger.exception(f"❌ Error validando consulta SQL: {e}")
            warnings = [f"❌ Error en validación: {str(e)}"]
            return query, warnings, False
    
    def _apply_automatic_fixes(self, query: str, violation: GuardrailViolation) -> str:
        """Aplica correcciones automáticas a la consulta."""
        fixed_query = query
        
        # Añadir LIMIT si no existe y es una operación de alto riesgo
        if (violation.operation in [SQLOperation.SELECT, SQLOperation.DELETE, SQLOperation.UPDATE] and
            "LIMIT" not in query.upper()):
            
            # Determinar límite apropiado
            if violation.operation == SQLOperation.SELECT:
                limit = self.default_limits.get(SQLOperation.SELECT, 10000)
            elif violation.operation == SQLOperation.DELETE:
                limit = self.default_limits.get(SQLOperation.DELETE, 100)
            elif violation.operation == SQLOperation.UPDATE:
                limit = self.default_limits.get(SQLOperation.UPDATE, 1000)
            else:
                limit = 1000
            
            # Añadir LIMIT al final
            if query.strip().endswith(';'):
                fixed_query = query[:-1] + f" LIMIT {limit};"
            else:
                fixed_query = query + f" LIMIT {limit}"
        
        return fixed_query
    
    def _check_row_limits_warning(self, query: str, operation: SQLOperation) -> Optional[str]:
        """Verifica límites de filas y retorna warning si es necesario."""
        if operation in [SQLOperation.DELETE, SQLOperation.UPDATE]:
            # Verificar si hay WHERE específico
            if "WHERE" not in query.upper():
                return "⚠️ Operación sin cláusula WHERE específica - podría afectar muchas filas"
            
            # Verificar si hay LIMIT
            if "LIMIT" not in query.upper():
                return "⚠️ Operación sin LIMIT - considera añadir límite de filas"
        
        return None
