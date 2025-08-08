# app/services/performance_monitoring_service.py
"""
PerformanceMonitoringService - Nivel Unicornio 🦄
─────────────────────────────────────────────────
Servicio de monitoreo de performance avanzado con métricas detalladas.
Combina métricas de sistema, base de datos y aplicación.
"""

import logging
import psutil
import time
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import asyncio
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """Métricas del sistema"""
    cpu_percent: float
    memory_percent: float
    memory_available: int
    disk_usage_percent: float
    network_io: Dict[str, int]
    load_average: Tuple[float, float, float]


@dataclass
class DatabaseMetrics:
    """Métricas de base de datos"""
    active_connections: int
    total_queries: int
    slow_queries: int
    avg_query_time: float
    cache_hit_rate: float
    index_usage: Dict[str, int]


@dataclass
class ApplicationMetrics:
    """Métricas de aplicación"""
    requests_per_second: float
    avg_response_time: float
    error_rate: float
    active_users: int
    memory_usage: int
    uptime: timedelta


@dataclass
class PerformanceAlert:
    """Alerta de performance"""
    level: str  # "info", "warning", "critical"
    message: str
    metric: str
    value: float
    threshold: float
    timestamp: datetime


class PerformanceMonitoringService:
    """
    Servicio de monitoreo de performance avanzado.
    """
    
    def __init__(self, monitoring_interval: int = 30):
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self.monitoring_thread = None
        
        # Métricas históricas
        self.system_history = deque(maxlen=1000)
        self.database_history = deque(maxlen=1000)
        self.application_history = deque(maxlen=1000)
        
        # Alertas
        self.alerts = deque(maxlen=100)
        self.alert_thresholds = self._load_alert_thresholds()
        
        # Estadísticas
        self.monitoring_stats = {
            "total_metrics_collected": 0,
            "alerts_generated": 0,
            "monitoring_uptime": timedelta(0),
            "last_collection": None
        }
        
        # Métricas en tiempo real
        self.current_metrics = {
            "system": None,
            "database": None,
            "application": None
        }
        
        logger.info("[PerformanceMonitoringService] 🦄 Inicializado con monitoreo avanzado")
    
    def _load_alert_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Cargar umbrales de alerta"""
        return {
            "system": {
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_usage_percent": 90.0
            },
            "database": {
                "avg_query_time": 2.0,  # segundos
                "slow_queries_percent": 10.0,
                "cache_hit_rate": 70.0
            },
            "application": {
                "avg_response_time": 1.0,  # segundos
                "error_rate": 5.0,
                "requests_per_second": 1000.0
            }
        }
    
    def start_monitoring(self) -> None:
        """Iniciar monitoreo continuo"""
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            logger.info("[PerformanceMonitoringService] 🚀 Monitoreo iniciado")
    
    def stop_monitoring(self) -> None:
        """Detener monitoreo"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("[PerformanceMonitoringService] 🛑 Monitoreo detenido")
    
    def _monitoring_loop(self) -> None:
        """Loop principal de monitoreo"""
        start_time = datetime.now()
        
        while self.is_monitoring:
            try:
                # Recolectar métricas
                self._collect_all_metrics()
                
                # Verificar alertas
                self._check_alerts()
                
                # Actualizar estadísticas
                self.monitoring_stats["total_metrics_collected"] += 1
                self.monitoring_stats["monitoring_uptime"] = datetime.now() - start_time
                self.monitoring_stats["last_collection"] = datetime.now()
                
                # Esperar hasta la siguiente colección
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"[PerformanceMonitoringService] ❌ Error en loop de monitoreo: {e}")
                time.sleep(5)  # Esperar antes de reintentar
    
    def _collect_all_metrics(self) -> None:
        """Recolectar todas las métricas"""
        try:
            # Métricas del sistema
            system_metrics = self._collect_system_metrics()
            self.current_metrics["system"] = system_metrics
            self.system_history.append(system_metrics)
            
            # Métricas de base de datos
            database_metrics = self._collect_database_metrics()
            self.current_metrics["database"] = database_metrics
            self.database_history.append(database_metrics)
            
            # Métricas de aplicación
            application_metrics = self._collect_application_metrics()
            self.current_metrics["application"] = application_metrics
            self.application_history.append(application_metrics)
            
            logger.debug("[PerformanceMonitoringService] 📊 Métricas recolectadas")
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error recolectando métricas: {e}")
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Recolectar métricas del sistema"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memoria
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            
            # Disco
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # Red
            network = psutil.net_io_counters()
            network_io = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
            
            # Load average (solo en Unix)
            try:
                load_avg = psutil.getloadavg()
            except AttributeError:
                load_avg = (0.0, 0.0, 0.0)
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available=memory_available,
                disk_usage_percent=disk_usage_percent,
                network_io=network_io,
                load_average=load_avg
            )
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error recolectando métricas del sistema: {e}")
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available=0,
                disk_usage_percent=0.0,
                network_io={},
                load_average=(0.0, 0.0, 0.0)
            )
    
    def _collect_database_metrics(self) -> DatabaseMetrics:
        """Recolectar métricas de base de datos"""
        try:
            # Métricas simuladas - en producción se conectaría a la BD
            active_connections = 5  # Simulado
            total_queries = 1000  # Simulado
            slow_queries = 50  # Simulado
            avg_query_time = 0.5  # Simulado
            cache_hit_rate = 85.0  # Simulado
            index_usage = {"primary": 100, "secondary": 50}  # Simulado
            
            return DatabaseMetrics(
                active_connections=active_connections,
                total_queries=total_queries,
                slow_queries=slow_queries,
                avg_query_time=avg_query_time,
                cache_hit_rate=cache_hit_rate,
                index_usage=index_usage
            )
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error recolectando métricas de BD: {e}")
            return DatabaseMetrics(
                active_connections=0,
                total_queries=0,
                slow_queries=0,
                avg_query_time=0.0,
                cache_hit_rate=0.0,
                index_usage={}
            )
    
    def _collect_application_metrics(self) -> ApplicationMetrics:
        """Recolectar métricas de aplicación"""
        try:
            # Métricas simuladas - en producción se obtendrían del sistema
            requests_per_second = 150.0  # Simulado
            avg_response_time = 0.3  # Simulado
            error_rate = 2.0  # Simulado
            active_users = 25  # Simulado
            memory_usage = psutil.Process().memory_info().rss  # Real
            uptime = timedelta(hours=24)  # Simulado
            
            return ApplicationMetrics(
                requests_per_second=requests_per_second,
                avg_response_time=avg_response_time,
                error_rate=error_rate,
                active_users=active_users,
                memory_usage=memory_usage,
                uptime=uptime
            )
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error recolectando métricas de app: {e}")
            return ApplicationMetrics(
                requests_per_second=0.0,
                avg_response_time=0.0,
                error_rate=0.0,
                active_users=0,
                memory_usage=0,
                uptime=timedelta(0)
            )
    
    def _check_alerts(self) -> None:
        """Verificar y generar alertas"""
        try:
            current_time = datetime.now()
            
            # Verificar métricas del sistema
            if self.current_metrics["system"]:
                system = self.current_metrics["system"]
                
                if system.cpu_percent > self.alert_thresholds["system"]["cpu_percent"]:
                    self._create_alert("warning", "CPU", system.cpu_percent, 
                                     self.alert_thresholds["system"]["cpu_percent"], current_time)
                
                if system.memory_percent > self.alert_thresholds["system"]["memory_percent"]:
                    self._create_alert("warning", "Memory", system.memory_percent,
                                     self.alert_thresholds["system"]["memory_percent"], current_time)
                
                if system.disk_usage_percent > self.alert_thresholds["system"]["disk_usage_percent"]:
                    self._create_alert("critical", "Disk", system.disk_usage_percent,
                                     self.alert_thresholds["system"]["disk_usage_percent"], current_time)
            
            # Verificar métricas de base de datos
            if self.current_metrics["database"]:
                database = self.current_metrics["database"]
                
                if database.avg_query_time > self.alert_thresholds["database"]["avg_query_time"]:
                    self._create_alert("warning", "Query Time", database.avg_query_time,
                                     self.alert_thresholds["database"]["avg_query_time"], current_time)
                
                if database.cache_hit_rate < self.alert_thresholds["database"]["cache_hit_rate"]:
                    self._create_alert("warning", "Cache Hit Rate", database.cache_hit_rate,
                                     self.alert_thresholds["database"]["cache_hit_rate"], current_time)
            
            # Verificar métricas de aplicación
            if self.current_metrics["application"]:
                application = self.current_metrics["application"]
                
                if application.avg_response_time > self.alert_thresholds["application"]["avg_response_time"]:
                    self._create_alert("warning", "Response Time", application.avg_response_time,
                                     self.alert_thresholds["application"]["avg_response_time"], current_time)
                
                if application.error_rate > self.alert_thresholds["application"]["error_rate"]:
                    self._create_alert("critical", "Error Rate", application.error_rate,
                                     self.alert_thresholds["application"]["error_rate"], current_time)
            
        except Exception as e:
            logger.error(f"[PerformanceMonitoringService] ❌ Error verificando alertas: {e}")
    
    def _create_alert(self, level: str, metric: str, value: float, threshold: float, timestamp: datetime) -> None:
        """Crear una nueva alerta"""
        alert = PerformanceAlert(
            level=level,
            message=f"{metric} {level.upper()}: {value:.2f} (threshold: {threshold:.2f})",
            metric=metric,
            value=value,
            threshold=threshold,
            timestamp=timestamp
        )
        
        self.alerts.append(alert)
        self.monitoring_stats["alerts_generated"] += 1
        
        logger.warning(f"[PerformanceMonitoringService] 🚨 {alert.message}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Obtener métricas actuales"""
        return {
            "system": self.current_metrics["system"].__dict__ if self.current_metrics["system"] else None,
            "database": self.current_metrics["database"].__dict__ if self.current_metrics["database"] else None,
            "application": self.current_metrics["application"].__dict__ if self.current_metrics["application"] else None,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_historical_metrics(self, hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Obtener métricas históricas"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        system_history = [
            {"timestamp": getattr(metric, 'timestamp', datetime.now()).isoformat(), **metric.__dict__}
            for metric in self.system_history
            if hasattr(metric, 'timestamp') and metric.timestamp > cutoff_time
        ]
        
        database_history = [
            {"timestamp": getattr(metric, 'timestamp', datetime.now()).isoformat(), **metric.__dict__}
            for metric in self.database_history
            if hasattr(metric, 'timestamp') and metric.timestamp > cutoff_time
        ]
        
        application_history = [
            {"timestamp": getattr(metric, 'timestamp', datetime.now()).isoformat(), **metric.__dict__}
            for metric in self.application_history
            if hasattr(metric, 'timestamp') and metric.timestamp > cutoff_time
        ]
        
        return {
            "system": system_history,
            "database": database_history,
            "application": application_history
        }
    
    def get_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Obtener alertas recientes"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_alerts = [
            {
                "level": alert.level,
                "message": alert.message,
                "metric": alert.metric,
                "value": alert.value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat()
            }
            for alert in self.alerts
            if alert.timestamp > cutoff_time
        ]
        
        return recent_alerts
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtener resumen de performance"""
        if not self.current_metrics["system"]:
            return {"status": "No metrics available"}
        
        system = self.current_metrics["system"]
        database = self.current_metrics["database"]
        application = self.current_metrics["application"]
        
        # Calcular scores de health
        system_health = self._calculate_system_health(system)
        database_health = self._calculate_database_health(database) if database else 0.0
        application_health = self._calculate_application_health(application) if application else 0.0
        
        # Overall health score
        overall_health = (system_health + database_health + application_health) / 3
        
        return {
            "overall_health": overall_health,
            "system_health": system_health,
            "database_health": database_health,
            "application_health": application_health,
            "status": self._get_health_status(overall_health),
            "recommendations": self._generate_recommendations(system, database, application),
            "last_updated": datetime.now().isoformat()
        }
    
    def _calculate_system_health(self, system: SystemMetrics) -> float:
        """Calcular health score del sistema"""
        if not system:
            return 0.0
        
        # CPU: 0-100% -> 100-0 score
        cpu_score = max(0, 100 - system.cpu_percent)
        
        # Memory: 0-100% -> 100-0 score
        memory_score = max(0, 100 - system.memory_percent)
        
        # Disk: 0-100% -> 100-0 score
        disk_score = max(0, 100 - system.disk_usage_percent)
        
        # Promedio ponderado
        return (cpu_score * 0.4 + memory_score * 0.4 + disk_score * 0.2) / 100
    
    def _calculate_database_health(self, database: DatabaseMetrics) -> float:
        """Calcular health score de la base de datos"""
        if not database:
            return 0.0
        
        # Query time: 0-2s -> 100-0 score
        query_time_score = max(0, 100 - (database.avg_query_time * 50))
        
        # Cache hit rate: 0-100% -> 0-100 score
        cache_score = database.cache_hit_rate
        
        # Slow queries: 0-10% -> 100-0 score
        slow_query_percent = (database.slow_queries / max(database.total_queries, 1)) * 100
        slow_query_score = max(0, 100 - slow_query_percent * 10)
        
        return (query_time_score * 0.4 + cache_score * 0.4 + slow_query_score * 0.2) / 100
    
    def _calculate_application_health(self, application: ApplicationMetrics) -> float:
        """Calcular health score de la aplicación"""
        if not application:
            return 0.0
        
        # Response time: 0-1s -> 100-0 score
        response_score = max(0, 100 - (application.avg_response_time * 100))
        
        # Error rate: 0-5% -> 100-0 score
        error_score = max(0, 100 - application.error_rate * 20)
        
        # Requests per second: 0-1000 -> 0-100 score
        rps_score = min(100, application.requests_per_second / 10)
        
        return (response_score * 0.4 + error_score * 0.4 + rps_score * 0.2) / 100
    
    def _get_health_status(self, health_score: float) -> str:
        """Obtener status basado en health score"""
        if health_score >= 0.8:
            return "excellent"
        elif health_score >= 0.6:
            return "good"
        elif health_score >= 0.4:
            return "fair"
        else:
            return "poor"
    
    def _generate_recommendations(self, system: SystemMetrics, database: DatabaseMetrics, application: ApplicationMetrics) -> List[str]:
        """Generar recomendaciones basadas en métricas"""
        recommendations = []
        
        if system:
            if system.cpu_percent > 70:
                recommendations.append("⚡ CPU alta - considerar optimización de procesos")
            if system.memory_percent > 80:
                recommendations.append("💾 Memoria alta - revisar uso de memoria")
            if system.disk_usage_percent > 85:
                recommendations.append("💿 Disco casi lleno - limpiar archivos temporales")
        
        if database:
            if database.avg_query_time > 1.0:
                recommendations.append("🔍 Queries lentas - revisar índices")
            if database.cache_hit_rate < 80:
                recommendations.append("🎯 Cache hit rate baja - optimizar queries")
        
        if application:
            if application.avg_response_time > 0.5:
                recommendations.append("⏱️ Tiempo de respuesta alto - optimizar código")
            if application.error_rate > 2:
                recommendations.append("❌ Error rate alto - revisar logs")
        
        return recommendations
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de monitoreo"""
        return {
            "total_metrics_collected": self.monitoring_stats["total_metrics_collected"],
            "alerts_generated": self.monitoring_stats["alerts_generated"],
            "monitoring_uptime": str(self.monitoring_stats["monitoring_uptime"]),
            "last_collection": self.monitoring_stats["last_collection"].isoformat() if self.monitoring_stats["last_collection"] else None,
            "is_monitoring": self.is_monitoring,
            "monitoring_interval": self.monitoring_interval
        }
