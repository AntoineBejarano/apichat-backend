#!/usr/bin/env python3
"""
APICacheRouter - Router para gestión del cache de definiciones OpenAPI
──────────────────────────────────────────────────────────────────────
Endpoints para:
- Obtener cache de APIs
- Generar cache en background
- Refrescar cache
- Eliminar cache
- Estadísticas y monitoreo
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from typing import List, Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel

from app.core.service_factory import ServiceFactory
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.services.cache.api_cache_service import get_api_cache_service
from app.services.background.api_generation_service import get_api_generation_service
from app.utils.logger import logger

router = APIRouter(
    prefix="/api-cache",
    tags=["🔧 Cache de APIs"],
    responses={
        400: {"description": "❌ Invalid request"},
        401: {"description": "❌ Unauthorized"},
        404: {"description": "❌ API cache not found"},
        500: {"description": "❌ Internal server error"},
    },
)

# 🧩 Inyección del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# Schemas Pydantic

class APICacheRequest(BaseModel):
    """Request para generar cache de API"""
    openapi_data: Dict[str, Any]
    enrichment_level: int = 1
    ttl_hours: int = 24


class APICacheResponse(BaseModel):
    """Response del cache de API"""
    app_id: str
    user_id: str
    status: str
    compression_ratio: Optional[float]
    original_size_mb: Optional[float]
    compressed_size_mb: Optional[float]
    last_accessed: Optional[str]
    access_count: int


class APICacheStats(BaseModel):
    """Estadísticas del cache de API"""
    total_entries: int
    ready_entries: int
    error_entries: int
    obsolete_entries: int
    average_compression_ratio: float
    space_saved_mb: float


# Endpoints principales

@router.get("/{app_id}")
async def get_api_cache(
    app_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el cache de una definición OpenAPI.
    
    Args:
        app_id: ID de la app
    
    Returns:
        Definición OpenAPI cacheada
    """
    try:
        user_id = factory.user.id
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Obtener cache
        cached_data = await api_cache_service.get_api_cache(user_id, app_id)
        
        if not cached_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache no encontrado para la app {app_id}"
            )
        
        # Obtener metadatos del cache
        metadata = await api_cache_service.redis_cache.get_api_cache_metadata(user_id, app_id)
        
        response = {
            "app_id": str(app_id),
            "user_id": str(user_id),
            "openapi_data": cached_data,
            "cache_metadata": metadata,
            "retrieved_from": "cache"
        }
        
        logger.info(f"[APICacheRouter] ✅ Cache obtenido para app {app_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error obteniendo cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting API cache"
        )


@router.post("/{app_id}/generate")
async def generate_api_cache(
    app_id: UUID,
    request: APICacheRequest,
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Genera cache para una definición OpenAPI en background.
    
    Args:
        app_id: ID de la app
        request: Datos OpenAPI y configuración
    
    Returns:
        Confirmación de generación iniciada
    """
    try:
        user_id = factory.user.id
        
        # Añadir tarea en background
        background_tasks.add_task(
            generate_api_cache_background,
            app_id=app_id,
            user_id=user_id,
            openapi_data=request.openapi_data,
            factory=factory
        )
        
        logger.info(f"[APICacheRouter] 🚀 Generación de cache iniciada para app {app_id}")
        
        return {
            "success": True,
            "message": f"We are working on preparing your API '{app_id}'. This may take a few minutes.",
            "app_id": str(app_id),
            "user_id": str(user_id),
            "status": "generating",
            "background_task": "started"
        }
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error iniciando generación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error starting cache generation"
        )


@router.put("/{app_id}/refresh")
async def refresh_api_cache(
    app_id: UUID,
    request: APICacheRequest,
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Refresca el cache de una definición OpenAPI en background.
    
    Args:
        app_id: ID de la app
        request: Nuevos datos OpenAPI
    
    Returns:
        Confirmación de refresh iniciado
    """
    try:
        user_id = factory.user.id
        
        # Añadir tarea en background
        background_tasks.add_task(
            refresh_api_cache_background,
            app_id=app_id,
            user_id=user_id,
            new_openapi_data=request.openapi_data,
            factory=factory
        )
        
        logger.info(f"[APICacheRouter] 🔄 Refresh de cache iniciado para app {app_id}")
        
        return {
            "success": True,
            "message": f"We are refreshing your API '{app_id}' cache. This may take a few minutes.",
            "app_id": str(app_id),
            "user_id": str(user_id),
            "status": "updating",
            "background_task": "started"
        }
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error iniciando refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error starting cache refresh"
        )


