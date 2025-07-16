import logging
from typing import List

from app.core.servicefactory import ServiceFactory
from app.models.chat_history_model import ChatHistory
from app.schemas.chat_history_schema import ChatHistoryCreate

logger = logging.getLogger(__name__)

class ChatHistoryService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        logger.info(f"[ChatHistoryService] Inicializado para user_id={self.user_id}")

    def create_message(self, data: ChatHistoryCreate) -> ChatHistory:
        logger.info(f"[ChatHistoryService] Creando nuevo mensaje para user_id={self.user_id}")
        new_message = ChatHistory(user_id=self.user_id, **data.model_dump())
        self.db.add(new_message)
        self.db.commit()
        self.db.refresh(new_message)
        return new_message

    def get_history(self, limit: int = 50) -> List[ChatHistory]:
        logger.info(f"[ChatHistoryService] Obteniendo historial de chat (limite={limit}) para user_id={self.user_id}")
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_all(self) -> int:
        logger.warning(f"[ChatHistoryService] Eliminando historial de chat para user_id={self.user_id}")
        deleted = self.db.query(ChatHistory).filter(ChatHistory.user_id == self.user_id).delete()
        self.db.commit()
        return deleted

    def append(self, message_data: dict) -> ChatHistory:
        logger.info(f"[ChatHistoryService] Añadiendo mensaje al historial de user_id={self.user_id}")

        if "role" not in message_data or "message" not in message_data:
            logger.error("[ChatHistoryService] Datos inválidos: falta 'role' o 'message'")
            raise ValueError("Message data must contain 'role' and 'message' fields")

        msg = ChatHistoryCreate(
            role=message_data["role"],
            message=message_data["message"]
        )

        return self.create_message(msg)
