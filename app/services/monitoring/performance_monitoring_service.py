"""
📊 Servicio de Monitoreo de Performance para el Sistema Explorer/Guided

Este servicio monitorea y mide:
- Métricas de tiempo de respuesta
- Cache hit ratio
- Uso de agentes por modo
- Performance general del sistema
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import statistics
import json

from app.core.service_factory import ServiceFactory
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.cache.response_cache_service import ResponseCacheService
from app.services.ai.agent_router_service import AgentRouterService

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Tipos de métricas"""
    RESPONSE_TIME = "response_time"
    CACHE_HIT_RATIO = "cache_hit_ratio"
    AGENT_USAGE = "agent_usage"
    MODE_DETECTION = "mode_detection"
    SYSTEM_PERFORMANCE = "system_performance"


class PerformanceThreshold(Enum):
    """Umbrales de performance"""
    EXCELLENT = "excellent"  # <100ms
    GOOD = "good"            # 100-300ms
    ACCEPTABLE = "acceptable" # 300-500ms
    SLOW = "slow"            # 500-1000ms
    POOR = "poor"            # >1000ms


@dataclass
class PerformanceMetric:
    """Métrica de performance individual"""
    metric_id: str
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class PerformanceSnapshot:
    """Snapshot de performance en un momento específico"""
    snapshot_id: str
    timestamp: datetime
    metrics: Dict[str, float]
    summary: Dict[str, Any]
    alerts: List[str] = field(default_factory=list)


