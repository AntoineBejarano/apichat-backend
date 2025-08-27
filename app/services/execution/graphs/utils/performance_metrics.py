import time
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Maneja las métricas de rendimiento del grafo de exploración"""
    
    def __init__(self):
        self.metrics = {
            "init": 0.0,
            "react_think": 0.0,
            "schema_build": 0.0,
            "openai_plan": 0.0,
            "sql_exec": 0.0,
            "total": 0.0
        }
        # Métricas de tokens
        self.token_metrics = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "schema_tokens": 0,
            "prompt_tokens": 0,
            "response_tokens": 0
        }
        # NUEVAS MÉTRICAS PARA READINESS Y FASES
        self.phase_timings = {}
        self.resource_readiness_times = {}
        self.users_waiting = {}
        self.resource_preparation_history = {}
        
        self.overall_start_time = None
    
    def start_overall_timer(self):
        """Inicia el timer general"""
        self.overall_start_time = time.time()
    
    def record_node_time(self, node_name: str, node_time: float):
        """Registra el tiempo de un nodo específico"""
        if node_name in self.metrics:
            self.metrics[node_name] = node_time
            logger.info(f"[PerformanceMetrics] 📊 Performance - {node_name}: {node_time:.3f}s")
    
    def record_node_performance(self, node_name: str, execution_time: float):
        """Registra el performance de un nodo específico (alias para record_node_time)"""
        self.record_node_time(node_name, execution_time)
    
    def record_tokens(self, token_type: str, count: int):
        """Registra el conteo de tokens por tipo"""
        if token_type in self.token_metrics:
            self.token_metrics[token_type] = count
            logger.info(f"[PerformanceMetrics] 🎯 Tokens - {token_type}: {count}")
    
    def record_openai_usage(self, input_tokens: int, output_tokens: int):
        """Registra el uso de tokens de OpenAI"""
        self.token_metrics["input_tokens"] = input_tokens
        self.token_metrics["output_tokens"] = output_tokens
        self.token_metrics["total_tokens"] = input_tokens + output_tokens
        logger.info(f"[PerformanceMetrics] 🤖 OpenAI Tokens - Input: {input_tokens}, Output: {output_tokens}, Total: {self.token_metrics['total_tokens']}")
    
    def record_schema_tokens(self, schema_text: str):
        """Calcula y registra tokens del esquema (aproximado)"""
        # Estimación aproximada: 1 token ≈ 4 caracteres
        estimated_tokens = len(schema_text) // 4
        self.token_metrics["schema_tokens"] = estimated_tokens
        logger.info(f"[PerformanceMetrics] 🗜️ Schema Tokens estimados: {estimated_tokens} (texto: {len(schema_text)} chars)")
    
    def calculate_total_time(self):
        """Calcula el tiempo total"""
        if self.overall_start_time:
            self.metrics["total"] = time.time() - self.overall_start_time
    
    def calculate_total_tokens(self):
        """Calcula el total de tokens"""
        # Sumar todos los tipos de tokens
        total = sum(self.token_metrics.values())
        self.token_metrics["total_tokens"] = total
        logger.info(f"[PerformanceMetrics] 🎯 Total Tokens calculado: {total}")
        return total
    
    # NUEVOS MÉTODOS PARA READINESS Y FASES
    def record_phase_time(self, phase: str, duration: float):
        """Registra tiempo de ejecución de una fase de inicialización"""
        if phase not in self.phase_timings:
            self.phase_timings[phase] = []
        self.phase_timings[phase].append(duration)
        logger.info(f"[PerformanceMetrics] 🚀 Fase {phase}: {duration:.3f}s")
    
    def record_resource_readiness(self, resource_type: str, resource_id: str, duration: float):
        """Registra tiempo de preparación de un recurso específico"""
        key = f"{resource_type}_{resource_id}"
        if key not in self.resource_readiness_times:
            self.resource_readiness_times[key] = []
        self.resource_readiness_times[key].append(duration)
        
        # Guardar historial de preparación
        if key not in self.resource_preparation_history:
            self.resource_preparation_history[key] = []
        
        self.resource_preparation_history[key].append({
            'timestamp': datetime.now(timezone.utc),
            'duration': duration,
            'status': 'completed'
        })
        
        logger.info(f"[PerformanceMetrics] 🔧 Recurso {resource_type}:{resource_id} preparado en {duration:.3f}s")
    
    def track_user_waiting(self, user_id: str, waiting_for: str):
        """Trackea usuarios esperando por recursos"""
        self.users_waiting[user_id] = {
            'waiting_for': waiting_for,
            'started_at': datetime.now(timezone.utc),
            'status': 'waiting'
        }
        logger.info(f"[PerformanceMetrics] ⏳ Usuario {user_id} esperando por {waiting_for}")
    
    def mark_user_no_longer_waiting(self, user_id: str):
        """Marca que un usuario ya no está esperando"""
        if user_id in self.users_waiting:
            self.users_waiting[user_id]['status'] = 'completed'
            self.users_waiting[user_id]['completed_at'] = datetime.now(timezone.utc)
            
            # Calcular tiempo total de espera
            start_time = self.users_waiting[user_id]['started_at']
            completed_time = self.users_waiting[user_id]['completed_at']
            total_wait_time = (completed_time - start_time).total_seconds()
            
            logger.info(f"[PerformanceMetrics] ✅ Usuario {user_id} completó espera en {total_wait_time:.3f}s")
    
    def get_phase_stats(self, phase: str) -> Dict[str, Any]:
        """Obtiene estadísticas de una fase específica"""
        times = self.phase_timings.get(phase, [])
        if not times:
            return {'count': 0, 'average': 0, 'min': 0, 'max': 0}
        
        return {
            'count': len(times),
            'average': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'last_execution': times[-1] if times else 0
        }
    
    def get_resource_performance_stats(self, resource_type: str, resource_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de performance de un recurso específico"""
        key = f"{resource_type}_{resource_id}"
        times = self.resource_readiness_times.get(key, [])
        
        if not times:
            return {'count': 0, 'average': 0, 'min': 0, 'max': 0}
        
        return {
            'count': len(times),
            'average': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'last_preparation': self.resource_preparation_history.get(key, [])[-1] if self.resource_preparation_history.get(key) else None
        }
    
    def get_users_waiting_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de usuarios esperando"""
        waiting_users = [u for u in self.users_waiting.values() if u['status'] == 'waiting']
        completed_users = [u for u in self.users_waiting.values() if u['status'] == 'completed']
        
        if not completed_users:
            avg_wait_time = 0
        else:
            wait_times = [(u['completed_at'] - u['started_at']).total_seconds() for u in completed_users]
            avg_wait_time = sum(wait_times) / len(wait_times)
        
        longest_current_wait = 0
        if waiting_users:
            longest_current_wait = max([
                (datetime.now(timezone.utc) - u['started_at']).total_seconds() 
                for u in waiting_users
            ])
        
        return {
            'currently_waiting': len(waiting_users),
            'total_completed': len(completed_users),
            'longest_current_wait': longest_current_wait,
            'average_wait_time': avg_wait_time
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene las métricas actuales incluyendo tokens"""
        return {
            "performance": self.metrics.copy(),
            "tokens": self.token_metrics.copy(),
            # NUEVAS MÉTRICAS
            "phases": self.phase_timings.copy(),
            "resources": self.resource_readiness_times.copy(),
            "users_waiting": self.get_users_waiting_stats()
        }
    
    def log_breakdown(self):
        """Registra el breakdown completo de métricas"""
        logger.info(f"[PerformanceMetrics] 📊 Performance BREAKDOWN:")
        logger.info(f"   • init: {self.metrics.get('init', 0):.3f}s")
        logger.info(f"   • react_think: {self.metrics.get('react_think', 0):.3f}s")
        logger.info(f"   • schema_build: {self.metrics.get('schema_build', 0):.3f}s")
        logger.info(f"   • openai_plan: {self.metrics.get('openai_plan', 0):.3f}s")
        logger.info(f"   • sql_exec: {self.metrics.get('sql_exec', 0):.3f}s")
        logger.info(f"   • TOTAL: {self.metrics['total']:.3f}s")
        
        logger.info(f"[PerformanceMetrics] 🎯 Token BREAKDOWN:")
        logger.info(f"   • Input tokens: {self.token_metrics.get('input_tokens', 0)}")
        logger.info(f"   • Output tokens: {self.token_metrics.get('output_tokens', 0)}")
        logger.info(f"   • Schema tokens: {self.token_metrics.get('schema_tokens', 0)}")
        logger.info(f"   • Prompt tokens: {self.token_metrics.get('prompt_tokens', 0)}")
        logger.info(f"   • Response tokens: {self.token_metrics.get('response_tokens', 0)}")
        logger.info(f"   • TOTAL TOKENS: {self.token_metrics.get('total_tokens', 0)}")
        
        # NUEVO: Breakdown de fases y recursos
        if self.phase_timings:
            logger.info(f"[PerformanceMetrics] 🚀 Fases BREAKDOWN:")
            for phase, times in self.phase_timings.items():
                if times:
                    avg_time = sum(times) / len(times)
                    logger.info(f"   • {phase}: {len(times)} ejecuciones, promedio: {avg_time:.3f}s")
        
        if self.resource_readiness_times:
            logger.info(f"[PerformanceMetrics] 🔧 Recursos BREAKDOWN:")
            for resource_key, times in self.resource_readiness_times.items():
                if times:
                    avg_time = sum(times) / len(times)
                    logger.info(f"   • {resource_key}: {len(times)} preparaciones, promedio: {avg_time:.3f}s")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen completo de las métricas de rendimiento"""
        return {
            "performance_breakdown": {
                "init": "Tiempo de inicialización y selección de recursos",
                "react_think": "Tiempo de pensamiento y decisión del AI",
                "schema_build": "Tiempo de construcción y limpieza de schema",
                "openai_plan": "Tiempo de generación de plan por OpenAI",
                "sql_exec": "Tiempo de ejecución SQL y procesamiento de resultados"
            },
            "optimization_status": {
                "lazy_load_enabled": True,
                "duplicate_detection_enabled": True,
                "schema_cache_enabled": True,
                "db_instances_cache_enabled": True
            },
            # NUEVO: Resumen de readiness y fases
            "readiness_metrics": {
                "total_phases_tracked": len(self.phase_timings),
                "total_resources_tracked": len(self.resource_readiness_times),
                "users_currently_waiting": len([u for u in self.users_waiting.values() if u['status'] == 'waiting']),
                "total_users_completed": len([u for u in self.users_waiting.values() if u['status'] == 'completed'])
            }
        }
