"""
📊 FASE 7: Servicio de Logs Estructurados y Observabilidad
────────────────────────────────────────────────────────────
Implementa logs JSON estructurados con métricas para:
- Trazabilidad completa (trace_id, tenant_id, app_id, db_id, snapshot_id)
- Métricas de performance (latencia, duración, tasas de éxito)
- Logs listos para agregación (ELK/Datadog)
- Códigos de error estandarizados
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
import traceback

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Niveles de log estandarizados"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ErrorCode(Enum):
    """Códigos de error estandarizados para la Fase 7"""
    # Errores de validación
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Errores de SQL
    SQL_VALIDATION_ERROR = "SQL_VALIDATION_ERROR"
    SQL_EXECUTION_ERROR = "SQL_EXECUTION_ERROR"
    SQL_TIMEOUT = "SQL_TIMEOUT"
    
    # Errores de pipeline
    PIPELINE_STAGE_FAILED = "PIPELINE_STAGE_FAILED"
    PIPELINE_TIMEOUT = "PIPELINE_TIMEOUT"
    PIPELINE_RETRY_EXCEEDED = "PIPELINE_RETRY_EXCEEDED"
    
    # Errores de vector store
    VECTOR_STORE_ERROR = "VECTOR_STORE_ERROR"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"
    VECTOR_QUERY_ERROR = "VECTOR_QUERY_ERROR"
    
    # Errores de chat
    CHAT_CONTEXT_ERROR = "CHAT_CONTEXT_ERROR"
    CHAT_PLANNING_ERROR = "CHAT_PLANNING_ERROR"
    CHAT_EXECUTION_ERROR = "CHAT_EXECUTION_ERROR"
    
    # Errores de sistema
    SYSTEM_ERROR = "SYSTEM_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


@dataclass
class LogContext:
    """Contexto estándar para todos los logs"""
    trace_id: str
    tenant_id: Optional[str] = None
    app_id: Optional[str] = None
    db_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el contexto a diccionario"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PerformanceMetrics:
    """Métricas de performance para observabilidad"""
    operation: str
    stage: str
    elapsed_ms: float
    start_time: float
    end_time: float
    
    # Métricas específicas por operación
    sql_gen_latency_ms: Optional[float] = None
    db_exec_latency_ms: Optional[float] = None
    vector_query_latency_ms: Optional[float] = None
    ingestion_duration_ms: Optional[float] = None
    ask_total_latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte las métricas a diccionario"""
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredLoggerService:
    """
    📊 Servicio de logs estructurados para la Fase 7
    
    Implementa:
    - Logs JSON estructurados con contexto completo
    - Métricas de performance automáticas
    - Códigos de error estandarizados
    - Trazabilidad end-to-end
    """
    
    def __init__(self, service_name: str = "apichat-backend"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        
        # Configurar formato JSON si no está configurado
        if not self.logger.handlers:
            self._setup_json_logging()
        
        logger.info(f"[StructuredLoggerService] Inicializado para servicio: {service_name}")
    
    def _setup_json_logging(self):
        """Configura logging en formato JSON"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_operation_start(self, operation: str, stage: str, 
                           context: LogContext, **kwargs) -> str:
        """
        📝 Registra el inicio de una operación
        
        Args:
            operation: Nombre de la operación
            stage: Etapa actual
            context: Contexto de la operación
            **kwargs: Datos adicionales
            
        Returns:
            start_time para usar en log_operation_end
        """
        start_time = time.time()
        
        log_data = {
            "event": "operation_start",
            "operation": operation,
            "stage": stage,
            "timestamp": start_time,
            "level": LogLevel.INFO.value,
            **context.to_dict(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data, default=str))
        return start_time
    
    def log_operation_end(self, operation: str, stage: str, 
                         context: LogContext, start_time: float,
                         status: str = "success", **kwargs):
        """
        📝 Registra el fin de una operación con métricas
        
        Args:
            operation: Nombre de la operación
            stage: Etapa actual
            context: Contexto de la operación
            start_time: Tiempo de inicio (de log_operation_start)
            status: Estado de la operación
            **kwargs: Datos adicionales
        """
        end_time = time.time()
        elapsed_ms = (end_time - start_time) * 1000
        
        # Crear métricas de performance
        metrics = PerformanceMetrics(
            operation=operation,
            stage=stage,
            elapsed_ms=elapsed_ms,
            start_time=start_time,
            end_time=end_time
        )
        
        log_data = {
            "event": "operation_end",
            "operation": operation,
            "stage": stage,
            "status": status,
            "timestamp": end_time,
            "level": LogLevel.INFO.value,
            **context.to_dict(),
            **metrics.to_dict(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data, default=str))
    
    def log_error(self, error: Exception, context: LogContext,
                  operation: str = None, stage: str = None,
                  error_code: ErrorCode = None, **kwargs):
        """
        ❌ Registra un error con contexto completo
        
        Args:
            error: Excepción que ocurrió
            context: Contexto de la operación
            operation: Operación que falló
            stage: Etapa donde falló
            error_code: Código de error estandarizado
            **kwargs: Datos adicionales
        """
        # Determinar código de error
        if error_code is None:
            error_code = self._infer_error_code(error)
        
        # Obtener stack trace
        stack_trace = traceback.format_exc()
        
        log_data = {
            "event": "error",
            "error_code": error_code.value,
            "error_message": str(error),
            "error_type": type(error).__name__,
            "stack_trace": stack_trace,
            "timestamp": time.time(),
            "level": LogLevel.ERROR.value,
            **context.to_dict(),
            **kwargs
        }
        
        if operation:
            log_data["operation"] = operation
        if stage:
            log_data["stage"] = stage
        
        self.logger.error(json.dumps(log_data, default=str))
    
    def log_metric(self, metric_name: str, metric_value: Any,
                   context: LogContext, **kwargs):
        """
        📊 Registra una métrica específica
        
        Args:
            metric_name: Nombre de la métrica
            metric_value: Valor de la métrica
            context: Contexto de la operación
            **kwargs: Datos adicionales
        """
        log_data = {
            "event": "metric",
            "metric_name": metric_name,
            "metric_value": metric_value,
            "timestamp": time.time(),
            "level": LogLevel.INFO.value,
            **context.to_dict(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data, default=str))
    
    def log_pipeline_progress(self, pipeline_id: str, stage: str,
                             progress_pct: float, context: LogContext,
                             **kwargs):
        """
        🔄 Registra progreso del pipeline
        
        Args:
            pipeline_id: ID del pipeline
            stage: Etapa actual
            progress_pct: Porcentaje de progreso (0-100)
            context: Contexto de la operación
            **kwargs: Datos adicionales
        """
        log_data = {
            "event": "pipeline_progress",
            "pipeline_id": pipeline_id,
            "stage": stage,
            "progress_pct": progress_pct,
            "timestamp": time.time(),
            "level": LogLevel.INFO.value,
            **context.to_dict(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data, default=str))
    
    def log_security_event(self, event_type: str, details: str,
                          context: LogContext, severity: str = "medium",
                          **kwargs):
        """
        🛡️ Registra eventos de seguridad
        
        Args:
            event_type: Tipo de evento de seguridad
            details: Detalles del evento
            context: Contexto de la operación
            severity: Severidad (low, medium, high, critical)
            **kwargs: Datos adicionales
        """
        log_data = {
            "event": "security_event",
            "event_type": event_type,
            "details": details,
            "severity": severity,
            "timestamp": time.time(),
            "level": LogLevel.WARNING.value,
            **context.to_dict(),
            **kwargs
        }
        
        self.logger.warning(json.dumps(log_data, default=str))
    
    @contextmanager
    def operation_timer(self, operation: str, stage: str, 
                       context: LogContext, **kwargs):
        """
        ⏱️ Context manager para medir tiempo de operaciones
        
        Usage:
            with logger.operation_timer("query_execution", "sql_validation", context):
                # código a medir
                pass
        """
        start_time = self.log_operation_start(operation, stage, context, **kwargs)
        
        try:
            yield
            self.log_operation_end(operation, stage, context, start_time, "success")
        except Exception as e:
            self.log_operation_end(operation, stage, context, start_time, "error")
            self.log_error(e, context, operation, stage)
            raise
    
    def _infer_error_code(self, error: Exception) -> ErrorCode:
        """Infiere el código de error basado en el tipo de excepción"""
        error_type = type(error).__name__
        
        # Mapeo de tipos de error a códigos
        error_mapping = {
            'SQLPolicyViolation': ErrorCode.SQL_VALIDATION_ERROR,
            'ValidationError': ErrorCode.VALIDATION_ERROR,
            'TimeoutError': ErrorCode.SQL_TIMEOUT,
            'ConnectionError': ErrorCode.SERVICE_UNAVAILABLE,
        }
        
        return error_mapping.get(error_type, ErrorCode.SYSTEM_ERROR)
    
    def generate_trace_id(self) -> str:
        """Genera un ID de trazabilidad único"""
        return str(uuid.uuid4())
    
    def get_log_summary(self) -> Dict[str, Any]:
        """Devuelve un resumen de la configuración de logging"""
        return {
            "service_name": self.service_name,
            "log_level": self.logger.level,
            "handlers_count": len(self.logger.handlers),
            "error_codes_available": [code.value for code in ErrorCode],
            "service_version": "1.0.0"
        }
