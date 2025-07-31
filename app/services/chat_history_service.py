import logging
from typing import List
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

from app.models.chat_history_model import ChatHistory
from app.schemas.chat_history_schema import ChatHistoryCreate
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ChatHistoryService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id = factory.user.id
        logger.info(f"[ChatHistoryService] Inicializado para user_id={self.user_id}")

    def create_message(self, data: ChatHistoryCreate) -> ChatHistory:
        logger.info(f"[ChatHistoryService] Creando nuevo mensaje para user_id={self.user_id}")
        message = ChatHistory(
            user_id=self.user_id,
            chat_id=data.chat_id,
            role=data.role,
            content=data.content,
            name=data.name,
            token_count=data.token_count,
            is_function_call=data.is_function_call,
            function_call_id=data.function_call_id
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_history(self, chat_id: UUID, limit: int = 50) -> List[ChatHistory]:
        logger.info(f"[ChatHistoryService] Obteniendo historial para chat_id={chat_id}, user_id={self.user_id} con límite={limit}")
        limit = min(limit, 1000)
        return (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.chat_id == chat_id,
                ChatHistory.user_id == self.user_id
            )
            .order_by(ChatHistory.timestamp.asc())
            .limit(limit)
            .all()
        )


    def delete_all_for_chat(self, chat_id: UUID) -> int:
        logger.warning(f"[ChatHistoryService] Eliminando historial de chat_id={chat_id} para user_id={self.user_id}")
        deleted = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.chat_id == chat_id,
                ChatHistory.user_id == self.user_id
            )
            .delete()
        )
        self.db.commit()
        return deleted

    def append(self, data: dict) -> ChatHistory:
        logger.info(f"[ChatHistoryService] Añadiendo mensaje para user_id={self.user_id}")
        required = ("chat_id", "role", "content")
        if not all(key in data for key in required):
            logger.error(
                "[ChatHistoryService] Datos inválidos: "
                f"faltan campos obligatorios {required}"
            )
            raise ValueError(f"Faltan campos requeridos: {required}")
        msg = ChatHistoryCreate(
            chat_id=data["chat_id"],
            role=data["role"],
            content=data["content"],
            name=data.get("name"),
            token_count=data.get("token_count"),
            is_function_call=data.get("is_function_call", False),
            function_call_id=data.get("function_call_id"),
        )
        return self.create_message(msg)
    
    def get_all(self, limit: int = 1000) -> List[ChatHistory]:
        logger.info(f"[ChatHistoryService] Obteniendo TODO el historial de user_id={self.user_id} con límite={limit}")
        limit = min(limit, 1000)
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id)
            .order_by(ChatHistory.timestamp.desc())
            .limit(limit)
            .all()
        )
