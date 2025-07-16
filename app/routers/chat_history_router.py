# app/routers/chat_history_router.py
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat History"],
    responses={
        400: {"description": "Petición inválida"},
        404: {"description": "No encontrado"},
        500: {"description": "Error interno del servidor"},
    },
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

# ─────────────────────────────────────────────────────────────────────────────
#  POST ▸ /chat/  ➜  Guardar mensaje
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=ChatHistoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir mensaje al historial",
    response_description="Mensaje guardado correctamente",
)
def add_message_to_history(
    data: ChatHistoryCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Guarda un nuevo mensaje en el historial de chat del usuario autenticado.
    """
    history_srv = factory.get_chat_history_service()
    return history_srv.create_message(data)

# ─────────────────────────────────────────────────────────────────────────────
#  GET ▸ /chat/  ➜  Listar historial
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=List[ChatHistoryOut],
    summary="Obtener historial de chat",
    response_description="Listado de mensajes del usuario",
)
def get_chat_history(factory: ServiceFactory = Depends(get_factory)):
    """
    Devuelve todo el historial de chat del usuario autenticado.
    """
    history_srv = factory.get_chat_history_service()
    return history_srv.get_history()

# ─────────────────────────────────────────────────────────────────────────────
#  DELETE ▸ /chat/  ➜  Borrar historial
# ─────────────────────────────────────────────────────────────────────────────
@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Eliminar historial de chat",
    response_description="Historial eliminado correctamente",
)
def delete_chat_history(factory: ServiceFactory = Depends(get_factory)):
    """
    Elimina todo el historial de chat del usuario autenticado.
    """
    history_srv = factory.get_chat_history_service()
    deleted = history_srv.delete_all()
    return {"deleted": deleted}
