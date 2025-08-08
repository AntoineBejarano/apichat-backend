# app/routers/chat_router.py
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

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

@router.get(
    "/{chat_id}",
    response_model=ChatOut,
    summary="📖 Obtener chat específico",
    description="Obtiene un chat específico del usuario autenticado.",
)
def get_chat(chat_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    chat = factory.get_chat_service().get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return chat

@router.delete(
    "/{chat_id}",
    summary="🗑️ Eliminar chat",
    description="Elimina un chat específico del usuario autenticado.",
)
def delete_chat(chat_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    success = factory.get_chat_service().delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return {"message": "Chat eliminado exitosamente"}

@router.post(
    "/send",
    summary="✉️ Enviar mensaje a IA",
    description="Envía un mensaje a la IA y obtiene la respuesta. Parámetros opcionales para contexto.",
)
async def send_message(
    message: ChatMessage,
    chat_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    db_ids: Optional[List[UUID]] = None,
    app_ids: Optional[List[UUID]] = None,
    explorer: bool = False,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Envía un mensaje a la IA y obtiene la respuesta.
    
    Parámetros:
    - message: El mensaje del usuario
    - chat_id: ID del chat (opcional, se crea uno nuevo si no se proporciona)
    - agent_id: ID del agente (opcional)
    - db_ids: Lista de IDs de bases de datos para contexto (opcional)
    - app_ids: Lista de IDs de aplicaciones para contexto (opcional)
    - explorer: Modo explorador (opcional, default: False)
    """
    try:
        # Si no se proporciona chat_id, usar el chat más reciente o crear uno nuevo
        if not chat_id:
            chat_service = factory.get_chat_service()
            chats = chat_service.get_all(limit=1)
            if chats:
                chat_id = chats[0].id
            else:
                new_chat = chat_service.create_chat(ChatCreate(name="Auto Chat"))
                chat_id = new_chat.id

        # Llamar al orchestrator con los mismos parámetros que el WebSocket
        response = await factory.get_orchestrator_service().handle_user_message(
            chat_id=chat_id,
            db_ids=db_ids or [],
            app_ids=app_ids or [],
            explorer=explorer,
            agent_id=agent_id,
            message=message,
        )

        return {
            "success": True,
            "chat_id": chat_id,
            "assistant_response": response.get("assistant_response", "🤖 No response generated"),
            "execution_results": response.get("execution_results", {}),
            "steps": response.get("steps", []),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )

@router.post(
    "/{chat_id}/message",
    summary="✉️ Enviar mensaje a chat específico",
    description="Envía un mensaje a la IA dentro de un chat específico.",
)
async def send_message_to_chat(
    chat_id: UUID,
    message: ChatMessage,
    agent_id: Optional[UUID] = None,
    db_ids: Optional[List[UUID]] = None,
    app_ids: Optional[List[UUID]] = None,
    explorer: bool = False,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Envía un mensaje a la IA dentro de un chat específico.
    
    Parámetros:
    - chat_id: ID del chat
    - message: El mensaje del usuario
    - agent_id: ID del agente (opcional)
    - db_ids: Lista de IDs de bases de datos para contexto (opcional)
    - app_ids: Lista de IDs de aplicaciones para contexto (opcional)
    - explorer: Modo explorador (opcional, default: False)
    """
    try:
        # Llamar al orchestrator con los mismos parámetros que el WebSocket
        response = await factory.get_orchestrator_service().handle_user_message(
            chat_id=chat_id,
            db_ids=db_ids or [],
            app_ids=app_ids or [],
            explorer=explorer,
            agent_id=agent_id,
            message=message,
        )

        return {
            "success": True,
            "chat_id": chat_id,
            "assistant_response": response.get("assistant_response", "🤖 No response generated"),
            "execution_results": response.get("execution_results", {}),
            "steps": response.get("steps", []),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )

