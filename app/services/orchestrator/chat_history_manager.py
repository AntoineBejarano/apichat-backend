"""
ChatHistoryManager - Manejo de Historial de Chat
───────────────────────────────────────────────
Módulo especializado para:
- Carga de historial de chat
- Almacenamiento de mensajes
- Optimización de historial
- Gestión de sesiones
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context
from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class ChatHistoryManager:
    """Maneja todas las operaciones relacionadas con historial de chat"""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.chat_history_service = factory.get_chat_history_service()
        self.chat_service = factory.get_chat_service()
    
    @monitor_performance("load_history")
    @profile_function("load_history")
    async def load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Carga historial de chat de forma asíncrona"""
        try:
            with performance_context("chat_history_loading"):
                # 🔒 CONTROL DE TOKENS - Cargar historial optimizado
                history = await self._load_optimized_history(chat_id)
                
                if not history:
                    logger.info(f"No se encontró historial para chat {chat_id}")
                    return []
                
                # Aplicar trimming inteligente
                optimized_history = self._apply_intelligent_history_trimming(history)
                
                logger.info(f"Historial cargado para chat {chat_id}: {len(optimized_history)} mensajes")
                return optimized_history
                
        except Exception as e:
            logger.error(f"Error cargando historial para chat {chat_id}: {e}")
            return []
    
    async def _load_optimized_history(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Carga historial con optimizaciones"""
        try:
            # Cargar historial desde el servicio
            history = await self.chat_history_service.get_chat_history(chat_id)
            
            if not history:
                return []
            
            # Convertir a formato optimizado
            optimized_history = []
            for msg in history:
                optimized_msg = self._optimize_message_for_context(msg)
                if optimized_msg:
                    optimized_history.append(optimized_msg)
            
            return optimized_history
            
        except Exception as e:
            logger.error(f"Error en _load_optimized_history: {e}")
            return []
    
    def _optimize_message_for_context(self, message: Any) -> Optional[Dict[str, Any]]:
        """Optimiza un mensaje para el contexto"""
        try:
            if not message:
                return None
            
            # Extraer información esencial
            optimized_msg = {
                "role": getattr(message, 'role', 'unknown'),
                "content": getattr(message, 'content', ''),
                "timestamp": getattr(message, 'created_at', datetime.now(timezone.utc)),
                "message_type": getattr(message, 'message_type', 'text')
            }
            
            # 🔒 CONTROL DE TOKENS - Limitar contenido largo
            max_content_length = 500
            if len(optimized_msg["content"]) > max_content_length:
                optimized_msg["content"] = optimized_msg["content"][:max_content_length] + "..."
                optimized_msg["truncated"] = True
            
            return optimized_msg
            
        except Exception as e:
            logger.error(f"Error optimizando mensaje: {e}")
            return None
    
    def _apply_intelligent_history_trimming(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aplica trimming inteligente al historial"""
        try:
            if not history:
                return []
            
            # 🔒 CONTROL DE TOKENS - Límites de trimming
            max_history_turns = 6
            max_history_chars = 5000
            
            # Si el historial es corto, no hacer trimming
            if len(history) <= max_history_turns:
                return history
            
            # Aplicar trimming por número de turnos
            trimmed_history = history[-max_history_turns:]
            
            # Verificar límite de caracteres
            total_chars = sum(len(msg.get("content", "")) for msg in trimmed_history)
            if total_chars <= max_history_chars:
                return trimmed_history
            
            # Aplicar trimming por caracteres
            final_history = []
            current_chars = 0
            
            for msg in reversed(trimmed_history):
                msg_content = msg.get("content", "")
                if current_chars + len(msg_content) <= max_history_chars:
                    final_history.insert(0, msg)
                    current_chars += len(msg_content)
                else:
                    break
            
            logger.info(f"Historial optimizado: {len(history)} -> {len(final_history)} mensajes")
            return final_history
            
        except Exception as e:
            logger.error(f"Error en trimming inteligente: {e}")
            return history
    
    @monitor_performance("store_user_message")
    @profile_function("store_user_message")
    async def store_user_message_async(self, chat_id: UUID, message: ChatMessage):
        """Almacena mensaje del usuario de forma asíncrona"""
        try:
            with performance_context("store_user_message"):
                # Crear entrada de historial
                history_entry = ChatHistoryCreate(
                    chat_id=chat_id,
                    role="user",
                    content=message.content,
                    message_type="text",
                    user_id=self.user_id
                )
                
                # Guardar en base de datos
                await self.chat_history_service.create_chat_history(history_entry)
                
                logger.info(f"Mensaje de usuario almacenado para chat {chat_id}")
                
        except Exception as e:
            logger.error(f"Error almacenando mensaje de usuario: {e}")
            raise
    
    @monitor_performance("save_assistant_message")
    @profile_function("save_assistant_message")
    async def save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ):
        """Guarda mensaje del asistente de forma asíncrona"""
        try:
            # 🔧 FASE 1: Usar solo un timer para evitar duplicación
            # with performance_context("save_assistant_message"):  # Removido para evitar duplicación
            
            # Crear entrada de historial
            history_entry = ChatHistoryCreate(
                chat_id=chat_id,
                role="assistant",
                content=content,
                message_type="text",
                user_id=self.user_id,
                metadata={
                    "token_count": token_count,
                    "executed_strategy_id": str(executed_strategy_id) if executed_strategy_id else None
                }
            )
            
            # Guardar en base de datos
            await self.chat_history_service.create_chat_history(history_entry)
            
            logger.info(f"Mensaje del asistente guardado para chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error guardando mensaje del asistente: {e}")
            raise
    
    def _store_user_message_with_session(self, chat_id: UUID, message: ChatMessage) -> None:
        """Almacena mensaje del usuario usando sesión específica"""
        try:
            # Crear nueva sesión para evitar conflictos
            with SessionLocal() as session:
                try:
                    # Crear entrada de historial
                    history_entry = ChatHistoryCreate(
                        chat_id=chat_id,
                        role="user",
                        content=message.content,
                        message_type="text",
                        user_id=self.user_id
                    )
                    
                    # Guardar usando la sesión
                    self.chat_history_service.create_chat_history_with_session(
                        history_entry, session
                    )
                    
                    session.commit()
                    logger.info(f"Mensaje de usuario almacenado con sesión para chat {chat_id}")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error en sesión al almacenar mensaje: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error almacenando mensaje con sesión: {e}")
            raise
    
    def _save_assistant_message_with_session(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        """Guarda mensaje del asistente usando sesión específica"""
        try:
            # Crear nueva sesión para evitar conflictos
            with SessionLocal() as session:
                try:
                    # Crear entrada de historial
                    history_entry = ChatHistoryCreate(
                        chat_id=chat_id,
                        role="assistant",
                        content=content,
                        message_type="text",
                        user_id=self.user_id,
                        metadata={
                            "token_count": token_count,
                            "executed_strategy_id": str(executed_strategy_id) if executed_strategy_id else None
                        }
                    )
                    
                    # Guardar usando la sesión
                    self.chat_history_service.create_chat_history_with_session(
                        history_entry, session
                    )
                    
                    session.commit()
                    logger.info(f"Mensaje del asistente guardado con sesión para chat {chat_id}")
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error en sesión al guardar mensaje: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"Error guardando mensaje con sesión: {e}")
            raise
    
    def _load_history_with_session(self, chat_id: UUID) -> List[Any]:
        """Carga historial usando sesión específica"""
        try:
            with SessionLocal() as session:
                try:
                    # Cargar historial usando la sesión
                    history = self.chat_history_service.get_chat_history_with_session(
                        chat_id, session
                    )
                    
                    return history or []
                    
                except Exception as e:
                    logger.error(f"Error en sesión al cargar historial: {e}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error cargando historial con sesión: {e}")
            return []
    
    def estimate_history_tokens(self, history: List[Dict[str, Any]]) -> int:
        """Estima el número de tokens del historial"""
        try:
            if not history:
                return 0
            
            total_tokens = 0
            for msg in history:
                content = msg.get("content", "")
                # Estimación simple: 1 token ≈ 4 caracteres
                estimated_tokens = len(content) // 4
                total_tokens += estimated_tokens
            
            return total_tokens
            
        except Exception as e:
            logger.error(f"Error estimando tokens del historial: {e}")
            return 0
    
    def get_conversation_summary(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Genera un resumen de la conversación"""
        try:
            if not history:
                return {"summary": "No hay conversación", "turn_count": 0}
            
            # Contar turnos por rol
            user_turns = len([msg for msg in history if msg.get("role") == "user"])
            assistant_turns = len([msg for msg in history if msg.get("role") == "assistant"])
            
            # Obtener último mensaje
            last_message = history[-1] if history else None
            last_role = last_message.get("role") if last_message else "none"
            
            summary = {
                "total_turns": len(history),
                "user_turns": user_turns,
                "assistant_turns": assistant_turns,
                "last_role": last_role,
                "estimated_tokens": self.estimate_history_tokens(history),
                "conversation_active": last_role == "user"  # Si el último es usuario, está esperando respuesta
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generando resumen de conversación: {e}")
            return {"summary": "Error generando resumen", "turn_count": 0}