class PerformanceMonitoringService:
    """
    📊 Servicio de Monitoreo de Performance
    
    Monitorea y mide el rendimiento del sistema Explorer/Guided
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.user_id = None  # Se establece al inicializar
        self.metrics_buffer: List[PerformanceMetric] = []
        self.performance_history: List[PerformanceSnapshot] = []
        self.active_monitoring = False
        
        # Configuración de monitoreo
        self.monitoring_config = {
            "buffer_size": 1000,
            "snapshot_interval": 60,  # 1 minuto
            "retention_days": 30,
            "alert_thresholds": {
                "response_time_ms": 1000,
                "cache_hit_ratio": 0.7,
                "error_rate": 0.05
            },
            "performance_targets": {
                "mode_detection_ms": 200,
                "agent_routing_ms": 150,
                "cache_response_ms": 50,
                "overall_response_ms": 500
            }
        }
        
        # Métricas en tiempo real
        self.real_time_metrics = {
            "response_times": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "agent_usage": {},
            "mode_detections": {},
            "errors": 0,
            "total_requests": 0
        }
        
        # Historial de métricas por tipo
        self.metric_history = {
            MetricType.RESPONSE_TIME: [],
            MetricType.CACHE_HIT_RATIO: [],
            MetricType.AGENT_USAGE: [],
            MetricType.MODE_DETECTION: [],
            MetricType.SYSTEM_PERFORMANCE: []
        }
        
        logger.info("[PerformanceMonitoringService] 📊 Servicio inicializado")
    
    async def initialize(self, user_id: str):
        """Inicializa el servicio para un usuario específico"""
        self.user_id = user_id
        logger.info(f"[PerformanceMonitoringService] Inicializado para usuario: {user_id}")
        
        # Cargar métricas históricas del usuario
        await self._load_historical_metrics()
        
        # Iniciar monitoreo automático
        await self._start_automatic_monitoring()
    
    async def _load_historical_metrics(self):
        """Carga métricas históricas del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, métricas vacías
            logger.debug(f"[PerformanceMonitoringService] Métricas históricas cargadas")
            
        except Exception as e:
            logger.warning(f"[PerformanceMonitoringService] ⚠️ Error cargando métricas históricas: {e}")
    
    async def _start_automatic_monitoring(self):
        """Inicia el monitoreo automático"""
        try:
            self.active_monitoring = True
            
            # Crear tarea de monitoreo periódico
            asyncio.create_task(self._periodic_monitoring())
            
            logger.info(f"[PerformanceMonitoringService] ✅ Monitoreo automático iniciado")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error iniciando monitoreo: {e}")
    
    async def _periodic_monitoring(self):
        """Monitoreo periódico del sistema"""
        while self.active_monitoring:
            try:
                # Crear snapshot de performance
                await self._create_performance_snapshot()
                
                # Analizar métricas para alertas
                await self._analyze_metrics_for_alerts()
                
                # Limpiar métricas antiguas
                await self._cleanup_old_metrics()
                
                # Esperar hasta la próxima ejecución
                await asyncio.sleep(self.monitoring_config["snapshot_interval"])
                
            except Exception as e:
                logger.error(f"[PerformanceMonitoringService] ❌ Error en monitoreo periódico: {e}")
                await asyncio.sleep(30)  # Esperar 30 segundos antes de reintentar
    
    async def _create_performance_snapshot(self):
        """Crea un snapshot de performance actual"""
        try:
            snapshot_id = f"snapshot_{int(time.time())}"
            timestamp = datetime.now()
            
            # Calcular métricas actuales
            current_metrics = await self._calculate_current_metrics()
            
            # Crear resumen
            summary = await self._create_performance_summary(current_metrics)
            
            # Crear snapshot
            snapshot = PerformanceSnapshot(
                snapshot_id=snapshot_id,
                timestamp=timestamp,
                metrics=current_metrics,
                summary=summary,
                alerts=[]
            )
            
            # Agregar a historial
            self.performance_history.append(snapshot)
            
            # Mantener solo los últimos N snapshots
            max_snapshots = (self.monitoring_config["retention_days"] * 24 * 60) // self.monitoring_config["snapshot_interval"]
            if len(self.performance_history) > max_snapshots:
                self.performance_history = self.performance_history[-max_snapshots:]
            
            logger.debug(f"[PerformanceMonitoringService] Snapshot creado: {snapshot_id}")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error creando snapshot: {e}")
    
    async def _calculate_current_metrics(self) -> Dict[str, float]:
        """Calcula métricas actuales del sistema"""
        try:
            metrics = {}
            
            # Métricas de tiempo de respuesta
            if self.real_time_metrics["response_times"]:
                metrics["avg_response_time_ms"] = statistics.mean(self.real_time_metrics["response_times"])
                metrics["min_response_time_ms"] = min(self.real_time_metrics["response_times"])
                metrics["max_response_time_ms"] = max(self.real_time_metrics["response_times"])
                metrics["p95_response_time_ms"] = self._calculate_percentile(self.real_time_metrics["response_times"], 95)
                metrics["p99_response_time_ms"] = self._calculate_percentile(self.real_time_metrics["response_times"], 99)
            else:
                metrics.update({
                    "avg_response_time_ms": 0.0,
                    "min_response_time_ms": 0.0,
                    "max_response_time_ms": 0.0,
                    "p95_response_time_ms": 0.0,
                    "p99_response_time_ms": 0.0
                })
            
            # Cache hit ratio
            total_cache_requests = self.real_time_metrics["cache_hits"] + self.real_time_metrics["cache_misses"]
            if total_cache_requests > 0:
                metrics["cache_hit_ratio"] = self.real_time_metrics["cache_hits"] / total_cache_requests
            else:
                metrics["cache_hit_ratio"] = 0.0
            
            # Métricas de agentes
            if self.real_time_metrics["agent_usage"]:
                total_agent_usage = sum(self.real_time_metrics["agent_usage"].values())
                for agent_id, usage_count in self.real_time_metrics["agent_usage"].items():
                    metrics[f"agent_{agent_id}_usage_ratio"] = usage_count / total_agent_usage if total_agent_usage > 0 else 0.0
            else:
                metrics["agent_usage_diversity"] = 0.0
            
            # Métricas de detección de modo
            if self.real_time_metrics["mode_detections"]:
                total_detections = sum(self.real_time_metrics["mode_detections"].values())
                for mode, count in self.real_time_metrics["mode_detections"].items():
                    metrics[f"mode_{mode}_detection_ratio"] = count / total_detections if total_detections > 0 else 0.0
            else:
                metrics["mode_detection_diversity"] = 0.0
            
            # Métricas generales
            metrics["total_requests"] = self.real_time_metrics["total_requests"]
            metrics["error_rate"] = self.real_time_metrics["errors"] / max(self.real_time_metrics["total_requests"], 1)
            metrics["requests_per_minute"] = self.real_time_metrics["total_requests"] / max(len(self.performance_history), 1)
            
            return metrics
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error calculando métricas: {e}")
            return {}
    
    async def _create_performance_summary(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Crea un resumen de performance basado en las métricas"""
        try:
            summary = {
                "overall_health": "unknown",
                "performance_score": 0.0,
                "bottlenecks": [],
                "recommendations": [],
                "trends": {}
            }
            
            # Calcular score de performance general
            performance_score = 0.0
            score_factors = []
            
            # Factor de tiempo de respuesta (40% del score)
            avg_response_time = metrics.get("avg_response_time_ms", 0.0)
            if avg_response_time <= 200:
                response_score = 1.0
            elif avg_response_time <= 500:
                response_score = 0.7
            elif avg_response_time <= 1000:
                response_score = 0.4
            else:
                response_score = 0.1
            
            performance_score += response_score * 0.4
            score_factors.append(f"Response time: {response_score:.2f}")
            
            # Factor de cache hit ratio (30% del score)
            cache_hit_ratio = metrics.get("cache_hit_ratio", 0.0)
            if cache_hit_ratio >= 0.8:
                cache_score = 1.0
            elif cache_hit_ratio >= 0.6:
                cache_score = 0.7
            elif cache_hit_ratio >= 0.4:
                cache_score = 0.4
            else:
                cache_score = 0.1
            
            performance_score += cache_score * 0.3
            score_factors.append(f"Cache hit ratio: {cache_score:.2f}")
            
            # Factor de error rate (20% del score)
            error_rate = metrics.get("error_rate", 0.0)
            if error_rate <= 0.01:
                error_score = 1.0
            elif error_rate <= 0.05:
                error_score = 0.7
            elif error_rate <= 0.1:
                error_score = 0.4
            else:
                error_score = 0.1
            
            performance_score += error_score * 0.2
            score_factors.append(f"Error rate: {error_score:.2f}")
            
            # Factor de diversidad de uso (10% del score)
            mode_diversity = metrics.get("mode_detection_diversity", 0.0)
            agent_diversity = metrics.get("agent_usage_diversity", 0.0)
            diversity_score = (mode_diversity + agent_diversity) / 2
            
            performance_score += diversity_score * 0.1
            score_factors.append(f"Diversity: {diversity_score:.2f}")
            
            summary["performance_score"] = performance_score
            summary["score_factors"] = score_factors
            
            # Determinar salud general
            if performance_score >= 0.8:
                summary["overall_health"] = "excellent"
            elif performance_score >= 0.6:
                summary["overall_health"] = "good"
            elif performance_score >= 0.4:
                summary["overall_health"] = "acceptable"
            elif performance_score >= 0.2:
                summary["overall_health"] = "poor"
            else:
                summary["overall_health"] = "critical"
            
            # Identificar bottlenecks
            bottlenecks = []
            if avg_response_time > 1000:
                bottlenecks.append("High response time - consider optimizing mode detection or agent routing")
            
            if cache_hit_ratio < 0.5:
                bottlenecks.append("Low cache hit ratio - consider improving cache warming or patterns")
            
            if error_rate > 0.1:
                bottlenecks.append("High error rate - investigate system errors or fallbacks")
            
            summary["bottlenecks"] = bottlenecks
            
            # Generar recomendaciones
            recommendations = []
            if avg_response_time > 500:
                recommendations.append("Optimize mode detection algorithms")
                recommendations.append("Implement response caching for common patterns")
            
            if cache_hit_ratio < 0.6:
                recommendations.append("Improve cache warming strategies")
                recommendations.append("Analyze user patterns for better pre-generation")
            
            if error_rate > 0.05:
                recommendations.append("Review error handling in fallback services")
                recommendations.append("Implement better user guidance for ambiguous inputs")
            
            summary["recommendations"] = recommendations
            
            return summary
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error creando resumen: {e}")
            return {"overall_health": "unknown", "performance_score": 0.0}
    
    async def _analyze_metrics_for_alerts(self):
        """Analiza métricas para generar alertas"""
        try:
            current_snapshot = self.performance_history[-1] if self.performance_history else None
            if not current_snapshot:
                return
            
            alerts = []
            metrics = current_snapshot.metrics
            
            # Alerta por tiempo de respuesta alto
            if metrics.get("avg_response_time_ms", 0) > self.monitoring_config["alert_thresholds"]["response_time_ms"]:
                alerts.append(f"High response time: {metrics['avg_response_time_ms']:.2f}ms")
            
            # Alerta por cache hit ratio bajo
            if metrics.get("cache_hit_ratio", 1.0) < self.monitoring_config["alert_thresholds"]["cache_hit_ratio"]:
                alerts.append(f"Low cache hit ratio: {metrics['cache_hit_ratio']:.2%}")
            
            # Alerta por error rate alto
            if metrics.get("error_rate", 0.0) > self.monitoring_config["alert_thresholds"]["error_rate"]:
                alerts.append(f"High error rate: {metrics['error_rate']:.2%}")
            
            # Alerta por performance score bajo
            if current_snapshot.summary.get("performance_score", 1.0) < 0.4:
                alerts.append(f"Low performance score: {current_snapshot.summary['performance_score']:.2f}")
            
            # Actualizar snapshot con alertas
            current_snapshot.alerts = alerts
            
            # Log de alertas
            if alerts:
                logger.warning(f"[PerformanceMonitoringService] ⚠️ Alertas de performance: {alerts}")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error analizando alertas: {e}")
    
    async def _cleanup_old_metrics(self):
        """Limpia métricas antiguas"""
        try:
            cutoff_time = datetime.now() - timedelta(days=self.monitoring_config["retention_days"])
            
            # Limpiar métricas del buffer
            self.metrics_buffer = [
                m for m in self.metrics_buffer 
                if m.timestamp > cutoff_time
            ]
            
            # Limpiar métricas del historial por tipo
            for metric_type in self.metric_history:
                self.metric_history[metric_type] = [
                    m for m in self.metric_history[metric_type]
                    if m.timestamp > cutoff_time
                ]
            
            logger.debug(f"[PerformanceMonitoringService] Limpieza de métricas antiguas completada")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error limpiando métricas: {e}")
    
    def record_response_time(self, operation: str, response_time_ms: float, context: Dict[str, Any] = None):
        """Registra tiempo de respuesta de una operación"""
        try:
            # Agregar a métricas en tiempo real
            self.real_time_metrics["response_times"].append(response_time_ms)
            
            # Mantener solo las últimas 1000 métricas
            if len(self.real_time_metrics["response_times"]) > 1000:
                self.real_time_metrics["response_times"] = self.real_time_metrics["response_times"][-1000:]
            
            # Crear métrica
            metric = PerformanceMetric(
                metric_id=f"response_time_{int(time.time() * 1000)}",
                metric_type=MetricType.RESPONSE_TIME,
                value=response_time_ms,
                unit="ms",
                timestamp=datetime.now(),
                context=context or {},
                user_id=self.user_id
            )
            
            # Agregar al buffer
            self.metrics_buffer.append(metric)
            
            # Agregar al historial por tipo
            self.metric_history[MetricType.RESPONSE_TIME].append(metric)
            
            # Incrementar contador de requests
            self.real_time_metrics["total_requests"] += 1
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando tiempo de respuesta: {e}")
    
    def record_cache_hit(self, cache_level: str, response_time_ms: float):
        """Registra un cache hit"""
        try:
            self.real_time_metrics["cache_hits"] += 1
            
            # Registrar métrica de cache
            metric = PerformanceMetric(
                metric_id=f"cache_hit_{int(time.time() * 1000)}",
                metric_type=MetricType.CACHE_HIT_RATIO,
                value=1.0,  # 1.0 = hit, 0.0 = miss
                unit="hit",
                timestamp=datetime.now(),
                context={"cache_level": cache_level, "response_time_ms": response_time_ms},
                user_id=self.user_id
            )
            
            self.metrics_buffer.append(metric)
            self.metric_history[MetricType.CACHE_HIT_RATIO].append(metric)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando cache hit: {e}")
    
    def record_cache_miss(self, cache_level: str, response_time_ms: float):
        """Registra un cache miss"""
        try:
            self.real_time_metrics["cache_misses"] += 1
            
            # Registrar métrica de cache
            metric = PerformanceMetric(
                metric_id=f"cache_miss_{int(time.time() * 1000)}",
                metric_type=MetricType.CACHE_HIT_RATIO,
                value=0.0,  # 1.0 = hit, 0.0 = miss
                unit="miss",
                timestamp=datetime.now(),
                context={"cache_level": cache_level, "response_time_ms": response_time_ms},
                user_id=self.user_id
            )
            
            self.metrics_buffer.append(metric)
            self.metric_history[MetricType.CACHE_HIT_RATIO].append(metric)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando cache miss: {e}")
    
    def record_agent_usage(self, agent_id: str, mode: str, response_time_ms: float):
        """Registra uso de un agente"""
        try:
            # Incrementar contador de uso
            if agent_id not in self.real_time_metrics["agent_usage"]:
                self.real_time_metrics["agent_usage"][agent_id] = 0
            self.real_time_metrics["agent_usage"][agent_id] += 1
            
            # Registrar métrica de agente
            metric = PerformanceMetric(
                metric_id=f"agent_usage_{int(time.time() * 1000)}",
                metric_type=MetricType.AGENT_USAGE,
                value=response_time_ms,
                unit="ms",
                timestamp=datetime.now(),
                context={"agent_id": agent_id, "mode": mode},
                user_id=self.user_id
            )
            
            self.metrics_buffer.append(metric)
            self.metric_history[MetricType.AGENT_USAGE].append(metric)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando uso de agente: {e}")
    
    def record_mode_detection(self, mode: str, confidence: float, response_time_ms: float):
        """Registra detección de modo"""
        try:
            # Incrementar contador de detección
            if mode not in self.real_time_metrics["mode_detections"]:
                self.real_time_metrics["mode_detections"][mode] = 0
            self.real_time_metrics["mode_detections"][mode] += 1
            
            # Registrar métrica de detección de modo
            metric = PerformanceMetric(
                metric_id=f"mode_detection_{int(time.time() * 1000)}",
                metric_type=MetricType.MODE_DETECTION,
                value=response_time_ms,
                unit="ms",
                timestamp=datetime.now(),
                context={"mode": mode, "confidence": confidence},
                user_id=self.user_id
            )
            
            self.metrics_buffer.append(metric)
            self.metric_history[MetricType.MODE_DETECTION].append(metric)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando detección de modo: {e}")
    
    def record_error(self, error_type: str, error_message: str):
        """Registra un error del sistema"""
        try:
            self.real_time_metrics["errors"] += 1
            
            # Registrar métrica de error
            metric = PerformanceMetric(
                metric_id=f"error_{int(time.time() * 1000)}",
                metric_type=MetricType.SYSTEM_PERFORMANCE,
                value=1.0,  # 1.0 = error occurred
                unit="error",
                timestamp=datetime.now(),
                context={"error_type": error_type, "error_message": error_message},
                user_id=self.user_id
            )
            
            self.metrics_buffer.append(metric)
            self.metric_history[MetricType.SYSTEM_PERFORMANCE].append(metric)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error registrando error: {e}")
    
    async def get_performance_summary(self, time_range: str = "1h") -> Dict[str, Any]:
        """Obtiene resumen de performance para un rango de tiempo"""
        try:
            # Calcular rango de tiempo
            now = datetime.now()
            if time_range == "1h":
                start_time = now - timedelta(hours=1)
            elif time_range == "24h":
                start_time = now - timedelta(days=1)
            elif time_range == "7d":
                start_time = now - timedelta(days=7)
            elif time_range == "30d":
                start_time = now - timedelta(days=30)
            else:
                start_time = now - timedelta(hours=1)
            
            # Filtrar snapshots por rango de tiempo
            relevant_snapshots = [
                s for s in self.performance_history
                if s.timestamp >= start_time
            ]
            
            if not relevant_snapshots:
                return {"error": "No hay datos para el rango de tiempo especificado"}
            
            # Calcular métricas agregadas
            summary = {
                "time_range": time_range,
                "snapshots_count": len(relevant_snapshots),
                "current_health": relevant_snapshots[-1].summary.get("overall_health", "unknown"),
                "current_score": relevant_snapshots[-1].summary.get("performance_score", 0.0),
                "trends": {},
                "alerts": [],
                "recommendations": []
            }
            
            # Calcular tendencias
            if len(relevant_snapshots) > 1:
                first_score = relevant_snapshots[0].summary.get("performance_score", 0.0)
                last_score = relevant_snapshots[-1].summary.get("performance_score", 0.0)
                
                if last_score > first_score:
                    summary["trends"]["performance"] = "improving"
                elif last_score < first_score:
                    summary["trends"]["performance"] = "declining"
                else:
                    summary["trends"]["performance"] = "stable"
            
            # Agregar alertas recientes
            for snapshot in relevant_snapshots[-5:]:  # Últimos 5 snapshots
                summary["alerts"].extend(snapshot.alerts)
            
            # Agregar recomendaciones del snapshot más reciente
            summary["recommendations"] = relevant_snapshots[-1].summary.get("recommendations", [])
            
            return summary
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error obteniendo resumen: {e}")
            return {"error": str(e)}
    
    async def get_detailed_metrics(self, metric_type: MetricType, time_range: str = "1h") -> List[Dict[str, Any]]:
        """Obtiene métricas detalladas de un tipo específico"""
        try:
            # Calcular rango de tiempo
            now = datetime.now()
            if time_range == "1h":
                start_time = now - timedelta(hours=1)
            elif time_range == "24h":
                start_time = now - timedelta(days=1)
            elif time_range == "7d":
                start_time = now - timedelta(days=7)
            else:
                start_time = now - timedelta(hours=1)
            
            # Filtrar métricas por tipo y tiempo
            relevant_metrics = [
                m for m in self.metric_history.get(metric_type, [])
                if m.timestamp >= start_time
            ]
            
            # Convertir a formato serializable
            metrics_data = []
            for metric in relevant_metrics:
                metrics_data.append({
                    "metric_id": metric.metric_id,
                    "value": metric.value,
                    "unit": metric.unit,
                    "timestamp": metric.timestamp.isoformat(),
                    "context": metric.context
                })
            
            return metrics_data
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error obteniendo métricas detalladas: {e}")
            return []
    
    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calcula el percentil de una lista de valores"""
        try:
            if not values:
                return 0.0
            
            sorted_values = sorted(values)
            index = (percentile / 100) * (len(sorted_values) - 1)
            
            if index.is_integer():
                return sorted_values[int(index)]
            else:
                lower_index = int(index)
                upper_index = lower_index + 1
                weight = index - lower_index
                
                return (sorted_values[lower_index] * (1 - weight) + 
                       sorted_values[upper_index] * weight)
                
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error calculando percentil: {e}")
            return 0.0
    
    async def cleanup(self):
        """Limpia recursos del servicio"""
        try:
            self.active_monitoring = False
            
            # Limpiar métricas en tiempo real
            self.real_time_metrics = {
                "response_times": [],
                "cache_hits": 0,
                "cache_misses": 0,
                "agent_usage": {},
                "mode_detections": {},
                "errors": 0,
                "total_requests": 0
            }
            
            logger.info(f"[PerformanceMonitoringService] 🧹 Limpieza completada")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error en limpieza: {e}")


# Factory function para crear el servicio
async def create_performance_monitoring_service(factory: ServiceFactory, user_id: str) -> PerformanceMonitoringService:
    """Crea e inicializa el servicio de monitoreo de performance"""
    service = PerformanceMonitoringService(factory)
    await service.initialize(user_id)
    return service
