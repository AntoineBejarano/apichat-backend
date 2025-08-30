"""
Router WebSocket para seguimiento en tiempo real de ejecución de planes.
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.websockets import WebSocketState

from app.core.service_factory import ServiceFactory, get_factory
from app.services.execution.plan_realtime_tracker import PlanRealtimeTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/plans", tags=["Plan WebSocket"])


# ===== WEBSOCKET ENDPOINTS =====

@router.websocket("/track/{user_id}")
async def track_user_plans(
    websocket: WebSocket,
    user_id: UUID,
    execution_id: Optional[str] = None
):
    """
    WebSocket para seguimiento en tiempo real de todos los planes de un usuario.
    
    Args:
        websocket: Conexión WebSocket
        user_id: ID del usuario
        execution_id: ID de ejecución específica (opcional)
    """
    try:
        # Crear factory para el usuario
        factory = ServiceFactory(websocket, user_id)
        tracker = PlanRealtimeTracker(factory)
        
        logger.info(f"[PlanWS] 🔌 Conexión WebSocket iniciada: usuario {user_id}, ejecución {execution_id}")
        
        # Manejar la conexión
        await tracker.handle_websocket_connection(websocket, user_id, execution_id)
        
    except WebSocketDisconnect:
        logger.info(f"[PlanWS] 🔌 WebSocket desconectado: usuario {user_id}")
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error en WebSocket: {e}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


@router.websocket("/track/execution/{execution_id}")
async def track_execution(
    websocket: WebSocket,
    execution_id: str,
    user_id: UUID
):
    """
    WebSocket para seguimiento en tiempo real de una ejecución específica.
    
    Args:
        websocket: Conexión WebSocket
        execution_id: ID de la ejecución
        user_id: ID del usuario
    """
    try:
        # Crear factory para el usuario
        factory = ServiceFactory(websocket, user_id)
        tracker = PlanRealtimeTracker(factory)
        
        logger.info(f"[PlanWS] 🔌 Conexión WebSocket iniciada: ejecución {execution_id}, usuario {user_id}")
        
        # Manejar la conexión
        await tracker.handle_websocket_connection(websocket, user_id, execution_id)
        
    except WebSocketDisconnect:
        logger.info(f"[PlanWS] 🔌 WebSocket desconectado: ejecución {execution_id}")
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error en WebSocket: {e}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011, reason="Internal server error")
        except:
            pass


# ===== ENDPOINTS DE INFORMACIÓN =====

@router.get("/connections/count")
async def get_connection_count(
    user_id: Optional[UUID] = None,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el número de conexiones WebSocket activas.
    
    Args:
        user_id: ID del usuario (opcional, si no se proporciona devuelve total)
        factory: ServiceFactory
        
    Returns:
        Dict con el número de conexiones
    """
    try:
        if not factory.user and not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        target_user_id = user_id or factory.user.id if factory.user else None
        
        count = tracker.get_connection_count(target_user_id)
        
        return {
            "user_id": str(target_user_id) if target_user_id else "all",
            "connection_count": count,
            "timestamp": "2024-01-01T00:00:00Z"  # TODO: Usar datetime real
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error obteniendo conteo de conexiones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo conteo de conexiones: {str(e)}"
        )


@router.get("/execution/{execution_id}/connections/count")
async def get_execution_connection_count(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el número de conexiones WebSocket para una ejecución específica.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Dict con el número de conexiones
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        count = tracker.get_execution_connection_count(execution_id)
        
        return {
            "execution_id": execution_id,
            "connection_count": count,
            "timestamp": "2024-01-01T00:00:00Z"  # TODO: Usar datetime real
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error obteniendo conteo de conexiones de ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo conteo de conexiones: {str(e)}"
        )


# ===== ENDPOINTS DE CONTROL =====

@router.post("/execution/{execution_id}/pause")
async def pause_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Pausa la ejecución de un plan.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Dict con el resultado de la operación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        success = await tracker.execution_service.pause_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "paused": success,
            "message": "Ejecución pausada exitosamente" if success else "Error pausando ejecución"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error pausando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Reanuda la ejecución de un plan pausado.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Dict con el resultado de la operación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        success = await tracker.execution_service.resume_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "resumed": success,
            "message": "Ejecución reanudada exitosamente" if success else "Error reanudando ejecución"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error reanudando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reanudando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Cancela la ejecución de un plan.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Dict con el resultado de la operación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        success = await tracker.execution_service.cancel_execution(execution_id, factory.user.id)
        
        return {
            "execution_id": execution_id,
            "cancelled": success,
            "message": "Ejecución cancelada exitosamente" if success else "Error cancelando ejecución"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error cancelando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelando ejecución: {str(e)}"
        )


# ===== ENDPOINTS DE ESTADO =====

@router.get("/execution/{execution_id}/status")
async def get_execution_status(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el estado actual de una ejecución.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Dict con el estado de la ejecución
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        tracker = PlanRealtimeTracker(factory)
        status = await tracker.execution_service.get_execution_status(execution_id, factory.user.id)
        
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ejecución no encontrada"
            )
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanWS] ❌ Error obteniendo estado de ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado de ejecución: {str(e)}"
        )
