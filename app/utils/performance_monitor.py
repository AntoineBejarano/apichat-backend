# app/utils/performance_monitor.py

import time
import logging
from functools import wraps
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.active_timers = {}
    
    def start_timer(self, name: str):
        """Inicia un timer para medir performance"""
        self.active_timers[name] = time.time()
        logger.debug(f"⏱️ Timer iniciado: {name}")
    
    def end_timer(self, name: str) -> float:
        """Termina un timer y retorna la duración"""
        if name not in self.active_timers:
            logger.warning(f"⏱️ Timer '{name}' no encontrado")
            return 0.0
        
        duration = time.time() - self.active_timers[name]
        del self.active_timers[name]
        
        # Guardar métrica
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration)
        
        logger.info(f"⏱️ Timer '{name}' completado: {duration:.3f}s")
        return duration
    
    def get_average_time(self, name: str) -> float:
        """Obtiene el tiempo promedio para una operación"""
        if name not in self.metrics or not self.metrics[name]:
            return 0.0
        return sum(self.metrics[name]) / len(self.metrics[name])
    
    def get_slow_operations(self, threshold: float = 1.0) -> Dict[str, float]:
        """Obtiene operaciones lentas que superan el umbral"""
        slow_ops = {}
        for name, times in self.metrics.items():
            avg_time = self.get_average_time(name)
            if avg_time > threshold:
                slow_ops[name] = avg_time
        return slow_ops
    
    def clear_metrics(self):
        """Limpia todas las métricas"""
        self.metrics.clear()
        self.active_timers.clear()

# Instancia global
performance_monitor = PerformanceMonitor()

def monitor_performance(operation_name: str):
    """Decorator para monitorear performance de funciones"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            performance_monitor.start_timer(operation_name)
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                performance_monitor.end_timer(operation_name)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            performance_monitor.start_timer(operation_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                performance_monitor.end_timer(operation_name)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

@contextmanager
def performance_context(operation_name: str):
    """Context manager para monitorear performance"""
    performance_monitor.start_timer(operation_name)
    try:
        yield
    finally:
        performance_monitor.end_timer(operation_name)

def log_performance_summary():
    """Logea un resumen de performance"""
    slow_ops = performance_monitor.get_slow_operations(threshold=0.5)
    
    if slow_ops:
        logger.warning("🐌 Operaciones lentas detectadas:")
        for op_name, avg_time in slow_ops.items():
            logger.warning(f"  - {op_name}: {avg_time:.3f}s promedio")
    else:
        logger.info("✅ Todas las operaciones están dentro del umbral de performance")

# Import asyncio para el decorator
import asyncio 