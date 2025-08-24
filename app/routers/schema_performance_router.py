"""
📊 Schema Performance Router: Dashboard unificado de performance

Este router expone endpoints para acceder al dashboard unificado
de performance de schemas, integrando todas las métricas existentes.
"""

import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID

from app.core.service_factory import ServiceFactory
from app.services.monitoring.schema_performance_service import SchemaPerformanceService
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/schema-performance",
    tags=["Schema Performance"],
    responses={404: {"description": "Not found"}}
)


def get_schema_performance_service() -> SchemaPerformanceService:
    """Dependency para obtener el servicio de performance de schemas"""
    try:
        # Crear servicio usando un factory mock para testing
        # En producción, esto se inyectará desde el router principal
        class MockFactory:
            def get_performance_monitoring_service(self):
                return None
            def get_detailed_schema_cache_service(self):
                return None
            def get_redis_schema_cache(self):
                return None
            def get_schema_maintenance_service(self):
                return None
            def get_schema_notification_service(self):
                return None
        
        factory = MockFactory()
        service = SchemaPerformanceService(factory)
        return service
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error creando servicio: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/dashboard/{user_id}")
async def get_schema_performance_dashboard(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene dashboard unificado de performance de schemas
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Dashboard con todas las métricas integradas
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 📊 Obteniendo dashboard para usuario {user_id}")
        
        dashboard = await service.get_schema_performance_dashboard(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=500, detail=dashboard["error"])
        
        return {
            "success": True,
            "data": dashboard,
            "message": "Dashboard generado exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/alerts/{user_id}")
async def get_performance_alerts(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene alertas de performance para un usuario
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Lista de alertas de performance
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 🚨 Obteniendo alertas para usuario {user_id}")
        
        alerts = await service.get_performance_alerts(user_id)
        
        return {
            "success": True,
            "data": {
                "user_id": str(user_id),
                "alerts": alerts,
                "total_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"]),
                "warning_alerts": len([a for a in alerts if a.get("severity") == "warning"])
            },
            "message": f"Alertas obtenidas: {len(alerts)} encontradas"
        }
        
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo alertas: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/recommendations/{user_id}")
async def get_optimization_recommendations(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene recomendaciones de optimización para un usuario
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Lista de recomendaciones de optimización
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 💡 Obteniendo recomendaciones para usuario {user_id}")
        
        recommendations = await service.get_optimization_recommendations(user_id)
        
        return {
            "success": True,
            "data": {
                "user_id": str(user_id),
                "recommendations": recommendations,
                "total_recommendations": len(recommendations),
                "high_priority": len([r for r in recommendations if r.get("priority") == "high"]),
                "medium_priority": len([r for r in recommendations if r.get("priority") == "medium"]),
                "low_priority": len([r for r in recommendations if r.get("priority") == "low"])
            },
            "message": f"Recomendaciones obtenidas: {len(recommendations)} encontradas"
        }
        
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo recomendaciones: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/health/{user_id}")
async def get_schema_health_status(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene estado de salud de schemas para un usuario
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Estado de salud del sistema de schemas
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 🏥 Obteniendo estado de salud para usuario {user_id}")
        
        dashboard = await service.get_schema_performance_dashboard(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=500, detail=dashboard["error"])
        
        health_data = dashboard.get("overall_health", {})
        
        return {
            "success": True,
            "data": {
                "user_id": str(user_id),
                "health_score": health_data.get("score", 0),
                "status": health_data.get("status", "unknown"),
                "color": health_data.get("color", "⚪"),
                "last_calculated": health_data.get("last_calculated"),
                "timestamp": dashboard.get("timestamp")
            },
            "message": f"Estado de salud: {health_data.get('status', 'unknown')}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo estado de salud: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/metrics/{user_id}")
async def get_detailed_metrics(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene métricas detalladas para un usuario
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Métricas detalladas de todos los componentes
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 📈 Obteniendo métricas detalladas para usuario {user_id}")
        
        dashboard = await service.get_schema_performance_dashboard(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=500, detail=dashboard["error"])
        
        return {
            "success": True,
            "data": {
                "user_id": str(user_id),
                "timestamp": dashboard.get("timestamp"),
                "cache_performance": dashboard.get("cache_performance", {}),
                "redis_performance": dashboard.get("redis_performance", {}),
                "maintenance_status": dashboard.get("maintenance_status", {}),
                "notification_stats": dashboard.get("notification_stats", {}),
                "overall_health": dashboard.get("overall_health", {})
            },
            "message": "Métricas detalladas obtenidas exitosamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo métricas detalladas: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/summary/{user_id}")
async def get_performance_summary(
    user_id: UUID,
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene resumen ejecutivo de performance para un usuario
    
    Args:
        user_id: ID del usuario
        service: Servicio de performance de schemas
        
    Returns:
        Resumen ejecutivo de performance
    """
    try:
        logger.info(f"[SchemaPerformanceRouter] 📋 Obteniendo resumen ejecutivo para usuario {user_id}")
        
        dashboard = await service.get_schema_performance_dashboard(user_id)
        alerts = await service.get_performance_alerts(user_id)
        recommendations = await service.get_optimization_recommendations(user_id)
        
        if "error" in dashboard:
            raise HTTPException(status_code=500, detail=dashboard["error"])
        
        # Crear resumen ejecutivo
        health = dashboard.get("overall_health", {})
        cache = dashboard.get("cache_performance", {})
        redis = dashboard.get("redis_performance", {})
        
        summary = {
            "user_id": str(user_id),
            "timestamp": dashboard.get("timestamp"),
            "overall_score": health.get("score", 0),
            "overall_status": health.get("status", "unknown"),
            "overall_color": health.get("color", "⚪"),
            "key_metrics": {
                "cache_hit_ratio": cache.get("hit_ratio", 0.0),
                "redis_connected": redis.get("redis_connected", False),
                "total_schemas": cache.get("total_schemas", 0),
                "cached_schemas": cache.get("cached_schemas", 0)
            },
            "alerts_summary": {
                "total_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a.get("severity") == "critical"]),
                "warning_alerts": len([a for a in alerts if a.get("severity") == "warning"])
            },
            "recommendations_summary": {
                "total_recommendations": len(recommendations),
                "high_priority": len([r for r in recommendations if r.get("priority") == "high"]),
                "medium_priority": len([r for r in recommendations if r.get("priority") == "medium"])
            }
        }
        
        return {
            "success": True,
            "data": summary,
            "message": f"Resumen ejecutivo: {health.get('status', 'unknown')} ({health.get('score', 0)}/100)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo resumen ejecutivo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/service-info")
async def get_service_information(
    service: SchemaPerformanceService = Depends(get_schema_performance_service)
) -> Dict[str, Any]:
    """
    Obtiene información del servicio de performance de schemas
    
    Args:
        service: Servicio de performance de schemas
        
    Returns:
        Información del servicio
    """
    try:
        logger.info("[SchemaPerformanceRouter] ℹ️ Obteniendo información del servicio")
        
        service_info = service.get_service_info()
        
        return {
            "success": True,
            "data": service_info,
            "message": "Información del servicio obtenida exitosamente"
        }
        
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error obteniendo información del servicio: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@router.get("/health-check")
async def health_check() -> Dict[str, Any]:
    """
    Health check del router de performance de schemas
    
    Returns:
        Estado de salud del router
    """
    try:
        logger.info("[SchemaPerformanceRouter] 🏥 Health check del router")
        
        return {
            "success": True,
            "data": {
                "service": "Schema Performance Router",
                "status": "healthy",
                "timestamp": "2025-08-24T14:30:00Z",
                "version": "1.0.0",
                "endpoints": [
                    "/dashboard/{user_id}",
                    "/alerts/{user_id}",
                    "/recommendations/{user_id}",
                    "/health/{user_id}",
                    "/metrics/{user_id}",
                    "/summary/{user_id}",
                    "/service-info",
                    "/health-check"
                ]
            },
            "message": "Router funcionando correctamente"
        }
        
    except Exception as e:
        logger.error(f"[SchemaPerformanceRouter] ❌ Error en health check: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
