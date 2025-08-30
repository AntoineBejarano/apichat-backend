from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any
from uuid import UUID

from app.dependencies import get_service_factory
from app.core.service_factory import ServiceFactory

router = APIRouter(
    prefix="/api-triggering",
    tags=["🚀 API Triggering"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Función no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)


@router.post(
    "/trigger",
    summary="Triggerear función automáticamente",
    description="Ejecutar función de API automáticamente basado en query en lenguaje natural"
)
async def trigger_function_by_query(
    query: str,
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    auto_execute: bool = Query(default=False, description="Ejecutar automáticamente sin confirmación"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Triggerear función automáticamente basado en query natural"""
    try:
        triggering_service = factory.get_api_triggering_service()
        
        result = await triggering_service.process_triggering_request(
            query=query,
            user_id=factory.user.id,
            app_id=app_id,
            db_id=db_id,
            auto_execute=auto_execute
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando triggering: {str(e)}"
        )


@router.post(
    "/execute-plan",
    summary="Ejecutar plan confirmado",
    description="Ejecutar un plan de triggering confirmado por el usuario"
)
async def execute_confirmed_plan(
    plan_data: Dict[str, Any],
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Ejecutar un plan de triggering confirmado"""
    try:
        triggering_service = factory.get_api_triggering_service()
        
        # Crear objeto TriggeringPlan desde los datos
        from app.services.ai.api_triggering_service import TriggeringPlan
        
        plan = TriggeringPlan(
            function_id=UUID(plan_data["function_id"]),
            function_name=plan_data["function_name"],
            endpoint=plan_data["endpoint"],
            method=plan_data["method"],
            parameters=plan_data["parameters"],
            confidence=plan_data["confidence"],
            requires_confirmation=plan_data["requires_confirmation"],
            estimated_execution_time=plan_data["estimated_execution_time"]
        )
        
        result = await triggering_service.execute_confirmed_plan(
            plan=plan,
            user_id=factory.user.id
        )
        
        return {
            "success": result.success,
            "function_name": result.function_name,
            "endpoint": result.endpoint,
            "result": result.result,
            "execution_time": result.execution_time,
            "error": result.error
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error ejecutando plan: {str(e)}"
        )


@router.get(
    "/suggestions",
    summary="Obtener sugerencias de triggering",
    description="Obtener sugerencias de funciones disponibles para triggering"
)
async def get_triggering_suggestions(
    query: str = Query(description="Query parcial para sugerencias"),
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtener sugerencias de triggering basadas en query parcial"""
    try:
        from app.services.context.unified_vector_search_service import SearchContext
        
        unified_search_service = factory.get_unified_vector_search_service()
        
        search_context = SearchContext(
            user_id=factory.user.id,
            app_id=app_id,
            db_id=db_id,
            search_types=["api"],
            confidence_threshold=0.5,
            max_results_per_type=5
        )
        
        suggestions = await unified_search_service.get_search_suggestions(
            partial_query=query,
            context=search_context,
            max_suggestions=5
        )
        
        return {
            "suggestions": suggestions,
            "query": query
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo sugerencias: {str(e)}"
        )


@router.get(
    "/analytics",
    summary="Obtener analytics de triggering",
    description="Obtener estadísticas de uso del sistema de triggering"
)
async def get_triggering_analytics(
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtener analytics de triggering para el usuario"""
    try:
        triggering_service = factory.get_api_triggering_service()
        
        analytics = await triggering_service.get_triggering_analytics(
            user_id=factory.user.id
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo analytics: {str(e)}"
        )


@router.post(
    "/test-query",
    summary="Probar query de triggering",
    description="Probar una query sin ejecutar funciones (solo búsqueda y planificación)"
)
async def test_triggering_query(
    query: str,
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Probar query de triggering sin ejecutar funciones"""
    try:
        triggering_service = factory.get_api_triggering_service()
        
        result = await triggering_service.process_triggering_request(
            query=query,
            user_id=factory.user.id,
            app_id=app_id,
            db_id=db_id,
            auto_execute=False  # Solo planificar, no ejecutar
        )
        
        return {
            "query": query,
            "test_result": result,
            "message": "Query probada exitosamente (sin ejecución)"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error probando query: {str(e)}"
        )
