# app/utils/profiler.py

import cProfile
import pstats
import io
import time
import logging
import asyncio
from functools import wraps
from typing import Dict, Any, Optional, Callable, List
from contextlib import contextmanager
import tracemalloc

logger = logging.getLogger(__name__)

class PerformanceProfiler:
    def __init__(self):
        self.profiler = cProfile.Profile()
        self.stats = None
        self.memory_snapshots = {}
        
    def start_profiling(self):
        """Inicia el profiling de CPU"""
        self.profiler.enable()
        tracemalloc.start()
        logger.info("🔍 Profiling iniciado")
        
    def stop_profiling(self) -> Dict[str, Any]:
        """Detiene el profiling y retorna estadísticas"""
        self.profiler.disable()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Generar estadísticas
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)  # Top 20 funciones
        stats_output = s.getvalue()
        
        # Analizar estadísticas
        stats = self._analyze_stats(ps)
        
        logger.info("🔍 Profiling completado")
        return {
            "cpu_stats": stats,
            "memory_current_mb": current / 1024 / 1024,
            "memory_peak_mb": peak / 1024 / 1024,
            "stats_output": stats_output
        }
    
    def _analyze_stats(self, ps: pstats.Stats) -> Dict[str, Any]:
        """Analiza las estadísticas del profiler"""
        stats_dict = {}
        for func, (cc, nc, tt, ct, callers) in ps.stats.items():
            func_name = f"{func[0]}:{func[1]}:{func[2]}"
            stats_dict[func_name] = {
                "calls": nc,
                "total_time": tt,
                "cumulative_time": ct,
                "time_per_call": tt / nc if nc > 0 else 0
            }
        
        # Encontrar las funciones más lentas
        slow_functions = sorted(
            stats_dict.items(),
            key=lambda x: x[1]["cumulative_time"],
            reverse=True
        )[:10]
        
        return {
            "slow_functions": slow_functions,
            "total_functions": len(stats_dict)
        }

# Instancia global
profiler = PerformanceProfiler()

def profile_function(func_name: str = None):
    """Decorator para profiling de funciones"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            with profile_context(name):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            with profile_context(name):
                return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

@contextmanager
def profile_context(name: str):
    """Context manager para profiling"""
    start_time = time.time()
    start_memory = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
    
    try:
        yield
    finally:
        end_time = time.time()
        end_memory = tracemalloc.get_traced_memory()[0] if tracemalloc.is_tracing() else 0
        
        duration = end_time - start_time
        memory_used = (end_memory - start_memory) / 1024 / 1024  # MB
        
        logger.info(f"⏱️ {name}: {duration:.3f}s, {memory_used:.2f}MB")

class DatabaseProfiler:
    """Profiler específico para consultas de BD"""
    
    def __init__(self):
        self.query_times = {}
        self.slow_queries = []
        
    def log_query(self, query: str, duration: float, params: Dict[str, Any] = None):
        """Registra una consulta de BD"""
        query_hash = hash(query)
        
        if query_hash not in self.query_times:
            self.query_times[query_hash] = []
        
        self.query_times[query_hash].append({
            "query": query,
            "duration": duration,
            "params": params,
            "timestamp": time.time()
        })
        
        # Registrar consultas lentas
        if duration > 1.0:  # Más de 1 segundo
            self.slow_queries.append({
                "query": query,
                "duration": duration,
                "params": params,
                "timestamp": time.time()
            })
            
        logger.debug(f"🗄️ Query: {duration:.3f}s - {query[:100]}...")
    
    def get_slow_queries(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Obtiene consultas que superan el umbral"""
        slow = []
        for query_hash, times in self.query_times.items():
            avg_time = sum(t["duration"] for t in times) / len(times)
            if avg_time > threshold:
                slow.append({
                    "query": times[0]["query"],
                    "avg_duration": avg_time,
                    "call_count": len(times),
                    "total_time": sum(t["duration"] for t in times)
                })
        
        return sorted(slow, key=lambda x: x["avg_duration"], reverse=True)
    
    def get_query_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas generales de consultas"""
        if not self.query_times:
            return {"total_queries": 0, "avg_time": 0, "slow_queries": 0}
        
        all_times = []
        for times in self.query_times.values():
            all_times.extend([t["duration"] for t in times])
        
        return {
            "total_queries": len(all_times),
            "avg_time": sum(all_times) / len(all_times),
            "slow_queries": len(self.slow_queries),
            "total_time": sum(all_times)
        }

# Instancia global para BD
db_profiler = DatabaseProfiler()

class MemoryProfiler:
    """Profiler específico para memoria"""
    
    def __init__(self):
        self.snapshots = {}
        
    def take_snapshot(self, name: str):
        """Toma una snapshot de memoria"""
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            self.snapshots[name] = {
                "current_mb": current / 1024 / 1024,
                "peak_mb": peak / 1024 / 1024,
                "timestamp": time.time()
            }
            logger.debug(f"📊 Snapshot '{name}': {current / 1024 / 1024:.2f}MB")
    
    def compare_snapshots(self, name1: str, name2: str) -> Dict[str, float]:
        """Compara dos snapshots"""
        if name1 not in self.snapshots or name2 not in self.snapshots:
            return {}
        
        snap1 = self.snapshots[name1]
        snap2 = self.snapshots[name2]
        
        return {
            "current_diff_mb": snap2["current_mb"] - snap1["current_mb"],
            "peak_diff_mb": snap2["peak_mb"] - snap1["peak_mb"],
            "time_diff": snap2["timestamp"] - snap1["timestamp"]
        }

# Instancia global para memoria
memory_profiler = MemoryProfiler()

def generate_performance_report() -> Dict[str, Any]:
    """Genera un reporte completo de performance"""
    
    # Profiling de CPU
    profiler.start_profiling()
    time.sleep(1)  # Simular trabajo
    cpu_stats = profiler.stop_profiling()
    
    # Estadísticas de BD
    db_stats = db_profiler.get_query_stats()
    slow_queries = db_profiler.get_slow_queries()
    
    # Reporte
    report = {
        "timestamp": time.time(),
        "cpu_profiling": cpu_stats,
        "database_stats": db_stats,
        "slow_queries": slow_queries[:5],  # Top 5 consultas lentas
        "memory_snapshots": memory_profiler.snapshots
    }
    
    # Log del reporte
    logger.info("📊 Reporte de Performance:")
    logger.info(f"  - CPU: {len(cpu_stats['cpu_stats']['slow_functions'])} funciones lentas")
    logger.info(f"  - BD: {db_stats['total_queries']} consultas, {db_stats['avg_time']:.3f}s promedio")
    logger.info(f"  - Memoria: {cpu_stats['memory_peak_mb']:.2f}MB pico")
    
    return report

# Decorator para profiling automático de endpoints
def profile_endpoint():
    """Decorator para profiling automático de endpoints FastAPI"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            endpoint_name = f"{func.__module__}.{func.__name__}"
            
            # Iniciar profiling
            memory_profiler.take_snapshot(f"{endpoint_name}_start")
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                memory_profiler.take_snapshot(f"{endpoint_name}_end")
                
                # Comparar snapshots
                diff = memory_profiler.compare_snapshots(
                    f"{endpoint_name}_start", 
                    f"{endpoint_name}_end"
                )
                
                if diff:
                    logger.info(f"📊 {endpoint_name}: {diff['current_diff_mb']:.2f}MB usado")
        
        return wrapper
    return decorator 