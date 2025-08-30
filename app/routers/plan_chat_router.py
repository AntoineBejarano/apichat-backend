"""
Router para chat con integración de planes.
"""

import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.service_factory import ServiceFactory, get_factory
from app.services.chat.plan_chat_commands_service import PlanChatCommandsService
from app.services.ai.unified_chat_service import ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/plans", tags=["Plan Chat"])


# ===== SCHEMAS =====

class ChatMessageRequest(BaseModel):
    """Request para mensaje de chat con planes."""
    message: str
    chat_id: Optional[UUID] = None
    app_id: Optional[UUID] = None
    db_id: Optional[UUID] = None
    auto_execute_apis: bool = False


class ChatMessageResponse(BaseModel):
    """Response para mensaje de chat con planes."""
    success: bool
    message: str
    response_type: str
    data: Optional[dict] = None
    execution_results: Optional[list] = None
    suggestions: Optional[list] = None
    requires_confirmation: bool = False


class PlanExecutionRequest(BaseModel):
    """Request para ejecutar plan desde chat."""
    plan_id: UUID
    auto_confirm: bool = False


class PlanExecutionResponse(BaseModel):
    """Response para ejecución de plan desde chat."""
    success: bool
    message: str
    response_type: str
    data: Optional[dict] = None


# ===== ENDPOINTS =====

@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    request: ChatMessageRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Envía un mensaje de chat con detección automática de planes.
    
    Args:
        request: Datos del mensaje de chat
        factory: ServiceFactory
        
    Returns:
        Respuesta del chat con posible plan o ejecución
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Procesar mensaje con comandos de planes
        chat_service = factory.get_plan_chat_commands_service()
        response = await chat_service.process_chat_message(
            message=request.message,
            user_id=factory.user.id,
            chat_id=request.chat_id,
            app_id=request.app_id,
            db_id=request.db_id,
            auto_execute_apis=request.auto_execute_apis
        )
        
        logger.info(f"[PlanChatRouter] 💬 Mensaje procesado: {response.response_type}")
        
        return ChatMessageResponse(
            success=response.success,
            message=response.message,
            response_type=response.response_type,
            data=response.data,
            execution_results=response.execution_results,
            suggestions=response.suggestions,
            requires_confirmation=response.requires_confirmation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error procesando mensaje: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando mensaje: {str(e)}"
        )


@router.post("/execute-plan", response_model=PlanExecutionResponse)
async def execute_plan_from_chat(
    request: PlanExecutionRequest,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Ejecuta un plan desde el chat.
    
    Args:
        request: Datos de ejecución del plan
        factory: ServiceFactory
        
    Returns:
        Respuesta de la ejecución del plan
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Ejecutar plan
        chat_service = factory.get_plan_chat_integration_service()
        response = await chat_service.execute_plan_from_chat(
            plan_id=request.plan_id,
            user_id=factory.user.id,
            auto_confirm=request.auto_confirm
        )
        
        logger.info(f"[PlanChatRouter] 🚀 Plan ejecutado: {request.plan_id}")
        
        return PlanExecutionResponse(
            success=response.success,
            message=response.message,
            response_type=response.response_type,
            data=response.data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error ejecutando plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ejecutando plan: {str(e)}"
        )


@router.get("/execution/{execution_id}/status")
async def get_execution_status_from_chat(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene el estado de una ejecución desde el chat.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Estado de la ejecución
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Obtener estado
        chat_service = factory.get_plan_chat_integration_service()
        response = await chat_service.get_plan_status_from_chat(
            execution_id=execution_id,
            user_id=factory.user.id
        )
        
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=response.message
            )
        
        return response.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error obteniendo estado: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estado: {str(e)}"
        )


@router.post("/execution/{execution_id}/pause")
async def pause_execution_from_chat(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Pausa una ejecución desde el chat.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Resultado de la pausa
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Pausar ejecución
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.pause_execution(execution_id, factory.user.id)
        
        if success:
            return {
                "success": True,
                "message": "⏸️ Ejecución pausada exitosamente",
                "execution_id": execution_id,
                "paused": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error pausando la ejecución"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error pausando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error pausando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/resume")
async def resume_execution_from_chat(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Reanuda una ejecución desde el chat.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Resultado de la reanudación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Reanudar ejecución
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.resume_execution(execution_id, factory.user.id)
        
        if success:
            return {
                "success": True,
                "message": "▶️ Ejecución reanudada exitosamente",
                "execution_id": execution_id,
                "resumed": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error reanudando la ejecución"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error reanudando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reanudando ejecución: {str(e)}"
        )


@router.post("/execution/{execution_id}/cancel")
async def cancel_execution_from_chat(
    execution_id: str,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Cancela una ejecución desde el chat.
    
    Args:
        execution_id: ID de la ejecución
        factory: ServiceFactory
        
    Returns:
        Resultado de la cancelación
    """
    try:
        if not factory.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no autenticado"
            )
        
        # Cancelar ejecución
        execution_service = factory.get_plan_execution_service()
        success = await execution_service.cancel_execution(execution_id, factory.user.id)
        
        if success:
            return {
                "success": True,
                "message": "🛑 Ejecución cancelada exitosamente",
                "execution_id": execution_id,
                "cancelled": True
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error cancelando la ejecución"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PlanChatRouter] ❌ Error cancelando ejecución: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelando ejecución: {str(e)}"
        )


# ===== ENDPOINTS DE INFORMACIÓN =====

@router.get("/help")
async def get_plan_chat_help():
    """
    Obtiene ayuda sobre los comandos de chat con planes.
    
    Returns:
        Lista de comandos disponibles
    """
    return {
        "title": "🎯 Comandos de Chat con Planes",
        "description": "Comandos disponibles para interactuar con el sistema de planes desde el chat",
        "commands": [
            {
                "command": "crear plan para: [objetivo]",
                "description": "Crea un plan complejo para el objetivo especificado",
                "example": "crear plan para: migrar datos de usuarios a nueva estructura"
            },
            {
                "command": "ejecutar plan: [plan_id]",
                "description": "Ejecuta un plan existente",
                "example": "ejecutar plan: 123e4567-e89b-12d3-a456-426614174000"
            },
            {
                "command": "pausar ejecución: [execution_id]",
                "description": "Pausa una ejecución en curso",
                "example": "pausar ejecución: 123e4567-e89b-12d3-a456-426614174000"
            },
            {
                "command": "reanudar ejecución: [execution_id]",
                "description": "Reanuda una ejecución pausada",
                "example": "reanudar ejecución: 123e4567-e89b-12d3-a456-426614174000"
            },
            {
                "command": "cancelar ejecución: [execution_id]",
                "description": "Cancela una ejecución en curso",
                "example": "cancelar ejecución: 123e4567-e89b-12d3-a456-426614174000"
            },
            {
                "command": "estado ejecución: [execution_id]",
                "description": "Obtiene el estado de una ejecución",
                "example": "estado ejecución: 123e4567-e89b-12d3-a456-426614174000"
            },
            {
                "command": "listar planes",
                "description": "Muestra todos los planes del usuario",
                "example": "listar planes"
            }
        ],
        "tips": [
            "💡 Los planes se generan automáticamente para consultas complejas",
            "💡 Puedes usar comandos en español o inglés",
            "💡 Los IDs de plan y ejecución se muestran en las respuestas",
            "💡 Usa 'auto' en ejecutar plan para confirmación automática"
        ]
    }
