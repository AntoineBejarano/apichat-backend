"""
📊 FASE 7: Módulo de Observabilidad y Logs Estructurados
──────────────────────────────────────────────────────────
Implementa:
- Logs JSON estructurados con contexto completo
- Métricas de performance automáticas
- Códigos de error estandarizados
- Trazabilidad end-to-end
"""

from .structured_logger_service import (
    StructuredLoggerService, 
    LogContext, 
    PerformanceMetrics, 
    LogLevel, 
    ErrorCode
)

__all__ = [
    "StructuredLoggerService",
    "LogContext",
    "PerformanceMetrics", 
    "LogLevel",
    "ErrorCode"
]
