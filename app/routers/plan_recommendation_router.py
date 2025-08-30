"""
Router para recomendaciones de planes.
"""

import logging
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.service_factory import ServiceFactory, get_factory
from app.services.ai.plan_recommendation_service import PlanRecommendation, RecommendationType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans/recommendations", tags=["Plan Recommendations"])


# ===== SCHEMAS =====

class RecommendationResponse(BaseModel):
    """Response para recomendación."""
    id: str
    type: str
    title: str
    description: str
    confidence: float
    priority: str
    action_required: bool
    metadata: dict
    created_at: str


class RecommendationListResponse(BaseModel):
    """Response para lista de recomendaciones."""
    recommendations: List[RecommendationResponse]
    total: int
    user_id: str


class ApplyRecommendationRequest(BaseModel):
    """Request para aplicar recomendación."""
    application_notes: Optional[str] = None


# ===== ENDPOINTS =====

@router.get("/", response_model=RecommendationListResponse)
async def get_recommendations(
    limit: int = 10,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene recomendaciones para el usuario.
    
    Args:
        limit: Límite de recomendaciones a devolver
        factory: ServiceFactory
        
    Returns:
        Lista de recomendaciones
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Obtener recomendaciones
        recommendation_service = factory.get_plan_recommendation_service()
        recommendations = await recommendation_service.generate_recommendations(
            user_id=factory.user.id,
            current_plan_context=None
        )
        
        # Convertir a response
        recommendation_responses = [
            RecommendationResponse(
                id=rec.id,
                type=rec.type.value,
                title=rec.title,
                description=rec.description,
                confidence=rec.confidence,
                priority=rec.priority,
                action_required=rec.action_required,
                metadata=rec.metadata,
                created_at=rec.created_at.isoformat()
            )
            for rec in recommendations[:limit]
        ]
        
        logger.info(f"[PlanRecommendationRouter] 💡 {len(recommendation_responses)} recomendaciones obtenidas")
        
        return RecommendationListResponse(
            recommendations=recommendation_responses,
            total=len(recommendation_responses),
            user_id=str(factory.user.id)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRecommendationRouter] ❌ Error obteniendo recomendaciones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo recomendaciones: {str(e)}"
        )


@router.get("/{recommendation_id}", response_model=RecommendationResponse)
async def get_recommendation(
    recommendation_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene una recomendación específica.
    
    Args:
        recommendation_id: ID de la recomendación
        factory: ServiceFactory
        
    Returns:
        Recomendación específica
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Obtener recomendación
        recommendation_service = factory.get_plan_recommendation_service()
        recommendation = await recommendation_service.get_recommendation_by_id(
            recommendation_id=recommendation_id,
            user_id=factory.user.id
        )
        
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recomendación no encontrada"
            )
        
        return RecommendationResponse(
            id=recommendation.id,
            type=recommendation.type.value,
            title=recommendation.title,
            description=recommendation.description,
            confidence=recommendation.confidence,
            priority=recommendation.priority,
            action_required=recommendation.action_required,
            metadata=recommendation.metadata,
            created_at=recommendation.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRecommendationRouter] ❌ Error obteniendo recomendación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo recomendación: {str(e)}"
        )


@router.post("/{recommendation_id}/apply")
async def apply_recommendation(
    recommendation_id: str,
    request: ApplyRecommendationRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Marca una recomendación como aplicada.
    
    Args:
        recommendation_id: ID de la recomendación
        request: Datos de aplicación
        factory: ServiceFactory
        
    Returns:
        Resultado de la aplicación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Aplicar recomendación
        recommendation_service = factory.get_plan_recommendation_service()
        success = await recommendation_service.mark_recommendation_as_applied(
            recommendation_id=recommendation_id,
            user_id=factory.user.id,
            application_notes=request.application_notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error aplicando recomendación"
            )
        
        logger.info(f"[PlanRecommendationRouter] ✅ Recomendación {recommendation_id} aplicada")
        
        return {
            "success": True,
            "message": "Recomendación aplicada exitosamente",
            "recommendation_id": recommendation_id,
            "applied_at": "2024-01-01T00:00:00Z"  # TODO: Usar datetime real
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRecommendationRouter] ❌ Error aplicando recomendación: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error aplicando recomendación: {str(e)}"
        )


