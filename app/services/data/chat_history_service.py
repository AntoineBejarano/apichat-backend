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
import hashlib
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

from app.models.chat_history_model import ChatHistory
from app.schemas.chat_history_schema import ChatHistoryCreate
from app.schemas.chat_schema import ChatMessage

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
        self._history_cache = {}
        logger.info("[ChatHistoryService] Inicializado para user_id=%s", self.user_id)

    # ─────────────────────────────────────────────
    #   Utilidades de idempotencia
    # ─────────────────────────────────────────────
    def _generate_idempotency_key(self, chat_id: UUID, user_id: UUID, content: str, role: str) -> str:
        """
        Genera clave de idempotencia SHA256 para evitar mensajes duplicados.
        Formula: sha256(chat_id + user_id + content + role)
        """
        # Crear string determinístico para el hash
        key_data = f"{chat_id}:{user_id}:{content}:{role}"
        return hashlib.sha256(key_data.encode('utf-8')).hexdigest()
    
    # ─────────────────────────────────────────────
    #   Crear mensaje (CON IDEMPOTENCIA)
    # ─────────────────────────────────────────────
    def create_message(self, data: ChatHistoryCreate) -> ChatHistory:
        """
        Crea un nuevo mensaje con idempotencia para evitar duplicados en reintentos.
        Si ya existe un mensaje con la misma idempotency_key, devuelve el existente.
        """
        logger.info("[ChatHistoryService] Creando mensaje idempotente para user_id=%s", self.user_id)

        # 🔧 Generar clave de idempotencia
        idempotency_key = data.idempotency_key or self._generate_idempotency_key(
            chat_id=data.chat_id,
            user_id=self.user_id,
            content=data.content,
            role=data.role
        )
        
        # 🔍 Verificar si ya existe un mensaje con esta clave
        existing_msg = self.db.query(ChatHistory).filter(
            ChatHistory.idempotency_key == idempotency_key
        ).first()
        
        if existing_msg:
            logger.info(f"[ChatHistoryService] ♻️ Mensaje duplicado detectado - devolviendo existente (id={existing_msg.id})")
            return existing_msg

        # ✨ Crear nuevo mensaje
        try:
            msg = ChatHistory(
                user_id=self.user_id,
                chat_id=data.chat_id,
                role=data.role,
                content=data.content,
                name=data.name,
                token_count=data.token_count,
                is_function_call=data.is_function_call,
                function_call_id=data.function_call_id,
                executed_strategy_id=data.executed_strategy_id,
                idempotency_key=idempotency_key  # 🔧 Incluir clave de idempotencia
            )
            self.db.add(msg)
            self.db.commit()
            self.db.refresh(msg)
            
            # Invalidar cache después de crear mensaje
            self._invalidate_cache(data.chat_id)
            
            logger.info(f"[ChatHistoryService] ✅ Mensaje creado con idempotencia (id={msg.id}, key={idempotency_key[:16]}...)")
            return msg
            
        except IntegrityError as e:
            # 🔄 Race condition: otro proceso creó el mensaje entre nuestro check y insert
            self.db.rollback()
            logger.warning(f"[ChatHistoryService] 🔄 Race condition detectada - buscando mensaje existente")
            
            # Buscar el mensaje que fue creado por el otro proceso
            existing_msg = self.db.query(ChatHistory).filter(
                ChatHistory.idempotency_key == idempotency_key
            ).first()
            
            if existing_msg:
                logger.info(f"[ChatHistoryService] ♻️ Mensaje encontrado tras race condition (id={existing_msg.id})")
                return existing_msg
            else:
                # Si no encontramos el mensaje, re-lanzar la excepción original
                logger.error(f"[ChatHistoryService] ❌ IntegrityError sin mensaje duplicado: {e}")
                raise

    # ─────────────────────────────────────────────
    #   Obtener historial de un chat (OPTIMIZADO)
    # ─────────────────────────────────────────────
    def get_history(self, chat_id: UUID, limit: int = 50) -> List[ChatHistory]:
        logger.info(
            "[ChatHistoryService] Obteniendo historial chat_id=%s (limit=%d) para user_id=%s",
            chat_id, limit, self.user_id
        )
        
        # Intentar obtener desde cache
        cache_key = f"{chat_id}_{limit}"
        if cache_key in self._history_cache:
            logger.debug("[ChatHistoryService] Usando cache para historial")
            return self._history_cache[cache_key]
        
        limit = min(limit, 1000)
        
        # ⚡ OPTIMIZACIÓN: Query más eficiente con índices
        history = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.chat_id == chat_id,
                ChatHistory.user_id == self.user_id
            )
            .order_by(ChatHistory.timestamp.asc())
            .limit(limit)
            .all()
        )
        
        # Guardar en cache
        self._history_cache[cache_key] = history
        
        return history

    # ─────────────────────────────────────────────
    #   Obtener TODO el historial del usuario (OPTIMIZADO)
    # ─────────────────────────────────────────────
    def get_all(self, limit: int = 1000) -> List[ChatHistory]:
        logger.info("[ChatHistoryService] Obteniendo todo el historial (limit=%d) para user_id=%s",
                    limit, self.user_id)
        
        # Intentar obtener desde cache
        cache_key = f"all_{limit}"
        if cache_key in self._history_cache:
            logger.debug("[ChatHistoryService] Usando cache para historial completo")
            return self._history_cache[cache_key]
        
        limit = min(limit, 1000)
        
        # ⚡ OPTIMIZACIÓN: Query más eficiente
        history = (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id)
            .order_by(desc(ChatHistory.timestamp))  # Más reciente primero
            .limit(limit)
            .all()
        )
        
        # Guardar en cache
        self._history_cache[cache_key] = history
        
        return history

    # ─────────────────────────────────────────────
    #   Cache Management
    # ─────────────────────────────────────────────
    def _invalidate_cache(self, chat_id: UUID):
        """Invalidar cache para un chat específico"""
        keys_to_remove = [key for key in self._history_cache.keys() if str(chat_id) in key]
        for key in keys_to_remove:
            del self._history_cache[key]
        logger.debug("[ChatHistoryService] Cache invalidado para chat_id=%s", chat_id)

    def clear_cache(self):
        """Limpiar todo el cache"""
        self._history_cache.clear()
        logger.debug("[ChatHistoryService] Cache limpiado")

    # ─────────────────────────────────────────────
    #   Obtener historial de un chat específico
    # ─────────────────────────────────────────────
    def get_chat_history(self, chat_id: UUID) -> List[ChatHistory]:
        return self.get_history(chat_id)

    def store_user_message(self, chat_id: UUID, message: ChatMessage) -> bool:
        """
        Almacena un mensaje del usuario.
        Wrapper para compatibilidad con ContextLoader.
        """
        try:
            from app.schemas.chat_history_schema import ChatHistoryCreate
            
            # Crear objeto ChatHistoryCreate
            history_data = ChatHistoryCreate(
                chat_id=chat_id,
                role=message.role,
                content=message.content,
                name=getattr(message, 'name', None),
                token_count=getattr(message, 'token_count', None),
                is_function_call=getattr(message, 'is_function_call', False),
                function_call_id=getattr(message, 'function_call_id', None),
                executed_strategy_id=getattr(message, 'executed_strategy_id', None)
            )
            
            # Usar el método existente create_message
            self.create_message(history_data)
            logger.debug(f"[ChatHistoryService] Mensaje del usuario almacenado para chat {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"[ChatHistoryService] Error almacenando mensaje del usuario: {e}")
            return False

    # ─────────────────────────────────────────────
    #   Borrar historial de un chat
    # ─────────────────────────────────────────────
    def delete_chat_history(self, chat_id: UUID) -> bool:
        logger.info("[ChatHistoryService] Borrando historial chat_id=%s para user_id=%s",
                    chat_id, self.user_id)
        
        try:
            deleted_count = (
                self.db.query(ChatHistory)
                .filter(
                    ChatHistory.chat_id == chat_id,
                    ChatHistory.user_id == self.user_id
                )
                .delete()
            )
            self.db.commit()
            
            # Invalidar cache
            self._invalidate_cache(chat_id)
            
            logger.info("[ChatHistoryService] %d mensajes borrados del chat_id=%s", deleted_count, chat_id)
            return deleted_count > 0
        except Exception as e:
            logger.exception("[ChatHistoryService] Error borrando historial: %s", e)
            self.db.rollback()
            return False

    # ─────────────────────────────────────────────
    #   Último system prompt (OPTIMIZADO)
    # ─────────────────────────────────────────────
    def get_last_system_prompt(self, chat_id: Optional[UUID] = None) -> Optional[ChatHistory]:
        """
        Devuelve el último mensaje con role='system' para este usuario
        (y opcionalmente para un chat concreto). None si no hay.
        """
        # Intentar obtener desde cache
        cache_key = f"system_prompt_{chat_id or 'all'}"
        if cache_key in self._history_cache:
            logger.debug("[ChatHistoryService] Usando cache para system prompt")
            return self._history_cache[cache_key]
        
        query = (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.user_id == self.user_id,
                ChatHistory.role == "system"
            )
            .order_by(desc(ChatHistory.timestamp))
        )
        
        if chat_id:
            query = query.filter(ChatHistory.chat_id == chat_id)
        
        result = query.first()
        
        # Guardar en cache
        self._history_cache[cache_key] = result
        
        return result

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

    # ─────────────────────────────────────────────
    #   Métodos de utilidad
    # ─────────────────────────────────────────────
    def get_message_count(self, chat_id: UUID) -> int:
        """Obtener número de mensajes en un chat"""
        return (
            self.db.query(ChatHistory)
            .filter(
                ChatHistory.chat_id == chat_id,
                ChatHistory.user_id == self.user_id
            )
            .count()
        )

    def get_total_message_count(self) -> int:
        """Obtener número total de mensajes del usuario"""
        return (
            self.db.query(ChatHistory)
            .filter(ChatHistory.user_id == self.user_id)
            .count()
        )
