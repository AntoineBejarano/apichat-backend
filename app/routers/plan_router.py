"""
Router para gestión de planes y to-dos.
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.service_factory import ServiceFactory, get_factory
from app.schemas.plan_schema import (
    UserPlanCreate, UserPlanUpdate, UserPlanOut,
    PlanTaskCreate, PlanTaskUpdate, PlanTaskOut,
    PlanGenerationRequest, PlanGenerationResponse,
    PlanQuery, PlanListResponse,
    PlanExecutionRequest, PlanExecutionResponse,
    TaskExecutionUpdate
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["Plans & To-dos"])


# ===== ENDPOINTS DE PLANES =====

@router.post("/", response_model=UserPlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    plan_data: UserPlanCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """Crea un nuevo plan para el usuario."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        plan = await plan_service.create_plan(plan_data, factory.user.id)
        
        logger.info(f"[PlanRouter] ✅ Plan creado: {plan.id}")
        return plan
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error creando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando plan: {str(e)}"
        )


@router.get("/", response_model=PlanListResponse)
async def list_plans(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    factory: ServiceFactory = Depends(get_factory)
):
    """Lista los planes del usuario con filtros."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        query = PlanQuery(
            user_id=factory.user.id,
            status=status,
            priority=priority,
            limit=limit,
            offset=offset
        )
        
        plan_service = factory.get_plan_service()
        result = await plan_service.list_plans(factory.user.id, query)
        
        return result
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error listando planes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando planes: {str(e)}"
        )


@router.get("/{plan_id}", response_model=UserPlanOut)
async def get_plan(
    plan_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """Obtiene un plan específico del usuario."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        plan = await plan_service.get_plan(plan_id, factory.user.id)
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan no encontrado"
            )
        
        return plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error obteniendo plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo plan: {str(e)}"
        )


@router.put("/{plan_id}", response_model=UserPlanOut)
async def update_plan(
    plan_id: UUID,
    plan_data: UserPlanUpdate,
    factory: ServiceFactory = Depends(get_factory)
):
    """Actualiza un plan existente."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        plan = await plan_service.update_plan(plan_id, factory.user.id, plan_data)
        
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan no encontrado"
            )
        
        logger.info(f"[PlanRouter] ✅ Plan actualizado: {plan.id}")
        return plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error actualizando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando plan: {str(e)}"
        )


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """Elimina un plan y todas sus tareas."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        deleted = await plan_service.delete_plan(plan_id, factory.user.id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan no encontrado"
            )
        
        logger.info(f"[PlanRouter] ✅ Plan eliminado: {plan_id}")
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error eliminando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error eliminando plan: {str(e)}"
        )


# ===== ENDPOINTS DE TAREAS =====

@router.post("/{plan_id}/tasks", response_model=PlanTaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    plan_id: UUID,
    task_data: PlanTaskCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """Crea una nueva tarea en un plan."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        task = await plan_service.create_task(plan_id, factory.user.id, task_data)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan no encontrado"
            )
        
        logger.info(f"[PlanRouter] ✅ Tarea creada: {task.id}")
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error creando tarea: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creando tarea: {str(e)}"
        )


@router.get("/{plan_id}/tasks", response_model=List[PlanTaskOut])
async def get_plan_tasks(
    plan_id: UUID,
    factory: ServiceFactory = Depends(get_factory)
):
    """Obtiene todas las tareas de un plan."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        tasks = await plan_service.get_plan_tasks(plan_id, factory.user.id)
        
        return tasks
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error obteniendo tareas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo tareas: {str(e)}"
        )


