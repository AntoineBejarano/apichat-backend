"""
Message Handler Module
─────────────────────
Maneja el almacenamiento y recuperación de mensajes del chat.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class MessageHandler:
    """
    Maneja el almacenamiento y recuperación de mensajes del chat.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.history_service = factory.get_chat_history_service()
        self.usage_service = factory.get_usage_service()
    
    async def store_user_message(
        self,
        chat_id: UUID,
        message: Any,
        session: Optional[Any] = None
    ) -> None:
        """
        Almacena el mensaje del usuario.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            session: Sesión de base de datos opcional
        """
        logger.info(f"[MessageHandler] 💾 Almacenando mensaje del usuario en chat {chat_id}")
        
        try:
            if session:
                # Usar sesión existente
                await self._store_user_message_with_session(chat_id, message, session)
            else:
                # Crear nueva sesión
                await self._store_user_message_async(chat_id, message)
            
            logger.info("[MessageHandler] ✅ Mensaje del usuario almacenado exitosamente")
            
        except Exception as e:
            logger.error(f"[MessageHandler] ❌ Error almacenando mensaje del usuario: {e}")
            raise
    
    async def save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int] = None,
        executed_strategy_id: Optional[UUID] = None,
        session: Optional[Any] = None
    ) -> None:
        """
        Guarda la respuesta del asistente.
        
        Args:
            chat_id: ID del chat
            content: Contenido de la respuesta
            token_count: Número de tokens utilizados
            executed_strategy_id: ID de la estrategia ejecutada
            session: Sesión de base de datos opcional
        """
        logger.info(f"[MessageHandler] 💾 Guardando respuesta del asistente en chat {chat_id}")
        
        try:
            if session:
                # Usar sesión existente
                await self._save_assistant_message_with_session(
                    chat_id, content, token_count, executed_strategy_id, session
                )
            else:
                # Crear nueva sesión
                await self._save_assistant_message_async(
                    chat_id, content, token_count, executed_strategy_id
                )
            
            logger.info("[MessageHandler] ✅ Respuesta del asistente guardada exitosamente")
            
        except Exception as e:
            logger.error(f"[MessageHandler] ❌ Error guardando respuesta del asistente: {e}")
            raise
    
    async def load_chat_history(
        self,
        chat_id: UUID,
        session: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Carga el historial del chat.
        
        Args:
            chat_id: ID del chat
            session: Sesión de base de datos opcional
            
        Returns:
            Lista de mensajes del historial
        """
        logger.info(f"[MessageHandler] 📚 Cargando historial del chat {chat_id}")
        
        try:
            if session:
                # Usar sesión existente
                history = await self._load_history_with_session(chat_id, session)
            else:
                # Crear nueva sesión
                history = await self._load_history_async(chat_id)
            
            logger.info(f"[MessageHandler] ✅ Historial cargado: {len(history)} mensajes")
            return history
            
        except Exception as e:
            logger.error(f"[MessageHandler] ❌ Error cargando historial: {e}")
            return []
    
    async def check_usage_limit(self, session: Optional[Any] = None) -> None:
        """
        Verifica el límite de uso del usuario.
        
        Args:
            session: Sesión de base de datos opcional
        """
        logger.info("[MessageHandler] 🔍 Verificando límite de uso")
        
        try:
            if session:
                # Usar sesión existente
                await self._check_usage_limit_with_session(session)
            else:
                # Crear nueva sesión
                await self._check_usage_limit_async()
            
            logger.info("[MessageHandler] ✅ Límite de uso verificado")
            
        except Exception as e:
            logger.error(f"[MessageHandler] ❌ Error verificando límite de uso: {e}")
            raise
    
    async def _store_user_message_async(self, chat_id: UUID, message: Any) -> None:
        """Almacena mensaje del usuario con nueva sesión."""
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Convertir mensaje a formato compatible
            if hasattr(message, 'model_dump'):
                message_data = message.model_dump()
            else:
                message_data = message
            
            # Crear entrada de historial
            history_entry = {
                "chat_id": str(chat_id),
                "user_id": str(self.factory.user.id),
                "role": "user",
                "content": message_data.get("content", str(message_data)),
                "timestamp": message_data.get("timestamp")
            }
            
            # Guardar en base de datos
            await self.history_service.create_chat_history(history_entry)
            
        finally:
            db.close()
    
    async def _save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int] = None,
        executed_strategy_id: Optional[UUID] = None
    ) -> None:
        """Guarda respuesta del asistente con nueva sesión."""
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Crear entrada de historial
            history_entry = {
                "chat_id": str(chat_id),
                "user_id": str(self.factory.user.id),
                "role": "assistant",
                "content": content,
                "token_count": token_count,
                "executed_strategy_id": str(executed_strategy_id) if executed_strategy_id else None
            }
            
            # Guardar en base de datos
            await self.history_service.create_chat_history(history_entry)
            
        finally:
            db.close()
    
    async def _load_history_async(self, chat_id: UUID) -> List[Any]:
        """Carga historial con nueva sesión."""
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Obtener historial del servicio
            history = await self.history_service.get_chat_history_by_chat_id(str(chat_id))
            
            # Convertir a formato compatible
            formatted_history = []
            for entry in history:
                formatted_entry = {
                    "role": entry.role,
                    "content": entry.content,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None
                }
                formatted_history.append(formatted_entry)
            
            return formatted_history
            
        finally:
            db.close()
    
    async def _check_usage_limit_async(self) -> None:
        """Verifica límite de uso con nueva sesión."""
        from app.core.database import SessionLocal
        
        db = SessionLocal()
        try:
            # Verificar límite de uso
            await self.usage_service.check_usage_limit()
            
        finally:
            db.close()
    
    async def _store_user_message_with_session(
        self,
        chat_id: UUID,
        message: Any,
        session: Any
    ) -> None:
        """Almacena mensaje del usuario con sesión existente."""
        # Convertir mensaje a formato compatible
        if hasattr(message, 'model_dump'):
            message_data = message.model_dump()
        else:
            message_data = message
        
        # Crear entrada de historial
        history_entry = {
            "chat_id": str(chat_id),
            "user_id": str(self.factory.user.id),
            "role": "user",
            "content": message_data.get("content", str(message_data)),
            "timestamp": message_data.get("timestamp")
        }
        
        # Guardar en base de datos usando la sesión existente
        await self.history_service.create_chat_history(history_entry)
    
    async def _save_assistant_message_with_session(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int] = None,
        executed_strategy_id: Optional[UUID] = None,
        session: Any = None
    ) -> None:
        """Guarda respuesta del asistente con sesión existente."""
        # Crear entrada de historial
        history_entry = {
            "chat_id": str(chat_id),
            "user_id": str(self.factory.user.id),
            "role": "assistant",
            "content": content,
            "token_count": token_count,
            "executed_strategy_id": str(executed_strategy_id) if executed_strategy_id else None
        }
        
        # Guardar en base de datos usando la sesión existente
        await self.history_service.create_chat_history(history_entry)
    
    async def _load_history_with_session(
        self,
        chat_id: UUID,
        session: Any
    ) -> List[Any]:
        """Carga historial con sesión existente."""
        # Obtener historial del servicio
        history = await self.history_service.get_chat_history_by_chat_id(str(chat_id))
        
        # Convertir a formato compatible
        formatted_history = []
        for entry in history:
            formatted_entry = {
                "role": entry.role,
                "content": entry.content,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None
            }
            formatted_history.append(formatted_entry)
        
        return formatted_history
    
    async def _check_usage_limit_with_session(self, session: Any) -> None:
        """Verifica límite de uso con sesión existente."""
        # Verificar límite de uso
        await self.usage_service.check_usage_limit()