@router.get("/statistics/execution")
async def get_execution_statistics(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene estadísticas de ejecución del usuario.
    
    Args:
        factory: ServiceFactory
        
    Returns:
        Estadísticas de ejecución
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Obtener estadísticas
        outcome_service = factory.get_plan_outcome_service()
        stats = await outcome_service.get_execution_statistics(factory.user.id)
        
        return {
            "user_id": str(factory.user.id),
            "statistics": stats,
            "generated_at": "2024-01-01T00:00:00Z"  # TODO: Usar datetime real
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRecommendationRouter] ❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.get("/history/executions")
async def get_execution_history(
    limit: int = 20,
    offset: int = 0,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el historial de ejecuciones del usuario.
    
    Args:
        limit: Límite de resultados
        offset: Offset para paginación
        factory: ServiceFactory
        
    Returns:
        Historial de ejecuciones
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Obtener historial
        outcome_service = factory.get_plan_outcome_service()
        history = await outcome_service.get_user_execution_history(
            user_id=factory.user.id,
            limit=limit,
            offset=offset
        )
        
        return {
            "user_id": str(factory.user.id),
            "executions": [
                {
                    "id": str(outcome.id),
                    "plan_id": str(outcome.plan_id),
                    "total_tasks": outcome.total_tasks,
                    "completed_tasks": outcome.completed_tasks,
                    "failed_tasks": outcome.failed_tasks,
                    "success_rate": outcome.success_rate,
                    "outcome_summary": outcome.outcome_summary,
                    "created_at": outcome.created_at.isoformat()
                }
                for outcome in history
            ],
            "total": len(history),
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRecommendationRouter] ❌ Error obteniendo historial: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo historial: {str(e)}"
        )


# ===== ENDPOINTS DE INFORMACIÓN =====

@router.get("/help")
async def get_recommendations_help():
    """
    Obtiene ayuda sobre el sistema de recomendaciones.
    
    Returns:
        Información de ayuda
    """
    return {
        "title": "💡 Sistema de Recomendaciones de Planes",
        "description": "El sistema analiza tu historial de ejecución para sugerir optimizaciones y automatizaciones",
        "features": [
            {
                "feature": "Análisis de Patrones",
                "description": "Detecta patrones en tus planes ejecutados para sugerir mejoras"
            },
            {
                "feature": "Optimizaciones",
                "description": "Sugiere optimizaciones basadas en planes fallidos o lentos"
            },
            {
                "feature": "Automatizaciones",
                "description": "Identifica secuencias de tareas que se pueden automatizar"
            },
            {
                "feature": "Optimización de Recursos",
                "description": "Sugiere mejoras en el uso de memoria y CPU"
            }
        ],
        "recommendation_types": [
            {
                "type": "similar_plan",
                "description": "Planes similares que fueron exitosos"
            },
            {
                "type": "optimization",
                "description": "Sugerencias para mejorar la eficiencia"
            },
            {
                "type": "automation",
                "description": "Candidatos para automatización"
            },
            {
                "type": "pattern_detection",
                "description": "Patrones detectados en tu comportamiento"
            },
            {
                "type": "resource_optimization",
                "description": "Optimizaciones de uso de recursos"
            }
        ],
        "tips": [
            "💡 Las recomendaciones se generan automáticamente después de ejecutar planes",
            "💡 Revisa las recomendaciones de alta prioridad regularmente",
            "💡 Aplica las recomendaciones que consideres útiles",
            "💡 El sistema aprende de tus patrones de uso"
        ]
    }
