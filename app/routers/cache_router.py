# app/routers/cache_router.py
"""
CacheRouter
───────────
Router para gestionar cache de esquemas de base de datos.
"""

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory

router = APIRouter(
    prefix="/cache",
    tags=["🗄️ Cache"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "No encontrado"},
        500: {"description": "Error interno del servidor"},
    },
)


def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.get(
    "/schemas/{db_id}",
    summary="📊 Obtener esquema cacheado",
    description="Obtiene el esquema cacheado de una base de datos específica.",
)
def get_cached_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener esquema cacheado de una base de datos"""
    try:
        cache_service = factory.get_cache_service()
        schema = cache_service.get_cached_schema(factory.user.id, db_id)
        
        if schema:
            return {
                "success": True,
                "db_id": str(db_id),
                "tables": schema,
                "table_count": len(schema)
            }
        else:
            return {
                "success": False,
                "message": "Esquema no encontrado en cache o expirado",
                "db_id": str(db_id)
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo esquema cacheado: {str(e)}"
        )


@router.post(
    "/schemas/{db_id}/refresh",
    summary="🔄 Refrescar esquema",
    description="Fuerza la exploración y cacheado del esquema de una base de datos.",
)
def refresh_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """Refrescar esquema de una base de datos"""
    try:
        schema_explorer = factory.get_schema_explorer_service()
        success = schema_explorer.refresh_schema_cache(factory.user.id, db_id)
        
        if success:
            return {
                "success": True,
                "message": "Esquema refrescado correctamente",
                "db_id": str(db_id)
            }
        else:
            return {
                "success": False,
                "message": "No se pudo refrescar el esquema",
                "db_id": str(db_id)
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error refrescando esquema: {str(e)}"
        )


@router.delete(
    "/schemas/{db_id}",
    summary="🗑️ Invalidar esquema",
    description="Invalida el cache del esquema de una base de datos específica.",
)
def invalidate_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """Invalidar cache de esquema de una base de datos"""
    try:
        cache_service = factory.get_cache_service()
        cache_service.invalidate_db_cache(factory.user.id, db_id)
        
        return {
            "success": True,
            "message": "Cache de esquema invalidado",
            "db_id": str(db_id)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error invalidando esquema: {str(e)}"
        )


@router.get(
    "/schemas",
    summary="📋 Listar esquemas cacheados",
    description="Obtiene todos los esquemas cacheados del usuario.",
)
def list_cached_schemas(
    factory: ServiceFactory = Depends(get_factory),
):
    """Listar todos los esquemas cacheados del usuario"""
    try:
        cache_service = factory.get_cache_service()
        user_key = str(factory.user.id)
        
        # Obtener cache del usuario
        user_cache = cache_service.cache.get(user_key, {})
        
        schemas = []
        for db_id, cache_entry in user_cache.items():
            if cache_service._is_cache_valid(cache_entry):
                schemas.append({
                    "db_id": db_id,
                    "table_count": cache_entry.get("table_count", 0),
                    "last_updated": cache_entry.get("last_updated"),
                    "schema_hash": cache_entry.get("schema_hash")
                })
        
        return {
            "success": True,
            "schemas": schemas,
            "total_schemas": len(schemas)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error listando esquemas: {str(e)}"
        )


@router.delete(
    "/schemas",
    summary="🧹 Limpiar cache de esquemas",
    description="Invalida todo el cache de esquemas del usuario.",
)
def clear_schema_cache(
    factory: ServiceFactory = Depends(get_factory),
):
    """Limpiar todo el cache de esquemas del usuario"""
    try:
        cache_service = factory.get_cache_service()
        cache_service.invalidate_user_cache(factory.user.id)
        
        return {
            "success": True,
            "message": "Cache de esquemas limpiado"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error limpiando cache: {str(e)}"
        )


@router.get(
    "/stats",
    summary="📊 Estadísticas del cache",
    description="Obtiene estadísticas generales del cache.",
)
def get_cache_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas del cache"""
    try:
        cache_service = factory.get_cache_service()
        stats = cache_service.get_cache_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas: {str(e)}"
        )


@router.post(
    "/schemas/explore",
    summary="🔍 Explorar esquemas",
    description="Explora y cachea esquemas de múltiples bases de datos.",
)
def explore_schemas(
    db_ids: List[UUID],
    factory: ServiceFactory = Depends(get_factory),
):
    """Explorar y cachear esquemas de múltiples bases de datos"""
    try:
        schema_explorer = factory.get_schema_explorer_service()
        schemas = schema_explorer.get_schema_for_user_dbs(factory.user.id, db_ids)
        
        results = []
        for db_id, tables in schemas.items():
            results.append({
                "db_id": str(db_id),
                "table_count": len(tables),
                "tables": [table["name"] for table in tables]
            })
        
        return {
            "success": True,
            "explored_schemas": results,
            "total_explored": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error explorando esquemas: {str(e)}"
        )


