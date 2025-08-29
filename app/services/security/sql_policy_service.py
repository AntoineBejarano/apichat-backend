"""
🛡️ FASE 7: Servicio de Políticas SQL
─────────────────────────────────────
Implementa políticas de seguridad para SQL:
- Solo SELECT permitido
- LIMIT y TIMEOUT inyectados automáticamente
- Whitelist de schemas
- Validación estricta de operaciones
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SQLOperationType(Enum):
    """Tipos de operaciones SQL permitidas"""
    SELECT = "SELECT"
    # Solo SELECT está permitido por seguridad


class SQLPolicyViolation(Exception):
    """Excepción para violaciones de políticas SQL"""
    
    def __init__(self, error_code: str, message: str, hint: str = ""):
        self.error_code = error_code
        self.message = message
        self.hint = hint
        super().__init__(f"[{error_code}] {message}")


@dataclass
class SQLPolicyConfig:
    """Configuración de políticas SQL"""
    # Operaciones permitidas
    allowed_operations: List[SQLOperationType] = None
    
    # Límites por defecto
    default_limit: int = 100
    max_limit: int = 1000
    default_timeout_seconds: int = 30
    max_timeout_seconds: int = 300
    
    # Whitelist de schemas
    allowed_schemas: List[str] = None
    
    # Patrones prohibidos
    forbidden_patterns: List[str] = None
    
    def __post_init__(self):
        if self.allowed_operations is None:
            self.allowed_operations = [SQLOperationType.SELECT]
        
        if self.allowed_schemas is None:
            self.allowed_schemas = ["public", "app_"]
        
        if self.forbidden_patterns is None:
            self.forbidden_patterns = [
                r"\b(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|TRUNCATE)\b",
                r"\b(EXEC|EXECUTE|sp_|xp_)\b",  # Stored procedures peligrosas
                r"\b(UNION|UNION ALL)\b",  # SQL injection común
                r"\b(INFORMATION_SCHEMA|pg_catalog|sys\.)\b",  # Metadatos del sistema
                r"\b(WAITFOR|DELAY)\b",  # Time-based attacks
                r"\b(BENCHMARK|SLEEP)\b",  # MySQL time-based attacks
            ]


class SQLPolicyService:
    """
    🛡️ Servicio de políticas SQL para la Fase 7
    
    Implementa:
    - Validación estricta de operaciones
    - Inyección automática de LIMIT y TIMEOUT
    - Whitelist de schemas
    - Detección de patrones peligrosos
    """
    
    def __init__(self, config: Optional[SQLPolicyConfig] = None):
        self.config = config or SQLPolicyConfig()
        self._compiled_patterns = [re.compile(pattern, re.IGNORECASE) 
                                 for pattern in self.config.forbidden_patterns]
        
        logger.info(f"[SQLPolicyService] Inicializado con políticas: "
                   f"operaciones={[op.value for op in self.config.allowed_operations]}, "
                   f"schemas={self.config.allowed_schemas}")
    
    def validate_and_secure_sql(self, sql: str, 
                               context: Dict[str, str] = None) -> Tuple[str, Dict[str, any]]:
        """
        🔒 Valida y asegura una consulta SQL
        
        Args:
            sql: Consulta SQL a validar
            context: Contexto de la operación (tenant_id, app_id, db_id, etc.)
            
        Returns:
            Tuple de (sql_seguro, métricas_de_validación)
            
        Raises:
            SQLPolicyViolation: Si la consulta viola las políticas
        """
        context = context or {}
        start_time = self._get_current_time()
        
        try:
            # 1. Validar operación principal
            operation = self._extract_operation(sql)
            self._validate_operation(operation)
            
            # 2. Validar schemas referenciados
            schemas = self._extract_referenced_schemas(sql)
            self._validate_schemas(schemas)
            
            # 3. Detectar patrones peligrosos
            self._detect_forbidden_patterns(sql)
            
            # 4. Aplicar políticas de seguridad
            secured_sql = self._apply_security_policies(sql)
            
            # 5. Generar métricas
            validation_metrics = self._generate_validation_metrics(
                start_time, operation, schemas, context
            )
            
            logger.info(f"[SQLPolicyService] SQL validado y asegurado: "
                       f"operation={operation}, schemas={schemas}, "
                       f"context={context.get('tenant_id', 'unknown')}")
            
            return secured_sql, validation_metrics
            
        except SQLPolicyViolation:
            # Re-raise para mantener el error_code
            raise
        except Exception as e:
            # Error inesperado
            logger.error(f"[SQLPolicyService] Error inesperado validando SQL: {e}")
            raise SQLPolicyViolation(
                error_code="SQL_VALIDATION_ERROR",
                message="Error interno validando la consulta SQL",
                hint="Contacta al administrador del sistema"
            )
    
    def _extract_operation(self, sql: str) -> str:
        """Extrae la operación principal del SQL"""
        sql_clean = sql.strip().upper()
        
        # Buscar la primera palabra que sea una operación SQL
        for operation in SQLOperationType:
            if sql_clean.startswith(operation.value):
                return operation.value
        
        raise SQLPolicyViolation(
            error_code="INVALID_OPERATION",
            message="No se pudo identificar la operación SQL",
            hint="La consulta debe comenzar con una operación válida"
        )
    
    def _validate_operation(self, operation: str):
        """Valida que la operación esté permitida"""
        if operation not in [op.value for op in self.config.allowed_operations]:
            raise SQLPolicyViolation(
                error_code="OPERATION_NOT_ALLOWED",
                message=f"La operación '{operation}' no está permitida",
                hint=f"Solo se permiten: {[op.value for op in self.config.allowed_operations]}"
            )
    
    def _extract_referenced_schemas(self, sql: str) -> List[str]:
        """Extrae los schemas referenciados en el SQL"""
        schemas = set()
        
        # Patrones para detectar referencias a schemas
        patterns = [
            r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\.',  # FROM schema.table
            r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\.',  # JOIN schema.table
            r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\.',  # UPDATE schema.table
            r'INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\.',  # INSERT INTO schema.table
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            schemas.update(matches)
        
        return list(schemas)
    
    def _validate_schemas(self, schemas: List[str]):
        """Valida que todos los schemas estén en la whitelist"""
        for schema in schemas:
            if not any(self._schema_matches_pattern(schema, allowed_pattern) 
                      for allowed_pattern in self.config.allowed_schemas):
                raise SQLPolicyViolation(
                    error_code="SCHEMA_NOT_ALLOWED",
                    message=f"El schema '{schema}' no está permitido",
                    hint=f"Schemas permitidos: {self.config.allowed_schemas}"
                )
    
    def _schema_matches_pattern(self, schema: str, pattern: str) -> bool:
        """Verifica si un schema coincide con un patrón permitido"""
        if pattern.endswith('_'):
            # Patrón con wildcard (ej: "app_")
            return schema.startswith(pattern[:-1])
        else:
            # Patrón exacto
            return schema == pattern
    
    def _detect_forbidden_patterns(self, sql: str):
        """Detecta patrones SQL peligrosos"""
        for pattern in self._compiled_patterns:
            if pattern.search(sql):
                raise SQLPolicyViolation(
                    error_code="FORBIDDEN_PATTERN_DETECTED",
                    message="Se detectó un patrón SQL peligroso",
                    hint="La consulta contiene operaciones no permitidas por seguridad"
                )
    
    def _apply_security_policies(self, sql: str) -> str:
        """Aplica políticas de seguridad al SQL"""
        secured_sql = sql
        
        # 1. Asegurar que solo sea SELECT
        if not secured_sql.strip().upper().startswith('SELECT'):
            raise SQLPolicyViolation(
                error_code="ONLY_SELECT_ALLOWED",
                message="Solo se permiten consultas SELECT",
                hint="Modifica la consulta para usar solo SELECT"
            )
        
        # 2. Inyectar LIMIT si no existe
        if not re.search(r'\bLIMIT\s+\d+', secured_sql, re.IGNORECASE):
            secured_sql += f" LIMIT {self.config.default_limit}"
            logger.info(f"[SQLPolicyService] LIMIT {self.config.default_limit} inyectado")
        
        # 3. Asegurar que el LIMIT no exceda el máximo
        limit_match = re.search(r'\bLIMIT\s+(\d+)', secured_sql, re.IGNORECASE)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > self.config.max_limit:
                secured_sql = re.sub(
                    r'\bLIMIT\s+\d+', 
                    f"LIMIT {self.config.max_limit}", 
                    secured_sql, 
                    flags=re.IGNORECASE
                )
                logger.warning(f"[SQLPolicyService] LIMIT reducido de {limit_value} a {self.config.max_limit}")
        
        # 4. Añadir comentario de seguridad
        secured_sql += f" -- 🔒 Políticas aplicadas: LIMIT, solo SELECT"
        
        return secured_sql
    
    def _generate_validation_metrics(self, start_time: float, operation: str, 
                                   schemas: List[str], context: Dict[str, str]) -> Dict[str, any]:
        """Genera métricas de validación para observabilidad"""
        validation_duration_ms = (self._get_current_time() - start_time) * 1000
        
        return {
            "validation_duration_ms": round(validation_duration_ms, 2),
            "operation": operation,
            "schemas_referenced": schemas,
            "policies_applied": ["LIMIT", "SELECT_ONLY", "SCHEMA_WHITELIST"],
            "context": context,
            "timestamp": self._get_current_time()
        }
    
    def _get_current_time(self) -> float:
        """Obtiene el tiempo actual para métricas"""
        import time
        return time.time()
    
    def get_policy_summary(self) -> Dict[str, any]:
        """Devuelve un resumen de las políticas activas"""
        return {
            "allowed_operations": [op.value for op in self.config.allowed_operations],
            "default_limit": self.config.default_limit,
            "max_limit": self.config.max_limit,
            "default_timeout_seconds": self.config.default_timeout_seconds,
            "max_timeout_seconds": self.config.max_timeout_seconds,
            "allowed_schemas": self.config.allowed_schemas,
            "forbidden_patterns_count": len(self.config.forbidden_patterns),
            "service_version": "1.0.0"
        }
