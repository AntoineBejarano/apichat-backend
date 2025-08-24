# app/routers/background_task_router.py
"""
Background Task Router
─────────────────────
Endpoints para gestionar tareas en background.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.core.service_factory import get_service_factory
from app.services.management.background_task_service import BackgroundTaskService, TaskPriority
from app.schemas.background_task_schema import (
    TaskCreate, TaskResponse, TaskStatusResponse, TaskListResponse, TASK_TYPES_INFO
)

router = APIRouter(prefix="/background-tasks", tags=["Background Tasks"])


@router.post("/submit", response_model=TaskResponse)
async def submit_background_task(
    task_data: TaskCreate,
    factory = Depends(get_service_factory)
):
    """
    Enviar una tarea al background.
    
    Tipos de tareas disponibles:
    - vector_search_update: Actualizar embeddings de vector search
    - schema_cache_refresh: Refrescar cache de esquemas
    - performance_metrics_collection: Recolectar métricas de performance
    - data_processing: Procesar datos pesados
    - report_generation: Generar reportes complejos
    """
    try:
        background_service = factory.get_background_task_service()
        
        # Convertir priority string a enum
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.CRITICAL
        }
        priority = priority_map.get(task_data.priority.lower(), TaskPriority.NORMAL)
        
        task_id = background_service.submit_task(
            task_type=task_data.task_type,
            payload=task_data.payload,
            priority=priority
        )
        
        return TaskResponse(
            task_id=task_id,
            status="submitted",
            message="Tarea enviada al background correctamente"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error enviando tarea al background: {str(e)}"
        )


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    factory = Depends(get_service_factory)
):
    """Obtener el estado de una tarea en background"""
    try:
        background_service = factory.get_background_task_service()
        task = background_service.get_task_status(task_id)
        
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada"
            )
        
        return TaskStatusResponse(
            task_id=task.id,
            status=task.status.value,
            progress=task.progress,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            result=task.result,
            error=task.error,
            retry_count=task.retry_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado de tarea: {str(e)}"
        )


@router.delete("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    factory = Depends(get_service_factory)
):
    """Cancelar una tarea en background"""
    try:
        background_service = factory.get_background_task_service()
        cancelled = background_service.cancel_task(task_id)
        
        if not cancelled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada o no se puede cancelar"
            )
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "message": "Tarea cancelada correctamente"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelando tarea: {str(e)}"
        )


@router.get("/stats")
async def get_background_service_stats(
    factory = Depends(get_service_factory)
):
    """Obtener estadísticas del servicio de background"""
    try:
        background_service = factory.get_background_task_service()
        stats = background_service.get_stats()
        
        return {
            "service_stats": stats,
            "message": "Estadísticas del servicio de background"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.get("/", response_model=TaskListResponse)
async def list_active_tasks(
    factory = Depends(get_service_factory)
):
    """Listar todas las tareas activas"""
    try:
        background_service = factory.get_background_task_service()
        
        active_tasks = []
        for task in background_service.active_tasks.values():
            active_tasks.append(TaskStatusResponse(
                task_id=task.id,
                status=task.status.value,
                progress=task.progress,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                result=task.result,
                error=task.error,
                retry_count=task.retry_count
            ))
        
        return TaskListResponse(
            tasks=active_tasks,
            total_count=len(active_tasks)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listando tareas: {str(e)}"
        )


@router.post("/cleanup")
async def cleanup_old_tasks(
    max_age_hours: int = 24,
    factory = Depends(get_service_factory)
):
    """Limpiar tareas antiguas"""
    try:
        background_service = factory.get_background_task_service()
        background_service.cleanup_old_tasks(max_age_hours)
        
        return {
            "status": "completed",
            "message": f"Limpieza completada (tareas más antiguas de {max_age_hours} horas)"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en limpieza: {str(e)}"
        )


@router.get("/task-types")
async def get_task_types():
    """Obtener información de los tipos de tareas disponibles"""
    return {
        "task_types": TASK_TYPES_INFO,
        "message": "Tipos de tareas disponibles"
    }