@router.get(
    "/detailed/{db_id}",
    summary="🦄 Obtener esquema detallado",
    description="Obtiene el esquema detallado cacheado de una base de datos específica.",
)
def get_detailed_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener esquema detallado de una base de datos"""
    try:
        detailed_cache = factory.get_detailed_schema_cache()
        schema = detailed_cache.get_detailed_schema(db_id)
        
        if schema:
            return {
                "success": True,
                "db_id": str(db_id),
                "tables": len(schema.tables),
                "schema": {
                    "db_id": str(schema.db_id),
                    "tables": {
                        name: {
                            "name": table.name,
                            "columns": len(table.columns),
                            "primary_keys": table.primary_keys,
                            "foreign_keys": len(table.foreign_keys),
                            "indexes": len(table.indexes),
                            "row_count": table.row_count
                        }
                        for name, table in schema.tables.items()
                    },
                    "relationships": schema.relationships,
                    "last_updated": schema.last_updated.isoformat(),
                    "schema_hash": schema.schema_hash,
                    "version": schema.version
                }
            }
        else:
            return {
                "success": False,
                "message": "Esquema detallado no encontrado en cache o expirado",
                "db_id": str(db_id)
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo esquema detallado: {str(e)}"
        )


@router.get(
    "/detailed/{db_id}/optimized",
    summary="🎯 Obtener esquema optimizado",
    description="Obtiene el esquema optimizado para una query específica.",
)
def get_optimized_schema(
    db_id: UUID,
    query: str,
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener esquema optimizado para una query específica"""
    try:
        detailed_cache = factory.get_detailed_schema_cache()
        optimized_schema = detailed_cache.get_schema_for_query(db_id, query)
        
        if optimized_schema:
            return {
                "success": True,
                "db_id": str(db_id),
                "query": query,
                "optimized_schema": optimized_schema
            }
        else:
            return {
                "success": False,
                "message": "No se pudo optimizar esquema para la query",
                "db_id": str(db_id),
                "query": query
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo esquema optimizado: {str(e)}"
        )


@router.get(
    "/detailed/stats",
    summary="📊 Estadísticas del cache detallado",
    description="Obtiene estadísticas del cache detallado.",
)
def get_detailed_cache_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas del cache detallado"""
    try:
        detailed_cache = factory.get_detailed_schema_cache()
        stats = detailed_cache.get_cache_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas detalladas: {str(e)}"
        )


@router.post(
    "/vector-search/{db_id}",
    summary="🔍 Búsqueda vectorial",
    description="Realiza búsqueda vectorial en el esquema de una base de datos.",
)
async def vector_search(
    db_id: UUID,
    query: str,
    top_k: int = 5,
    factory: ServiceFactory = Depends(get_factory),
):
    """Realizar búsqueda vectorial en esquema"""
    try:
        vector_search_service = factory.get_vector_search_service()
        results = await vector_search_service.semantic_search(db_id, query, top_k)
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "element_id": result.element_id,
                "content": result.content,
                "similarity_score": result.similarity_score,
                "metadata": result.metadata,
                "semantic_type": result.semantic_type,
                "relevance_boost": result.relevance_boost,
                "final_score": result.similarity_score * result.relevance_boost
            })
        
        return {
            "success": True,
            "db_id": str(db_id),
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error en búsqueda vectorial: {str(e)}"
        )


@router.post(
    "/prompt-engineering/optimize",
    summary="🎯 Optimizar prompt",
    description="Optimiza un prompt para una query específica usando prompt engineering.",
)
def optimize_prompt(
    query: str,
    schema_context: Dict[str, Any],
    factory: ServiceFactory = Depends(get_factory),
):
    """Optimizar prompt para una query específica"""
    try:
        prompt_engineering_service = factory.get_prompt_engineering_service()
        optimized_prompt = prompt_engineering_service.optimize_prompt_for_query(
            query, schema_context
        )
        
        return {
            "success": True,
            "query": query,
            "optimized_prompt": {
                "system_prompt": optimized_prompt.system_prompt,
                "user_prompt": optimized_prompt.user_prompt,
                "confidence_score": optimized_prompt.confidence_score,
                "semantic_hints": optimized_prompt.semantic_hints,
                "optimization_notes": optimized_prompt.optimization_notes
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error optimizando prompt: {str(e)}"
        )


@router.get(
    "/vector-search/stats",
    summary="📊 Estadísticas de búsqueda vectorial",
    description="Obtiene estadísticas del servicio de búsqueda vectorial.",
)
def get_vector_search_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas de búsqueda vectorial"""
    try:
        vector_search_service = factory.get_vector_search_service()
        stats = vector_search_service.get_search_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas de búsqueda: {str(e)}"
        )


