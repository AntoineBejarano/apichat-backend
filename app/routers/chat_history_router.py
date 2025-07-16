from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.core.database import get_db
from app.core.servicefactory import ServiceFactory

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat History"],
    responses={
        400: {"description": "Petición inválida"},
        404: {"description": "No encontrado"},
        500: {"description": "Error interno del servidor"}
    }
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    response_model=ChatHistoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir mensaje al historial",
    response_description="Mensaje guardado correctamente"
)
def add_message(
    data: ChatHistoryCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Guarda un nuevo mensaje en el historial de chat del usuario autenticado.
    """
    return factory.get_openai_service().create_chat_message(factory.user.id, data)


@router.get(
    "/",
    response_model=List[ChatHistoryOut],
    summary="Obtener historial de chat",
    response_description="Listado de mensajes del usuario"
)
def fetch_chat(factory: ServiceFactory = Depends(get_factory)):
    """
    Devuelve todo el historial de chat del usuario autenticado.
    """
    return factory.get_openai_service().get_chat_history(factory.user.id)


@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Eliminar historial de chat",
    response_description="Historial eliminado correctamente"
)
def clear_history(factory: ServiceFactory = Depends(get_factory)):
    """
    Elimina todo el historial de chat del usuario autenticado.
    """
    deleted = factory.get_openai_service().delete_chat_history(factory.user.id)
    return {"deleted": deleted}
