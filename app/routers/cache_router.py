#!/usr/bin/env python3
"""
CacheRouter - Endpoints para monitorear y gestionar cache
─────────────────────────────────────────────────────────
Proporciona endpoints para:
- Estadísticas del cache Redis
- Health check del cache
- Limpieza manual del cache
- Métricas de performance
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.services.cache.redis_schema_cache import redis_schema_cache

router = APIRouter(
    prefix="/cache",
    tags=["🗄️ Cache Management"],
    responses={
        401: {"description": "No autorizado"},
        500: {"description": "Error interno del servidor"},
    },
)


@router.get(
    "/stats",
    summary="Estadísticas del cache Redis",
    response_description="Estadísticas detalladas del cache"
)
def get_cache_stats() -> Dict[str, Any]:
    """
    🔍 Obtiene estadísticas del cache Redis.
    
    Returns:
        Estadísticas del cache incluyendo memoria, clientes, hits/misses
    """
    try:
        stats = redis_schema_cache.get_cache_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": "2025-08-24T12:00:00Z"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas del cache: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health check del cache Redis",
    response_description="Estado de salud del cache"
)
def get_cache_health() -> Dict[str, Any]:
    """
    🏥 Realiza health check del cache Redis.
    
    Returns:
        Estado de salud del cache
    """
    try:
        health = redis_schema_cache.health_check()
        return {
            "status": "success",
            "health": health,
            "timestamp": "2025-08-24T12:00:00Z"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en health check del cache: {str(e)}"
        )


@router.delete(
    "/clear",
    summary="Limpiar todo el cache Redis",
    response_description="Cache limpiado correctamente"
)
def clear_cache() -> Dict[str, Any]:
    """
    🧹 Limpia todo el cache Redis.
    
    ⚠️ **ADVERTENCIA**: Esta operación elimina todos los schemas cacheados.
    
    Returns:
        Confirmación de limpieza del cache
    """
    try:
        success = redis_schema_cache.clear_all_schemas()
        if success:
            return {
                "status": "success",
                "message": "Cache limpiado correctamente",
                "timestamp": "2025-08-24T12:00:00Z"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error limpiando el cache"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error limpiando el cache: {str(e)}"
        )


@router.get(
    "/performance",
    summary="Métricas de performance del cache",
    response_description="Métricas de performance del cache"
)
def get_cache_performance() -> Dict[str, Any]:
    """
    📊 Obtiene métricas de performance del cache Redis.
    
    Returns:
        Métricas de performance incluyendo hit ratio, latencia, etc.
    """
    try:
        stats = redis_schema_cache.get_cache_stats()
        
        # Calcular métricas de performance
        if stats.get('status') == 'available':
            keyspace_hits = stats.get('keyspace_hits', 0)
            keyspace_misses = stats.get('keyspace_misses', 0)
            total_requests = keyspace_hits + keyspace_misses
            
            if total_requests > 0:
                hit_ratio = (keyspace_hits / total_requests) * 100
            else:
                hit_ratio = 0
            
            performance_metrics = {
                "hit_ratio_percent": round(hit_ratio, 2),
                "total_requests": total_requests,
                "cache_hits": keyspace_hits,
                "cache_misses": keyspace_misses,
                "schema_ttl_seconds": stats.get('schema_ttl', 3600),
                "memory_usage": stats.get('used_memory', 'N/A'),
                "connected_clients": stats.get('connected_clients', 0)
            }
        else:
            performance_metrics = {
                "status": "unavailable",
                "message": "Cache no disponible para métricas"
            }
        
        return {
            "status": "success",
            "performance": performance_metrics,
            "timestamp": "2025-08-24T12:00:00Z"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo métricas de performance: {str(e)}"
        )
