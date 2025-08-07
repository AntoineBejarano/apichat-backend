# app/services/chat_history_service.py
"""
ChatHistoryService
──────────────────
Servicio centralizado para gestionar el historial de chat de cada usuario.
Incluye helpers para:
  • crear y recuperar mensajes
  • paginar historial
  • borrar historial de un chat concreto
  • recuperar el último system-prompt (útil para agentes dinámicos)
Todos los accesos a BD usan SQLAlchemy ORM y emiten logs detallados.
"""
from __future__ import annotations

import logging
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chat_history_model import ChatHistory
from app.schemas.chat_history_schema import ChatHistoryCreate

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ChatHistoryService:
    # ─────────────────────────────────────────────
    #   Init
    # ─────────────────────────────────────────────
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: UUID = factory.user.id
        logger.info("[ChatHistoryService] Inicializado para user_id=%s", self.user_id)

    # ─────────────────────────────────────────────
    #   Crear mensaje
    # ─────────────────────────────────────────────
    def create_message(self, data: ChatHistoryCreate) -> ChatHistory:
        logger.info("[ChatHistoryService] Creando nuevo mensaje para user_id=%s", self.user_id)

        msg = ChatHistory(
            user_id=self.user_id,
            chat_id=data.chat_id,
            role=data.role,
            content=data.content,
            name=data.name,
            token_count=data.token_count,
            is_function_call=data.is_function_call,
            function_call_id=data.function_call_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    # ─────────────────────────────────────────────
    #   Obtener historial de un chat
    # ─────────────────────────────────────────────
    def get_history(self, chat_id: UUID, limit: int = 50) -> List[ChatHistory]:
        logger.info(
            "[ChatHistoryService] Obteniendo historial chat_id=%s (limit=%d) para user_id=%s",
            chat_id, limit, self.user_id
        )
        limit = min(limit, 1000)
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.chat_id == chat_id,
                    ChatHistory.user_id == self.user_id)
            .order_by(ChatHistory.timestamp.asc())
            .limit(limit)
            .all()
        )

    # ─────────────────────────────────────────────
    #   Obtener TODO el historial del usuario
    # ─────────────────────────────────────────────
    def get_all(self, limit: int = 1000) -> List[ChatHistory]:
        logger.info("[ChatHistoryService] Obteniendo todo el historial (limit=%d) para user_id=%s",
                    limit, self.user_id)
        limit = min(limit, 1000)
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id)
            .order_by(ChatHistory.timestamp.desc())
            .limit(limit)
            .all()
        )

    # ─────────────────────────────────────────────
    #   Eliminar historial de un chat
    # ─────────────────────────────────────────────
    def delete_all_for_chat(self, chat_id: UUID) -> int:
        logger.warning("[ChatHistoryService] Eliminando historial chat_id=%s para user_id=%s",
                       chat_id, self.user_id)
        deleted = (
            self.db.query(ChatHistory)
            .filter(ChatHistory.chat_id == chat_id,
                    ChatHistory.user_id == self.user_id)
            .delete()
        )
        self.db.commit()
        return deleted

    # ─────────────────────────────────────────────
    #   Append (dict helper)
    # ─────────────────────────────────────────────
    def append(self, data: dict) -> ChatHistory:
        required = ("chat_id", "role", "content")
        if not all(k in data for k in required):
            msg = f"Datos inválidos. Faltan campos requeridos: {required}"
            logger.error("[ChatHistoryService] %s", msg)
            raise ValueError(msg)

        return self.create_message(
            ChatHistoryCreate(
                chat_id=data["chat_id"],
                role=data["role"],
                content=data["content"],
                name=data.get("name"),
                token_count=data.get("token_count"),
                is_function_call=data.get("is_function_call", False),
                function_call_id=data.get("function_call_id"),
            )
        )

    # ─────────────────────────────────────────────
    #   Último system prompt
    # ─────────────────────────────────────────────
    def get_last_system_prompt(self, chat_id: Optional[UUID] = None) -> Optional[ChatHistory]:
        """
        Devuelve el último mensaje con role='system' para este usuario
        (y opcionalmente para un chat concreto). None si no hay.
        """
        query = (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id,
                    ChatHistory.role == "system")
            .order_by(ChatHistory.timestamp.desc())
        )
        if chat_id:
            query = query.filter(ChatHistory.chat_id == chat_id)
        return query.first()

    def get_prompt_from_history(self, chat_id: Optional[UUID] = None) -> str:
        """
        Devuelve el contenido del último system-prompt guardado.
        Cadena vacía si no existe o ante error.
        """
        try:
            last = self.get_last_system_prompt(chat_id)
            return last.content if last else ""
        except Exception as e:
            logger.warning("[ChatHistoryService] No se pudo obtener system prompt: %s", e)
            return ""
