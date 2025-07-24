from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut

router = APIRouter(
    prefix="/chat-history",
    tags=["🕓 Chat History"],
    responses={
        400: {"description": "Petición inválida"},
        404: {"description": "No encontrado"},
        500: {"description": "Error interno del servidor"},
    },
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    response_model=ChatHistoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="📝 Añadir mensaje al historial",
    description="Guarda un nuevo mensaje en el historial de chat del usuario autenticado.",
)
def add_message_to_history(
    data: ChatHistoryCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_chat_history_service().create_message(data)

@router.get(
    "/all",
    response_model=List[ChatHistoryOut],
    summary="📜 Obtener TODO el historial del usuario",
)
def get_all_chat_history(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_history_service().get_all()


@router.get(
    "/{chat_id}",
    response_model=List[ChatHistoryOut],
    summary="📜 Obtener historial por chat_id",
)
def get_chat_history(chat_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_history_service().get_history(chat_id)


@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="🗑️ Eliminar historial",
    description="Elimina todo el historial de chat del usuario autenticado.",
)
def delete_chat_history(factory: ServiceFactory = Depends(get_factory)):
    deleted = factory.get_chat_history_service().delete_all()
    return {"deleted": deleted}
