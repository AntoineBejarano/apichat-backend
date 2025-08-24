"""
📊 Schema Performance Service: Integración de métricas existentes

Este servicio INTEGRA (no duplica) todos los servicios de monitoring,
rate limiting y cleanup existentes para crear un dashboard unificado
de performance de schemas.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from app.services.management.performance_monitoring_service import PerformanceMonitoringService
from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.cache.redis_schema_cache import RedisSchemaCache
from app.services.background.schema_maintenance_service import SchemaMaintenanceService
from app.services.notifications.schema_notification_service import SchemaNotificationService

logger = logging.getLogger(__name__)


class SchemaPerformanceService:
    """
    📊 Servicio de performance unificado para schemas
    
    INTEGRA servicios existentes:
    - PerformanceMonitoringService (métricas)
    - DetailedSchemaCacheService (cache)
    - RedisSchemaCache (Redis)
    - SchemaMaintenanceService (cleanup)
    - SchemaNotificationService (notificaciones)
    """
    
    def __init__(self, factory):
        """
        Inicializa el servicio integrando servicios existentes
        
        Args:
            factory: ServiceFactory para obtener servicios
        """
        self.factory = factory
        
        # Integrar servicios existentes (NO crear nuevos)
        self.performance_service = None
        self.cache_service = None
        self.redis_cache = None
        self.maintenance_service = None
        self.notification_service = None
        
        logger.info("[SchemaPerformanceService] 🚀 Inicializando integración de métricas existentes")
    
    async def _get_services(self):
        """Obtiene servicios existentes de forma lazy"""
        try:
            if not self.performance_service:
                self.performance_service = self.factory.get_performance_monitoring_service()
            
            if not self.cache_service:
                self.cache_service = self.factory.get_detailed_schema_cache_service()
            
            if not self.redis_cache:
                self.redis_cache = self.factory.get_redis_schema_cache()
            
            if not self.maintenance_service:
                self.maintenance_service = self.factory.get_schema_maintenance_service()
            
            if not self.notification_service:
                self.notification_service = self.factory.get_schema_notification_service()
                
        except Exception as e:
            logger.warning(f"[SchemaPerformanceService] ⚠️ Algunos servicios no disponibles: {e}")
    
    async def get_schema_performance_dashboard(self, user_id: UUID) -> Dict[str, Any]:
        """
        Obtiene dashboard unificado de performance de schemas
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Dashboard con todas las métricas integradas
        """
        try:
            await self._get_services()
            
            # Recolectar métricas de servicios existentes
            cache_metrics = await self._get_cache_metrics(user_id)
            redis_metrics = await self._get_redis_metrics(user_id)
            maintenance_metrics = await self._get_maintenance_metrics(user_id)
            notification_metrics = await self._get_notification_metrics(user_id)
            
            # Integrar métricas en dashboard unificado
            dashboard = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id),
                "cache_performance": cache_metrics,
                "redis_performance": redis_metrics,
                "maintenance_status": maintenance_metrics,
                "notification_stats": notification_metrics,
                "overall_health": self._calculate_overall_health(
                    cache_metrics, redis_metrics, maintenance_metrics
                )
            }
            
            logger.info(f"[SchemaPerformanceService] 📊 Dashboard generado para usuario {user_id}")
            return dashboard
            
        except Exception as e:
            logger.error(f"[SchemaPerformanceService] ❌ Error generando dashboard: {e}")
            return {"error": str(e)}
    
    async def _get_cache_metrics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene métricas del servicio de cache existente"""
        try:
            if not self.cache_service:
                return {"status": "service_unavailable"}
            
            # Usar métodos existentes del DetailedSchemaCacheService
            cache_stats = await self.cache_service.get_cache_statistics(user_id)
            
            return {
                "total_schemas": cache_stats.get("total_schemas", 0),
                "cached_schemas": cache_stats.get("cached_schemas", 0),
                "hit_ratio": cache_stats.get("hit_ratio", 0.0),
                "average_response_time": cache_stats.get("avg_response_time", 0.0),
                "cache_size_mb": cache_stats.get("cache_size_mb", 0.0),
                "last_updated": cache_stats.get("last_updated")
            }
            
        except Exception as e:
            logger.warning(f"[SchemaPerformanceService] ⚠️ Error obteniendo métricas de cache: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_redis_metrics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene métricas del Redis cache existente"""
        try:
            if not self.redis_cache:
                return {"status": "service_unavailable"}
            
            # Usar métodos existentes del RedisSchemaCache
            redis_stats = await self.redis_cache.get_redis_statistics()
            
            return {
                "redis_connected": redis_stats.get("connected", False),
                "total_keys": redis_stats.get("total_keys", 0),
                "memory_usage_mb": redis_stats.get("memory_usage_mb", 0.0),
                "hit_count": redis_stats.get("hit_count", 0),
                "miss_count": redis_stats.get("miss_count", 0),
                "ttl_average": redis_stats.get("ttl_average", 0)
            }
            
        except Exception as e:
            logger.warning(f"[SchemaPerformanceService] ⚠️ Error obteniendo métricas de Redis: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_maintenance_metrics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene métricas del servicio de mantenimiento existente"""
        try:
            if not self.maintenance_service:
                return {"status": "service_unavailable"}
            
            # Usar métodos existentes del SchemaMaintenanceService
            maintenance_report = await self.maintenance_service.get_maintenance_report()
            
            return {
                "last_maintenance": maintenance_report.get("last_maintenance"),
                "caches_cleaned": maintenance_report.get("caches_cleaned", 0),
                "storage_freed_mb": maintenance_report.get("storage_freed_mb", 0.0),
                "weekly_cleanup_enabled": maintenance_report.get("weekly_cleanup_enabled", False),
                "errors_count": len(maintenance_report.get("errors", [])),
                "next_scheduled": maintenance_report.get("next_scheduled")
            }
            
        except Exception as e:
            logger.warning(f"[SchemaPerformanceService] ⚠️ Error obteniendo métricas de mantenimiento: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _get_notification_metrics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene métricas del servicio de notificaciones existente"""
        try:
            if not self.notification_service:
                return {"status": "service_unavailable"}
            
            # Usar métodos existentes del SchemaNotificationService
            notification_stats = self.notification_service.get_notification_statistics()
            
            return {
                "total_notifications": notification_stats.get("total_notifications", 0),
                "successful_deliveries": notification_stats.get("successful_deliveries", 0),
                "failed_deliveries": notification_stats.get("failed_deliveries", 0),
                "rate_limiting_enabled": notification_stats.get("rate_limiting_enabled", False),
                "active_subscriptions": notification_stats.get("active_subscriptions", 0),
                "last_notification": notification_stats.get("last_notification")
            }
            
        except Exception as e:
            logger.warning(f"[SchemaPerformanceService] ⚠️ Error obteniendo métricas de notificaciones: {e}")
            return {"status": "error", "message": str(e)}
    
    def _calculate_overall_health(
        self, 
        cache_metrics: Dict[str, Any], 
        redis_metrics: Dict[str, Any], 
        maintenance_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calcula salud general del sistema basado en métricas existentes"""
        try:
            # Calcular score de salud (0-100)
            health_score = 100
            
            # Cache health (40% del score)
            if cache_metrics.get("status") == "error":
                health_score -= 40
            elif cache_metrics.get("hit_ratio", 0) < 0.8:
                health_score -= 20
            
            # Redis health (30% del score)
            if redis_metrics.get("status") == "error":
                health_score -= 30
            elif not redis_metrics.get("redis_connected", False):
                health_score -= 30
            
            # Maintenance health (30% del score)
            if maintenance_metrics.get("status") == "error":
                health_score -= 30
            elif maintenance_metrics.get("errors_count", 0) > 5:
                health_score -= 15
            
            # Determinar estado
            if health_score >= 90:
                status = "excellent"
                color = "🟢"
            elif health_score >= 70:
                status = "good"
                color = "🟡"
            elif health_score >= 50:
                status = "warning"
                color = "🟠"
            else:
                status = "critical"
                color = "🔴"
            
            return {
                "score": max(0, health_score),
                "status": status,
                "color": color,
                "last_calculated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SchemaPerformanceService] ❌ Error calculando salud: {e}")
            return {
                "score": 0,
                "status": "error",
                "color": "🔴",
                "error": str(e)
            }
    
    async def get_performance_alerts(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Obtiene alertas de performance basadas en métricas existentes"""
        try:
            await self._get_services()
            
            alerts = []
            
            # Verificar cache performance
            cache_metrics = await self._get_cache_metrics(user_id)
            if cache_metrics.get("hit_ratio", 1.0) < 0.8:
                alerts.append({
                    "type": "cache_performance",
                    "severity": "warning",
                    "message": f"Cache hit ratio bajo: {cache_metrics.get('hit_ratio', 0):.1%}",
                    "recommendation": "Revisar configuración de cache y TTLs"
                })
            
            # Verificar Redis health
            redis_metrics = await self._get_redis_metrics(user_id)
            if not redis_metrics.get("redis_connected", False):
                alerts.append({
                    "type": "redis_connection",
                    "severity": "critical",
                    "message": "Redis no está conectado",
                    "recommendation": "Verificar conexión Redis y configuración"
                })
            
            # Verificar mantenimiento
            maintenance_metrics = await self._get_maintenance_metrics(user_id)
            if maintenance_metrics.get("errors_count", 0) > 5:
                alerts.append({
                    "type": "maintenance_errors",
                    "severity": "warning",
                    "message": f"Muchos errores de mantenimiento: {maintenance_metrics.get('errors_count')}",
                    "recommendation": "Revisar logs de mantenimiento y configuración"
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"[SchemaPerformanceService] ❌ Error obteniendo alertas: {e}")
            return []
    
    async def get_optimization_recommendations(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Obtiene recomendaciones de optimización basadas en métricas existentes"""
        try:
            await self._get_services()
            
            recommendations = []
            
            # Cache optimization
            cache_metrics = await self._get_cache_metrics(user_id)
            if cache_metrics.get("hit_ratio", 1.0) < 0.9:
                recommendations.append({
                    "category": "cache",
                    "priority": "high",
                    "title": "Optimizar Cache Hit Ratio",
                    "description": f"Hit ratio actual: {cache_metrics.get('hit_ratio', 0):.1%}",
                    "action": "Ajustar TTLs y estrategias de cache"
                })
            
            # Redis optimization
            redis_metrics = await self._get_redis_metrics(user_id)
            if redis_metrics.get("memory_usage_mb", 0) > 1000:
                recommendations.append({
                    "category": "redis",
                    "priority": "medium",
                    "title": "Optimizar Uso de Memoria Redis",
                    "description": f"Uso actual: {redis_metrics.get('memory_usage_mb', 0):.1f} MB",
                    "action": "Revisar TTLs y limpiar caches obsoletos"
                })
            
            # Maintenance optimization
            maintenance_metrics = await self._get_maintenance_metrics(user_id)
            if not maintenance_metrics.get("weekly_cleanup_enabled", False):
                recommendations.append({
                    "category": "maintenance",
                    "priority": "medium",
                    "title": "Habilitar Cleanup Semanal",
                    "description": "Cleanup automático está deshabilitado",
                    "action": "Habilitar cleanup semanal para optimizar almacenamiento"
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"[SchemaPerformanceService] ❌ Error obteniendo recomendaciones: {e}")
            return []
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtiene información del servicio integrado"""
        return {
            "service_name": "SchemaPerformanceService",
            "description": "Servicio de integración de métricas existentes para schemas",
            "integrated_services": [
                "PerformanceMonitoringService",
                "DetailedSchemaCacheService", 
                "RedisSchemaCache",
                "SchemaMaintenanceService",
                "SchemaNotificationService"
            ],
            "features": [
                "Dashboard unificado de performance",
                "Métricas integradas de servicios existentes",
                "Alertas de performance",
                "Recomendaciones de optimización",
                "Cálculo de salud del sistema"
            ],
            "status": "active"
        }
