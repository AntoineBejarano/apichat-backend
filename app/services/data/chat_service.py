import logging
from typing import Optional, List

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from fastapi import HTTPException
from datetime import timezone

from app.models.chat_model import Chat
from app.models.token_usage_model import TokenUsage
from app.schemas.chat_schema import ChatCreate

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id = factory.user.id
        logger.info(f"[ChatService] Initialized for user_id={self.user_id}")

    def create_chat(self, data: Optional[ChatCreate] = None) -> Chat:
        """Create a new chat for the current user."""
        logger.info(f"[ChatService] Creating new chat for user_id={self.user_id}")
        payload = data.model_dump() if data else {}
        new_chat = Chat(user_id=self.user_id, **payload)
        self.db.add(new_chat)
        self.db.commit()
        self.db.refresh(new_chat)
        return new_chat

    def get_chat(self, chat_id: int) -> Optional[Chat]:
        """Retrieve a specific chat by ID, ensuring it belongs to the current user."""
        logger.info(f"[ChatService] Retrieving chat_id={chat_id} for user_id={self.user_id}")
        return (
            self.db.query(Chat)
            .filter(Chat.id == chat_id, Chat.user_id == self.user_id)
            .first()
        )

    def get_all(self, limit: int = 50) -> List[Chat]:
        """Get a list of all chats for the current user, ordered by creation date."""
        logger.info(f"[ChatService] Getting all chats for user_id={self.user_id} (limit={limit})")
        return (
            self.db.query(Chat)
            .filter(Chat.user_id == self.user_id)
            .order_by(Chat.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete_chat(self, chat_id: int) -> bool:
        """Delete a chat by ID if it belongs to the current user."""
        logger.warning(f"[ChatService] Deleting chat_id={chat_id} for user_id={self.user_id}")
        chat = self.get_chat(chat_id)
        if not chat:
            logger.error(f"[ChatService] Chat not found for id={chat_id}")
            return False
        self.db.delete(chat)
        self.db.commit()
        return True

    def get_or_create_chat(self) -> int:
        """
        Return the most recent chat for the user, or create a new one if none exists.
        Used in WebSocket sessions to maintain continuity.
        """
        logger.info(f"[ChatService] Checking for existing chats for user_id={self.user_id}")
        existing = (
            self.db.query(Chat)
            .filter(Chat.user_id == self.user_id)
            .order_by(Chat.created_at.desc())
            .first()
        )
        if existing:
            logger.info(f"[ChatService] Reusing existing chat_id={existing.id}")
            return existing.id

        logger.info(f"[ChatService] No existing chat found, creating new chat")
        return self.create_chat().id

    def check_token_limit(self):
        """Check if the user has exceeded their daily token usage limit based on their plan."""
        user = self.factory.user

        if not user.plan or user.plan.daily_token_limit is None:
            logger.warning(f"[ChatService] No plan or token limit configured for user_id={user.id}")
            return  # No limitation applied

        today = ddatetime.now(timezone.utc).date()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        total_tokens_today = (
            self.db.query(func.sum(TokenUsage.tokens_used))
            .filter(
                TokenUsage.user_id == self.user_id,
                TokenUsage.created_at >= start_of_day,
                TokenUsage.created_at <= end_of_day,
            )
            .scalar()
        ) or 0

        logger.info(f"[ChatService] user_id={self.user_id} has used {total_tokens_today} tokens today")

        if total_tokens_today >= user.plan.daily_token_limit:
            logger.error(
                f"[ChatService] Daily token limit reached: {total_tokens_today}/{user.plan.daily_token_limit}"
            )
            raise HTTPException(
                status_code=429,
                detail="You have reached your daily token limit"
            )