@router.delete("/{app_id}")
async def delete_api_cache(
    app_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Elimina el cache de una definición OpenAPI.
    
    Args:
        app_id: ID de la app
    
    Returns:
        Confirmación de eliminación
    """
    try:
        user_id = factory.user.id
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Invalidar cache
        success = await api_cache_service.invalidate_api_cache(user_id, app_id)
        
        if success:
            logger.info(f"[APICacheRouter] 🗑️ Cache eliminado para app {app_id}")
            return {
                "success": True,
                "message": f"Cache eliminado para la app {app_id}",
                "app_id": str(app_id),
                "user_id": str(user_id)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error eliminando cache"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error eliminando cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error deleting API cache"
        )


@router.get("/{app_id}/stats")
async def get_api_cache_stats(
    app_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene estadísticas del cache de una API específica.
    
    Args:
        app_id: ID de la app
    
    Returns:
        Estadísticas del cache
    """
    try:
        user_id = factory.user.id
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Obtener estadísticas
        stats = await api_cache_service.get_cache_statistics(user_id)
        
        # Filtrar por app específica
        app_stats = {
            "app_id": str(app_id),
            "user_id": str(user_id),
            "cache_stats": stats,
            "timestamp": stats.get('timestamp')
        }
        
        logger.info(f"[APICacheRouter] 📊 Estadísticas obtenidas para app {app_id}")
        return app_stats
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting API cache stats"
        )


@router.get("/stats/global")
async def get_global_api_cache_stats(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene estadísticas globales del cache de APIs.
    
    Returns:
        Estadísticas globales del cache
    """
    try:
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Obtener estadísticas globales
        stats = await api_cache_service.get_cache_statistics()
        
        logger.info("[APICacheRouter] 📊 Estadísticas globales obtenidas")
        return stats
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error obteniendo estadísticas globales: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting global API cache stats"
        )


@router.post("/batch/generate")
async def generate_api_cache_batch(
    app_ids: List[UUID],
    openapi_data_map: Dict[str, Dict[str, Any]],
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Genera cache para múltiples APIs en lote.
    
    Args:
        app_ids: Lista de IDs de apps
        openapi_data_map: Mapa de datos OpenAPI por app
    
    Returns:
        Confirmación de generación en lote iniciada
    """
    try:
        user_id = factory.user.id
        
        # Convertir string keys a UUID
        openapi_data_uuid_map = {
            UUID(app_id_str): data 
            for app_id_str, data in openapi_data_map.items()
        }
        
        # Añadir tarea en background
        background_tasks.add_task(
            generate_api_cache_batch_background,
            app_ids=app_ids,
            user_id=user_id,
            openapi_data_map=openapi_data_uuid_map,
            factory=factory
        )
        
        logger.info(f"[APICacheRouter] 📦 Generación en lote iniciada para {len(app_ids)} apps")
        
        return {
            "success": True,
            "message": f"We are working on preparing {len(app_ids)} APIs. This may take several minutes.",
            "total_apps": len(app_ids),
            "user_id": str(user_id),
            "status": "batch_generating",
            "background_task": "started"
        }
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error iniciando generación en lote: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error starting batch cache generation"
        )


@router.post("/retry/failed")
async def retry_failed_api_generations(
    max_retries: int = 10,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Reintenta generaciones de cache fallidas.
    
    Args:
        max_retries: Máximo número de reintentos
    
    Returns:
        Resumen de reintentos
    """
    try:
        api_generation_service = get_api_generation_service(factory)
        
        # Ejecutar reintentos
        results = await api_generation_service.retry_failed_generations(max_retries)
        
        logger.info(f"[APICacheRouter] 🔄 Reintentos completados: {results['successful']}/{results['total_retries']} exitosos")
        return results
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error en reintentos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during retry process"
        )


@router.post("/cleanup/expired")
async def cleanup_expired_api_caches(
    max_cleanup: int = 100,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Limpia caches de APIs expirados.
    
    Args:
        max_cleanup: Máximo número de caches a limpiar
    
    Returns:
        Resumen de limpieza
    """
    try:
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Ejecutar limpieza
        cleaned_count = await api_cache_service.cleanup_expired_caches(max_cleanup)
        
        logger.info(f"[APICacheRouter] 🧹 Limpieza completada: {cleaned_count} entradas")
        
        return {
            "success": True,
            "message": f"Cleanup completed successfully",
            "cleaned_entries": cleaned_count,
            "max_cleanup": max_cleanup
        }
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error en limpieza: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during cleanup process"
        )


