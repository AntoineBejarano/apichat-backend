import logging
from typing import Optional, List

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

from app.models.chat_model import Chat
from app.schemas.chat_schema import ChatCreate
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id = factory.user.id
        logger.info(f"[ChatService] Inicializado para user_id={self.user_id}")

    def create_chat(self, data: ChatCreate) -> Chat:
        logger.info(f"[ChatService] Creando nuevo chat para user_id={self.user_id}")
        new_chat = Chat(user_id=self.user_id, **data.model_dump())
        self.db.add(new_chat)
        self.db.commit()
        self.db.refresh(new_chat)
        return new_chat

    def get_chat(self, chat_id: int) -> Optional[Chat]:
        logger.info(f"[ChatService] Obteniendo chat_id={chat_id} para user_id={self.user_id}")
        return (
            self.db.query(Chat)
            .filter(Chat.id == chat_id, Chat.user_id == self.user_id)
            .first()
        )

    def get_all(self, limit: int = 50) -> List[Chat]:
        logger.info(f"[ChatService] Obteniendo todos los chats de user_id={self.user_id} (limite={limit})")
        return (
            self.db.query(Chat)
            .filter(Chat.user_id == self.user_id)
            .order_by(Chat.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_chat(self, chat_id: int) -> bool:
        logger.warning(f"[ChatService] Eliminando chat_id={chat_id} para user_id={self.user_id}")
        chat = self.get_chat(chat_id)
        if not chat:
            logger.error(f"[ChatService] Chat no encontrado para id={chat_id}")
            return False
        self.db.delete(chat)
        self.db.commit()
        return True