@router.put("/tasks/{task_id}", response_model=PlanTaskOut)
async def update_task(
    task_id: UUID,
    task_data: PlanTaskUpdate,
    factory: ServiceFactory = Depends(get_factory)
):
    """Actualiza una tarea existente."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        task = await plan_service.update_task(task_id, factory.user.id, task_data)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        logger.info(f"[PlanRouter] ✅ Tarea actualizada: {task.id}")
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error actualizando tarea: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error actualizando tarea: {str(e)}"
        )


# ===== ENDPOINTS DE GENERACIÓN =====

@router.post("/generate", response_model=PlanGenerationResponse)
async def generate_plan(
    request: PlanGenerationRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """Genera un plan detallado basado en el objetivo del usuario."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # 1. Detectar tipo de plan necesario
        detection_service = factory.get_plan_detection_service()
        detection_result = detection_service.detect_plan_type(
            user_prompt=request.user_prompt,
            context=request.context,
            user_id=factory.user.id,
            database_info=request.database_info,
            application_info=request.application_info,
            api_info=request.api_info
        )
        
        # 2. Si es plan simple, usar sistema existente
        if detection_result.should_use_existing:
            logger.info(f"[PlanRouter] 🔄 Usando sistema existente para plan simple")
            # TODO: Integrar con PlanBuilderService existente
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Integración con sistema existente pendiente"
            )
        
        # 3. Generar plan complejo
        generation_service = factory.get_plan_generation_service()
        generated_plan = await generation_service.generate_plan(
            user_prompt=request.user_prompt,
            user_id=factory.user.id,
            context=request.context,
            database_info=request.database_info,
            application_info=request.application_info,
            api_info=request.api_info
        )
        
        # 4. Guardar plan en base de datos
        plan_service = factory.get_plan_service()
        plan_data = UserPlanCreate(
            title=generated_plan.title,
            description=generated_plan.description,
            priority="medium",  # TODO: Determinar prioridad basada en complejidad
            estimated_duration=generated_plan.total_estimated_effort,
            metadata={
                "complexity": generated_plan.complexity.value,
                "generated_at": generated_plan.generated_at.isoformat(),
                "requires_confirmation": generated_plan.requires_confirmation
            }
        )
        
        saved_plan = await plan_service.create_plan(plan_data, factory.user.id)
        
        # 5. Crear tareas
        tasks = []
        for i, task in enumerate(generated_plan.tasks):
            task_data = PlanTaskCreate(
                title=task.title,
                description=task.description,
                order_index=i,
                estimated_effort=task.estimated_effort,
                dependencies=task.dependencies
            )
            
            saved_task = await plan_service.create_task(saved_plan.id, factory.user.id, task_data)
            if saved_task:
                tasks.append(saved_task)
        
        logger.info(f"[PlanRouter] ✅ Plan generado: {saved_plan.id} con {len(tasks)} tareas")
        
        return PlanGenerationResponse(
            plan=saved_plan,
            tasks=tasks,
            estimated_total_effort=generated_plan.total_estimated_effort,
            requires_confirmation=generated_plan.requires_confirmation,
            fallback_plan=generated_plan.fallback_plan
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error generando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando plan: {str(e)}"
        )


# ===== ENDPOINTS DE ESTADÍSTICAS =====

@router.get("/statistics/overview")
async def get_plan_statistics(
    factory: ServiceFactory = Depends(get_factory)
):
    """Obtiene estadísticas de planes del usuario."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        plan_service = factory.get_plan_service()
        stats = await plan_service.get_plan_statistics(factory.user.id)
        
        return stats
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


# ===== ENDPOINTS DE DETECCIÓN =====

@router.post("/detect-type")
async def detect_plan_type(
    request: PlanGenerationRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """Detecta el tipo de plan necesario para una consulta."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        detection_service = factory.get_plan_detection_service()
        result = detection_service.detect_plan_type(
            user_prompt=request.user_prompt,
            context=request.context,
            user_id=factory.user.id,
            database_info=request.database_info,
            application_info=request.application_info,
            api_info=request.api_info
        )
        
        return {
            "plan_type": result.plan_type.value,
            "complexity": result.complexity.value,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "should_use_existing": result.should_use_existing,
            "estimated_steps": result.estimated_steps
        }
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error detectando tipo de plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error detectando tipo de plan: {str(e)}"
        )


# ===== ENDPOINTS DE EJECUCIÓN =====

@router.post("/{plan_id}/execute", response_model=PlanExecutionResponse)
async def execute_plan(
    plan_id: UUID,
    request: PlanExecutionRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """Inicia la ejecución de un plan."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Verificar que el plan existe
        plan_service = factory.get_plan_service()
        plan = await plan_service.get_plan(plan_id, factory.user.id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Plan no encontrado"
            )
        
        # Iniciar ejecución
        execution_service = factory.get_plan_execution_service()
        result = await execution_service.start_plan_execution(
            plan_id=plan_id,
            user_id=factory.user.id,
            auto_confirm=request.auto_confirm,
            start_from_task=request.start_from_task
        )
        
        logger.info(f"[PlanRouter] ✅ Ejecución iniciada: {result.execution_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error ejecutando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando plan: {str(e)}"
        )


@router.get("/execution/{execution_id}/status")
async def get_execution_status(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """Obtiene el estado de una ejecución."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        execution_service = factory.get_plan_execution_service()
        status = await execution_service.get_execution_status(execution_id, factory.user.id)
        
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ejecución no encontrada"
            )
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error obteniendo estado de ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado de ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """Pausa la ejecución de un plan."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.pause_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "paused": success,
            "message": "Ejecución pausada exitosamente" if success else "Error pausando ejecución"
        }
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error pausando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """Reanuda la ejecución de un plan pausado."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.resume_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "resumed": success,
            "message": "Ejecución reanudada exitosamente" if success else "Error reanudando ejecución"
        }
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error reanudando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reanudando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """Cancela la ejecución de un plan."""
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.cancel_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "cancelled": success,
            "message": "Ejecución cancelada exitosamente" if success else "Error cancelando ejecución"
        }
        
    except Exception as e:
        logger.error(f"[PlanRouter] ❌ Error cancelando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelando ejecución: {str(e)}"
        )