@router.get(
    "/prompt-engineering/stats",
    summary="📊 Estadísticas de prompt engineering",
    description="Obtiene estadísticas del servicio de prompt engineering.",
)
def get_prompt_engineering_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas de prompt engineering"""
    try:
        prompt_engineering_service = factory.get_prompt_engineering_service()
        stats = prompt_engineering_service.get_prompt_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas de prompt engineering: {str(e)}"
        )


@router.post(
    "/query-validation/validate",
    summary="🔍 Validar query",
    description="Valida una query SQL usando el servicio de validación inteligente.",
)
def validate_query(
    query: str,
    schema_context: Dict[str, Any],
    user_permissions: List[str] = None,
    factory: ServiceFactory = Depends(get_factory),
):
    """Validar una query SQL"""
    try:
        query_validation_service = factory.get_query_validation_service()
        validation_result = query_validation_service.validate_query(
            query, schema_context, user_permissions
        )
        
        return {
            "success": True,
            "query": query,
            "validation_result": {
                "is_valid": validation_result.is_valid,
                "confidence_score": validation_result.confidence_score,
                "errors": validation_result.errors,
                "warnings": validation_result.warnings,
                "suggestions": validation_result.suggestions,
                "performance_score": validation_result.performance_score,
                "security_score": validation_result.security_score,
                "complexity_level": validation_result.complexity_level
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error validando query: {str(e)}"
        )


@router.get(
    "/query-validation/stats",
    summary="📊 Estadísticas de validación",
    description="Obtiene estadísticas del servicio de validación de queries.",
)
def get_query_validation_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas de validación de queries"""
    try:
        query_validation_service = factory.get_query_validation_service()
        stats = query_validation_service.get_validation_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas de validación: {str(e)}"
        )


@router.get(
    "/performance-monitoring/current",
    summary="📊 Métricas actuales",
    description="Obtiene las métricas de performance actuales.",
)
def get_current_performance_metrics(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener métricas de performance actuales"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        metrics = performance_monitoring_service.get_current_metrics()
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo métricas actuales: {str(e)}"
        )


@router.get(
    "/performance-monitoring/summary",
    summary="📈 Resumen de performance",
    description="Obtiene un resumen completo de la performance del sistema.",
)
def get_performance_summary(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener resumen de performance"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        summary = performance_monitoring_service.get_performance_summary()
        
        return {
            "success": True,
            "summary": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo resumen de performance: {str(e)}"
        )


@router.get(
    "/performance-monitoring/alerts",
    summary="🚨 Alertas de performance",
    description="Obtiene las alertas de performance recientes.",
)
def get_performance_alerts(
    hours: int = 24,
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener alertas de performance"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        alerts = performance_monitoring_service.get_alerts(hours)
        
        return {
            "success": True,
            "alerts": alerts,
            "hours": hours
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo alertas: {str(e)}"
        )


@router.post(
    "/performance-monitoring/start",
    summary="🚀 Iniciar monitoreo",
    description="Inicia el monitoreo continuo de performance.",
)
def start_performance_monitoring(
    factory: ServiceFactory = Depends(get_factory),
):
    """Iniciar monitoreo de performance"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        performance_monitoring_service.start_monitoring()
        
        return {
            "success": True,
            "message": "Monitoreo de performance iniciado"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error iniciando monitoreo: {str(e)}"
        )


@router.post(
    "/performance-monitoring/stop",
    summary="🛑 Detener monitoreo",
    description="Detiene el monitoreo continuo de performance.",
)
def stop_performance_monitoring(
    factory: ServiceFactory = Depends(get_factory),
):
    """Detener monitoreo de performance"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        performance_monitoring_service.stop_monitoring()
        
        return {
            "success": True,
            "message": "Monitoreo de performance detenido"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error deteniendo monitoreo: {str(e)}"
        )


@router.get(
    "/performance-monitoring/stats",
    summary="📊 Estadísticas de monitoreo",
    description="Obtiene estadísticas del servicio de monitoreo de performance.",
)
def get_performance_monitoring_stats(
    factory: ServiceFactory = Depends(get_factory),
):
    """Obtener estadísticas de monitoreo de performance"""
    try:
        performance_monitoring_service = factory.get_performance_monitoring_service()
        stats = performance_monitoring_service.get_monitoring_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error obteniendo estadísticas de monitoreo: {str(e)}"
        )
