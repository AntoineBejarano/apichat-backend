# app/routers/chat_router.py
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage, ChatCreate, ChatOut
from app.schemas.chat_history_schema import ChatHistoryOut

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat IA"],
    responses={404: {"description": "No encontrado"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    response_model=ChatOut,
    summary="🧠 Crear nuevo chat",
    description="Crea una nueva sesión de chat del usuario con IA.",
)
def create_chat(chat: ChatCreate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_service().create_chat(chat)

@router.get(
    "/",
    response_model=List[ChatOut],
    summary="📚 Listar chats del usuario",
    description="Devuelve todos los chats del usuario autenticado.",
)
def list_user_chats(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_service().get_all()

@router.delete(
    "/{chat_id}",
    response_model=dict,
    summary="🗑️ Eliminar un chat",
    description="Elimina un chat específico por ID.",
)
def delete_chat(chat_id: int, factory: ServiceFactory = Depends(get_factory)):
    deleted = factory.get_chat_service().delete_chat(chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="❌ Chat no encontrado")
    return {"deleted": True}

@router.get(
    "/{chat_id}/history",
    response_model=List[ChatHistoryOut],
    summary="🕓 Historial de un chat",
    description="Obtiene el historial de mensajes de un chat específico.",
)
def get_chat_history(chat_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_history_service().get_chat_history(chat_id)

@router.post(
    "/{chat_id}/message",
    response_model=ChatHistoryOut,
    summary="✉️ Enviar mensaje a IA",
    description="Envía un mensaje a la IA dentro de un chat específico.",
)
def send_message_to_chat(
    chat_id: int,
    message: ChatMessage,
    factory: ServiceFactory = Depends(get_factory),
):
    try:
        return factory.get_orchestrator_service().handle_chat_message(
            chat_id=chat_id,
            message=message,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )
