from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, Dict, Any, List
from uuid import UUID

from app.dependencies import get_service_factory
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage

router = APIRouter(
    prefix="/unified-chat",
    tags=["💬 Unified Chat"],
    responses={
        401: {"description": "No autorizado"},
        500: {"description": "Error interno del servidor"},
    },
)


@router.post(
    "/send",
    summary="💬 Enviar mensaje al chat unificado",
    description="Envía un mensaje al chat unificado que detecta automáticamente si es para DB o APIs"
)
async def send_unified_message(
    message: ChatMessage,
    chat_id: Optional[UUID] = Query(default=None, description="ID del chat (opcional)"),
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    auto_execute_apis: bool = Query(default=False, description="Ejecutar APIs automáticamente"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Enviar mensaje al chat unificado con detección automática de intención"""
    try:
        unified_chat_service = factory.get_unified_chat_service()
        
        response = await unified_chat_service.process_chat_message(
            message=message.content,
            user_id=factory.user.id,
            chat_id=chat_id,
            app_id=app_id,
            db_id=db_id,
            auto_execute_apis=auto_execute_apis
        )
        
        return {
            "success": response.success,
            "message": response.message,
            "response_type": response.response_type,
            "data": response.data,
            "execution_results": response.execution_results,
            "suggestions": response.suggestions,
            "requires_confirmation": response.requires_confirmation,
            "chat_id": chat_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando mensaje: {str(e)}"
        )


@router.post(
    "/confirm-api-execution",
    summary="✅ Confirmar ejecución de API",
    description="Confirmar la ejecución de un plan de API"
)
async def confirm_api_execution(
    plan_data: Dict[str, Any],
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Confirmar ejecución de un plan de API"""
    try:
        unified_chat_service = factory.get_unified_chat_service()
        
        response = await unified_chat_service.confirm_api_execution(
            plan_data=plan_data,
            user_id=factory.user.id
        )
        
        return {
            "success": response.success,
            "message": response.message,
            "response_type": response.response_type,
            "data": response.data,
            "execution_results": response.execution_results
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error confirmando ejecución: {str(e)}"
        )


@router.get(
    "/suggestions",
    summary="💡 Obtener sugerencias de chat",
    description="Obtener sugerencias basadas en el contexto del usuario"
)
async def get_chat_suggestions(
    partial_message: str = Query(description="Mensaje parcial para sugerencias"),
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtener sugerencias de chat basadas en el contexto"""
    try:
        unified_chat_service = factory.get_unified_chat_service()
        
        suggestions = await unified_chat_service.get_chat_suggestions(
            partial_message=partial_message,
            user_id=factory.user.id,
            app_id=app_id,
            db_id=db_id
        )
        
        return {
            "suggestions": suggestions,
            "partial_message": partial_message
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo sugerencias: {str(e)}"
        )


@router.get(
    "/analytics",
    summary="📊 Obtener analytics del chat unificado",
    description="Obtener estadísticas de uso del chat unificado"
)
async def get_chat_analytics(
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtener analytics del chat unificado"""
    try:
        unified_chat_service = factory.get_unified_chat_service()
        
        analytics = await unified_chat_service.get_chat_analytics(
            user_id=factory.user.id
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo analytics: {str(e)}"
        )


@router.post(
    "/test-intent",
    summary="🧪 Probar detección de intención",
    description="Probar la detección de intención sin ejecutar acciones"
)
async def test_intent_detection(
    message: ChatMessage,
    app_id: Optional[UUID] = Query(default=None, description="ID de la app (opcional)"),
    db_id: Optional[UUID] = Query(default=None, description="ID de la base de datos (opcional)"),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Probar detección de intención sin ejecutar acciones"""
    try:
        unified_chat_service = factory.get_unified_chat_service()
        
        # Usar el método interno de detección de intención
        intent = await unified_chat_service._detect_message_intent(
            message=message.content,
            user_id=factory.user.id,
            app_id=app_id,
            db_id=db_id
        )
        
        return {
            "message": message.content,
            "detected_intent": intent,
            "test_mode": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error probando detección de intención: {str(e)}"
        )
