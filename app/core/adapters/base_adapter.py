#!/usr/bin/env python3
"""
Base Adapter - Clase base para todos los adapters
─────────────────────────────────────────────────
Implementa la Fase 4 del plan de refactorización:
- Funcionalidad común para todos los adapters
- Manejo de configuración por ENV
- Logging estructurado
- Métricas de performance
"""

import os
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class AdapterType(Enum):
    """Tipos de adapters disponibles"""
    EMBEDDING = "embedding"
    VECTOR_STORE = "vector_store"
    CACHE = "cache"
    LLM = "llm"


@dataclass
class AdapterConfig:
    """Configuración base para adapters"""
    provider: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    batch_size: int = 100
    namespace_strategy: str = "tenant_app_db_snapshot"


class BaseAdapter(ABC):
    """
    🔧 Clase base para todos los adapters
    
    Responsabilidades:
    - Configuración común
    - Logging estructurado
    - Métricas de performance
    - Manejo de errores
    - Validación de configuración
    """
    
    def __init__(self, adapter_type: AdapterType, config: AdapterConfig):
        self.adapter_type = adapter_type
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{adapter_type.value}")
        
        # 🔧 FASE 4: Métricas de performance
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0,
            "last_request_time": None
        }
        
        # Validar configuración
        self._validate_config()
    
    def _validate_config(self):
        """Validar configuración del adapter"""
        if not self.config.provider:
            raise ValueError(f"Provider es requerido para {self.adapter_type.value}")
        
        if self.config.timeout < 1:
            raise ValueError(f"Timeout debe ser >= 1 segundo para {self.adapter_type.value}")
        
        if self.config.max_retries < 0:
            raise ValueError(f"Max retries debe ser >= 0 para {self.adapter_type.value}")
        
        if self.config.batch_size < 1:
            raise ValueError(f"Batch size debe ser >= 1 para {self.adapter_type.value}")
    
    def _get_env_config(self, key: str, default: Any = None) -> Any:
        """Obtener configuración desde variables de entorno"""
        env_key = f"{self.adapter_type.value.upper()}_{key.upper()}"
        return os.getenv(env_key, default)
    
    def _log_operation(self, operation: str, **kwargs):
        """Log estructurado para operaciones"""
        log_data = {
            "adapter_type": self.adapter_type.value,
            "provider": self.config.provider,
            "operation": operation,
            **kwargs
        }
        self.logger.info(f"[{self.adapter_type.value.upper()}] {operation}", extra=log_data)
    
    def _log_error(self, operation: str, error: Exception, **kwargs):
        """Log estructurado para errores"""
        log_data = {
            "adapter_type": self.adapter_type.value,
            "provider": self.config.provider,
            "operation": operation,
            "error": str(error),
            "error_type": type(error).__name__,
            **kwargs
        }
        self.logger.error(f"[{self.adapter_type.value.upper()}] ❌ Error en {operation}: {error}", extra=log_data)
    
    def _measure_performance(self, operation: str):
        """Decorator para medir performance de operaciones"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    self._update_metrics(True, time.time() - start_time)
                    return result
                except Exception as e:
                    self._update_metrics(False, time.time() - start_time)
                    self._log_error(operation, e)
                    raise
            return wrapper
        return decorator
    
    def _update_metrics(self, success: bool, latency_ms: float):
        """Actualizar métricas de performance"""
        self.metrics["total_requests"] += 1
        if success:
            self.metrics["successful_requests"] += 1
        else:
            self.metrics["failed_requests"] += 1
        
        self.metrics["total_latency_ms"] += latency_ms
        self.metrics["last_request_time"] = time.time()
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance del adapter"""
        total_requests = self.metrics["total_requests"]
        if total_requests == 0:
            return {
                "adapter_type": self.adapter_type.value,
                "provider": self.config.provider,
                "total_requests": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0
            }
        
        success_rate = self.metrics["successful_requests"] / total_requests
        avg_latency = self.metrics["total_latency_ms"] / total_requests
        
        return {
            "adapter_type": self.adapter_type.value,
            "provider": self.config.provider,
            "total_requests": total_requests,
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate": round(success_rate, 3),
            "avg_latency_ms": round(avg_latency, 2),
            "last_request_time": self.metrics["last_request_time"]
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Obtener estado de salud del adapter"""
        try:
            # Intentar operación básica para verificar conectividad
            health_check = self._health_check()
            return {
                "adapter_type": self.adapter_type.value,
                "provider": self.config.provider,
                "status": "healthy" if health_check else "unhealthy",
                "last_check": time.time(),
                "metrics": self.get_performance_metrics()
            }
        except Exception as e:
            return {
                "adapter_type": self.adapter_type.value,
                "provider": self.config.provider,
                "status": "error",
                "error": str(e),
                "last_check": time.time(),
                "metrics": self.get_performance_metrics()
            }
    
    @abstractmethod
    def _health_check(self) -> bool:
        """Verificación de salud del adapter (implementar en subclases)"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Inicializar el adapter (implementar en subclases)"""
        pass
    
    def cleanup(self):
        """Limpieza del adapter (opcional)"""
        self.logger.info(f"[{self.adapter_type.value.upper()}] 🧹 Limpieza completada")
    
    def __str__(self):
        return f"{self.adapter_type.value.capitalize()}Adapter({self.config.provider})"
    
    def __repr__(self):
        return self.__str__()