@router.get("/health")
async def get_api_cache_health(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Verifica la salud del sistema de cache de APIs.
    
    Returns:
        Estado de salud del sistema
    """
    try:
        api_cache_service = get_api_cache_service(factory.get_db())
        
        # Verificar salud de Redis
        redis_health = await api_cache_service.redis_cache.health_check()
        
        # Verificar salud de base de datos
        db_stats = await api_cache_service.get_cache_statistics()
        
        health_status = {
            "status": "healthy" if redis_health.get("status") == "healthy" else "degraded",
            "redis": redis_health,
            "database": db_stats,
            "timestamp": redis_health.get("timestamp")
        }
        
        logger.info("[APICacheRouter] 🏥 Health check completado")
        return health_status
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error en health check: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": None
        }


@router.get("/performance/metrics")
async def get_api_cache_performance_metrics(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene métricas de performance del cache de APIs.
    
    Returns:
        Métricas de performance
    """
    try:
        api_cache_service = get_api_cache_service(factory.get_db())
        api_generation_service = get_api_generation_service(factory)
        
        # Obtener estadísticas del cache
        cache_stats = await api_cache_service.get_cache_statistics()
        
        # Obtener estadísticas de generación
        generation_stats = api_generation_service.get_generation_stats()
        
        # Calcular métricas de performance
        performance_metrics = {
            "cache_performance": {
                "hit_ratio": cache_stats.get("cache_hit_ratio", 0),
                "total_entries": cache_stats.get("total_entries", 0),
                "compression_efficiency": cache_stats.get("database", {}).get("average_compression_ratio", 0),
                "space_saved_mb": cache_stats.get("database", {}).get("space_saved_mb", 0)
            },
            "generation_performance": {
                "total_generated": generation_stats.get("generation_stats", {}).get("total_generated", 0),
                "total_failed": generation_stats.get("generation_stats", {}).get("total_failed", 0),
                "success_rate": _calculate_success_rate(generation_stats),
                "average_generation_time": generation_stats.get("generation_stats", {}).get("average_generation_time", 0)
            },
            "system_health": {
                "redis_status": cache_stats.get("redis", {}).get("status", "unknown"),
                "memory_usage": cache_stats.get("memory", {}).get("memory_usage_percent", 0),
                "database_entries": cache_stats.get("database", {}).get("total_entries", 0)
            }
        }
        
        logger.info("[APICacheRouter] 📈 Métricas de performance obtenidas")
        return performance_metrics
        
    except Exception as e:
        logger.error(f"[APICacheRouter] ❌ Error obteniendo métricas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting performance metrics"
        )


# Funciones helper

def _calculate_success_rate(generation_stats: Dict[str, Any]) -> float:
    """Calcula la tasa de éxito de generación"""
    try:
        stats = generation_stats.get("generation_stats", {})
        total = stats.get("total_generated", 0) + stats.get("total_failed", 0)
        
        if total == 0:
            return 0.0
        
        success_rate = (stats.get("total_generated", 0) / total) * 100
        return round(success_rate, 2)
        
    except Exception:
        return 0.0


# Funciones helper para background tasks

async def generate_api_cache_background(app_id: UUID, user_id: UUID, 
                                     openapi_data: Dict[str, Any], factory) -> None:
    """Función helper para background task de generación"""
    try:
        service = get_api_generation_service(factory)
        await service.generate_cache_for_app(app_id, user_id, openapi_data)
    except Exception as e:
        logger.error(f"[generate_api_cache_background] ❌ Error: {e}")


async def refresh_api_cache_background(app_id: UUID, user_id: UUID, 
                                    new_openapi_data: Dict[str, Any], factory) -> None:
    """Función helper para background task de refresh"""
    try:
        service = get_api_generation_service(factory)
        await service.refresh_cache_for_app(app_id, user_id, new_openapi_data)
    except Exception as e:
        logger.error(f"[refresh_api_cache_background] ❌ Error: {e}")


async def generate_api_cache_batch_background(app_ids: List[UUID], user_id: UUID, 
                                           openapi_data_map: Dict[UUID, Dict[str, Any]], 
                                           factory) -> None:
    """Función helper para background task de generación en lote"""
    try:
        service = get_api_generation_service(factory)
        await service.generate_cache_batch(app_ids, user_id, openapi_data_map)
    except Exception as e:
        logger.error(f"[generate_api_cache_batch_background] ❌ Error: {e}")
