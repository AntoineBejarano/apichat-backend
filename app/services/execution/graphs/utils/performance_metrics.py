import time
import logging
from typing import Dict, Any

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
        self.overall_start_time = None
    
    def start_overall_timer(self):
        """Inicia el timer general"""
        self.overall_start_time = time.time()
    
    def record_node_time(self, node_name: str, node_time: float):
        """Registra el tiempo de un nodo específico"""
        if node_name in self.metrics:
            self.metrics[node_name] = node_time
            logger.info(f"[PerformanceMetrics] 📊 Performance - {node_name}: {node_time:.3f}s")
    
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
    
    def get_metrics(self) -> Dict[str, Any]:
        """Obtiene las métricas actuales incluyendo tokens"""
        return {
            "performance": self.metrics.copy(),
            "tokens": self.token_metrics.copy()
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
            }
        }
