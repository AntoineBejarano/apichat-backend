# app/utils/performance_monitor.py

import time
import logging
import asyncio
from functools import wraps
from typing import Dict, Any, Optional, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.active_timers = {}
        self.timer_stack = []  # 🔧 FASE 1: Stack para evitar timers anidados
    
    def start_timer(self, name: str):
        """🔧 FASE 1: Inicia un timer para medir performance con validaciones"""
        if name in self.active_timers:
            logger.warning(f"⏱️ Timer '{name}' ya está activo, no se puede iniciar nuevamente")
            return False
        
        self.active_timers[name] = time.time()
        self.timer_stack.append(name)
        logger.debug(f"⏱️ Timer iniciado: {name}")
        return True
    
    def end_timer(self, name: str) -> float:
        """🔧 FASE 1: Termina un timer y retorna la duración con validaciones"""
        if name not in self.active_timers:
            logger.warning(f"⏱️ Timer '{name}' no encontrado o ya cerrado")
            return 0.0
        
        # Verificar que el timer esté en el stack (evita cierres desordenados)
        if name not in self.timer_stack:
            logger.warning(f"⏱️ Timer '{name}' no está en el stack de timers activos")
            return 0.0
        
        duration = time.time() - self.active_timers[name]
        del self.active_timers[name]
        self.timer_stack.remove(name)
        
        # Guardar métrica
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration)
        
        logger.info(f"⏱️ Timer '{name}' completado: {duration:.3f}s")
        return duration
    
    def stop_timer(self, name: str) -> float:
        """🔧 FASE 1: Alias para end_timer para compatibilidad"""
        return self.end_timer(name)
    
    def is_timer_active(self, name: str) -> bool:
        """🔧 FASE 1: Verifica si un timer está activo"""
        return name in self.active_timers
    
    def get_active_timers(self) -> List[str]:
        """🔧 FASE 1: Obtiene lista de timers activos"""
        return list(self.active_timers.keys())
    
    def force_stop_all_timers(self):
        """🔧 FASE 1: Fuerza el cierre de todos los timers activos (útil para cleanup)"""
        active_timers = list(self.active_timers.keys())
        for timer_name in active_timers:
            try:
                self.end_timer(timer_name)
            except Exception as e:
                logger.error(f"Error forzando cierre de timer '{timer_name}': {e}")
        
        logger.info(f"🔧 FASE 1: {len(active_timers)} timers forzados a cerrar")
    
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
        self.timer_stack.clear()

# Instancia global
performance_monitor = PerformanceMonitor()

def monitor_performance(operation_name: str):
    """🔧 FASE 1: Decorator para monitorear performance de funciones con validaciones"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not performance_monitor.start_timer(operation_name):
                # Si no se pudo iniciar el timer, continuar sin monitoreo
                return await func(*args, **kwargs)
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                performance_monitor.end_timer(operation_name)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not performance_monitor.start_timer(operation_name):
                # Si no se pudo iniciar el timer, continuar sin monitoreo
                return func(*args, **kwargs)
            
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
    """🔧 FASE 1: Context manager para monitorear performance con validaciones"""
    if not performance_monitor.start_timer(operation_name):
        # Si no se pudo iniciar el timer, continuar sin monitoreo
        yield
        return
    
    try:
        yield
    finally:
        performance_monitor.end_timer(operation_name)

def log_performance_summary():
    """🔧 FASE 1: Logea un resumen de performance incluyendo timers activos"""
    slow_ops = performance_monitor.get_slow_operations(threshold=0.5)
    
    if slow_ops:
        logger.info("🐌 Operaciones lentas detectadas:")
        for op, time in slow_ops.items():
            logger.info(f"  - {op}: {time:.3f}s promedio")
    
    active_timers = performance_monitor.get_active_timers()
    if active_timers:
        logger.warning(f"⚠️ Timers activos sin cerrar: {active_timers}")
        # Forzar cierre de timers huérfanos
        performance_monitor.force_stop_all_timers()
    
    logger.info(f"📊 Total de métricas registradas: {len(performance_monitor.metrics)}") 