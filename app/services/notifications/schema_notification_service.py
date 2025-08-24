#!/usr/bin/env python3
"""
SchemaNotificationService - Servicio de notificaciones en tiempo real para schemas
────────────────────────────────────────────────────────────────────────────────
Implementa:
- Notificaciones WebSocket para cambios de estado de schema
- Progress tracking en tiempo real
- Notificaciones push para eventos importantes
- Gestión de suscripciones por usuario
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum

from app.utils.logger import logger
from app.services.common.ws_emitter import WSEmitter


class NotificationType(Enum):
    """Tipos de notificaciones disponibles"""
    SCHEMA_GENERATION_STARTED = "schema_generation_started"
    SCHEMA_GENERATION_PROGRESS = "schema_generation_progress"
    SCHEMA_GENERATION_COMPLETED = "schema_generation_completed"
    SCHEMA_GENERATION_FAILED = "schema_generation_failed"
    SCHEMA_REFRESH_STARTED = "schema_refresh_started"
    SCHEMA_REFRESH_COMPLETED = "schema_refresh_completed"
    SCHEMA_REFRESH_FAILED = "schema_refresh_failed"
    SCHEMA_CHANGES_DETECTED = "schema_changes_detected"
    SCHEMA_CACHE_INVALIDATED = "schema_cache_invalidated"
    DATABASE_STATUS_CHANGED = "database_status_changed"


class NotificationPriority(Enum):
    """Prioridades de notificaciones"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SchemaNotificationService:
    """
    Servicio de notificaciones en tiempo real para schemas de bases de datos.
    
    Características:
    - Notificaciones WebSocket en tiempo real
    - Progress tracking granular
    - Gestión de suscripciones por usuario
    - Notificaciones push para eventos críticos
    - Rate limiting para evitar spam
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # WebSocket emitter para notificaciones
        self.ws_emitter = WSEmitter()
        
        # Suscripciones activas por usuario
        self._user_subscriptions: Dict[UUID, Set[str]] = {}
        
        # Rate limiting para notificaciones
        self._notification_cooldowns: Dict[str, float] = {}
        self._cooldown_duration = 1.0  # 1 segundo entre notificaciones del mismo tipo
        
        # Configuración de notificaciones
        self.notification_config = {
            'enable_push_notifications': True,
            'enable_email_notifications': False,
            'max_notifications_per_minute': 60,
            'notification_retention_days': 7
        }
    
    async def notify_schema_generation_started(self, user_id: UUID, db_id: UUID, db_name: str) -> None:
        """
        Notifica que ha comenzado la generación de schema.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            db_name: Nombre de la base de datos
        """
        notification = {
            'type': NotificationType.SCHEMA_GENERATION_STARTED.value,
            'priority': NotificationPriority.HIGH.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': f"🔄 Preparando tu base de datos '{db_name}'...",
                'progress': 0,
                'estimated_time': '2-5 minutos'
            }
        }
        
        await self._send_notification(user_id, notification)
        self.logger.info(f"[SchemaNotificationService] ✅ Notificación enviada: Generación iniciada para DB {db_id}")
    
    async def notify_schema_generation_progress(self, user_id: UUID, db_id: UUID, 
                                             progress: int, stage: str, message: str) -> None:
        """
        Notifica progreso en la generación de schema.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            progress: Porcentaje de progreso (0-100)
            stage: Etapa actual del proceso
            message: Mensaje descriptivo
        """
        notification = {
            'type': NotificationType.SCHEMA_GENERATION_PROGRESS.value,
            'priority': NotificationPriority.NORMAL.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'progress': progress,
                'stage': stage,
                'message': message,
                'estimated_remaining': self._estimate_remaining_time(progress)
            }
        }
        
        await self._send_notification(user_id, notification)
        self.logger.debug(f"[SchemaNotificationService] 📊 Progreso {progress}% para DB {db_id}: {stage}")
    
    async def notify_schema_generation_completed(self, user_id: UUID, db_id: UUID, 
                                              db_name: str, execution_time: float) -> None:
        """
        Notifica que la generación de schema se ha completado.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            db_name: Nombre de la base de datos
            execution_time: Tiempo de ejecución en segundos
        """
        notification = {
            'type': NotificationType.SCHEMA_GENERATION_COMPLETED.value,
            'priority': NotificationPriority.HIGH.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': f"✅ Tu base de datos '{db_name}' está lista para usar",
                'progress': 100,
                'execution_time': f"{execution_time:.1f}s",
                'next_steps': "Ya puedes hacer preguntas sobre tu base de datos"
            }
        }
        
        await self._send_notification(user_id, notification)
        self.logger.info(f"[SchemaNotificationService] 🎉 Schema completado para DB {db_id} en {execution_time:.1f}s")
    
    async def notify_schema_generation_failed(self, user_id: UUID, db_id: UUID, 
                                           db_name: str, error: str, retry_count: int = 0) -> None:
        """
        Notifica que la generación de schema ha fallado.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            db_name: Nombre de la base de datos
            error: Mensaje de error
            retry_count: Número de intentos realizados
        """
        # Determinar mensaje según intentos
        if retry_count >= 3:
            message = f"❌ Error preparando '{db_name}'. Por favor, bórrala y añádela de nuevo."
            priority = NotificationPriority.URGENT
        else:
            message = f"⚠️ Error preparando '{db_name}'. Reintentando... (intento {retry_count + 1}/3)"
            priority = NotificationPriority.HIGH
        
        notification = {
            'type': NotificationType.SCHEMA_GENERATION_FAILED.value,
            'priority': priority.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': message,
                'error': error,
                'retry_count': retry_count,
                'max_retries': 3,
                'action_required': retry_count >= 3
            }
        }
        
        await self._send_notification(user_id, notification)
        self.logger.error(f"[SchemaNotificationService] ❌ Fallo en generación de schema para DB {db_id}: {error}")
    
    async def notify_schema_refresh_started(self, user_id: UUID, db_id: UUID, db_name: str) -> None:
        """Notifica que ha comenzado el refresh de schema"""
        notification = {
            'type': NotificationType.SCHEMA_REFRESH_STARTED.value,
            'priority': NotificationPriority.NORMAL.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': f"🔄 Actualizando esquema de '{db_name}'...",
                'progress': 0
            }
        }
        
        await self._send_notification(user_id, notification)
    
    async def notify_schema_refresh_completed(self, user_id: UUID, db_id: UUID, 
                                           db_name: str, changes_detected: bool) -> None:
        """Notifica que el refresh de schema se ha completado"""
        if changes_detected:
            message = f"✅ Esquema de '{db_name}' actualizado con cambios detectados"
        else:
            message = f"✅ Esquema de '{db_name}' actualizado (sin cambios)"
        
        notification = {
            'type': NotificationType.SCHEMA_REFRESH_COMPLETED.value,
            'priority': NotificationPriority.NORMAL.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': message,
                'changes_detected': changes_detected
            }
        }
        
        await self._send_notification(user_id, notification)
    
    async def notify_schema_refresh_failed(self, user_id: UUID, db_id: UUID, 
                                        db_name: str, error: str) -> None:
        """Notifica que el refresh de schema ha fallado"""
        notification = {
            'type': NotificationType.SCHEMA_REFRESH_FAILED.value,
            'priority': NotificationPriority.HIGH.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': f"❌ Error actualizando esquema de '{db_name}'",
                'error': error,
                'suggestion': "Puedes intentar refrescar manualmente más tarde"
            }
        }
        
        await self._send_notification(user_id, notification)
    
    async def notify_schema_changes_detected(self, user_id: UUID, db_id: UUID, 
                                          db_name: str, changes_summary: str) -> None:
        """Notifica que se han detectado cambios en el schema"""
        notification = {
            'type': NotificationType.SCHEMA_CHANGES_DETECTED.value,
            'priority': NotificationPriority.HIGH.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'message': f"🔄 Cambios detectados en '{db_name}': {changes_summary}",
                'changes_summary': changes_summary,
                'action': "El esquema se actualizará automáticamente"
            }
        }
        
        await self._send_notification(user_id, notification)
    
    async def notify_database_status_changed(self, user_id: UUID, db_id: UUID, 
                                          db_name: str, old_status: str, new_status: str) -> None:
        """Notifica cambios en el estado de la base de datos"""
        status_messages = {
            'pending': '⏳ Pendiente de preparación',
            'generating': '🔄 Preparando base de datos',
            'ready': '✅ Lista para usar',
            'error': '❌ Error en la preparación',
            'updating': '🔄 Actualizando esquema'
        }
        
        notification = {
            'type': NotificationType.DATABASE_STATUS_CHANGED.value,
            'priority': NotificationPriority.NORMAL.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'user_id': str(user_id),
                'db_id': str(db_id),
                'db_name': db_name,
                'old_status': old_status,
                'new_status': new_status,
                'message': f"Estado de '{db_name}': {status_messages.get(new_status, new_status)}",
                'status_description': status_messages.get(new_status, new_status)
            }
        }
        
        await self._send_notification(user_id, notification)
    
    async def _send_notification(self, user_id: UUID, notification: Dict[str, Any]) -> None:
        """
        Envía una notificación al usuario.
        
        Args:
            user_id: ID del usuario
            notification: Datos de la notificación
        """
        try:
            # Verificar rate limiting
            if self._is_rate_limited(notification['type'], user_id):
                self.logger.debug(f"[SchemaNotificationService] ⏳ Rate limited para {notification['type']}")
                return
            
            # Enviar por WebSocket
            await self.ws_emitter.emit_to_user(
                user_id=str(user_id),
                event="schema_notification",
                data=notification
            )
            
            # Guardar en historial de notificaciones (opcional)
            await self._save_notification_history(user_id, notification)
            
            # Actualizar cooldown
            self._update_cooldown(notification['type'], user_id)
            
        except Exception as e:
            self.logger.error(f"[SchemaNotificationService] ❌ Error enviando notificación: {e}")
    
    def _is_rate_limited(self, notification_type: str, user_id: UUID) -> bool:
        """Verifica si una notificación está rate limited"""
        cooldown_key = f"{notification_type}_{user_id}"
        last_sent = self._notification_cooldowns.get(cooldown_key, 0)
        current_time = asyncio.get_event_loop().time()
        
        return (current_time - last_sent) < self._cooldown_duration
    
    def _update_cooldown(self, notification_type: str, user_id: UUID) -> None:
        """Actualiza el cooldown de una notificación"""
        cooldown_key = f"{notification_type}_{user_id}"
        self._notification_cooldowns[cooldown_key] = asyncio.get_event_loop().time()
    
    def _estimate_remaining_time(self, progress: int) -> str:
        """Estima el tiempo restante basado en el progreso"""
        if progress < 20:
            return "4-5 minutos"
        elif progress < 40:
            return "3-4 minutos"
        elif progress < 60:
            return "2-3 minutos"
        elif progress < 80:
            return "1-2 minutos"
        else:
            return "Menos de 1 minuto"
    
    async def _save_notification_history(self, user_id: UUID, notification: Dict[str, Any]) -> None:
        """Guarda la notificación en el historial (implementación futura)"""
        # TODO: Implementar guardado en BD para historial de notificaciones
        pass
    
    def subscribe_user(self, user_id: UUID, notification_types: List[str] = None) -> None:
        """
        Suscribe un usuario a tipos específicos de notificaciones.
        
        Args:
            user_id: ID del usuario
            notification_types: Lista de tipos de notificación (None = todos)
        """
        if notification_types is None:
            notification_types = [nt.value for nt in NotificationType]
        
        if user_id not in self._user_subscriptions:
            self._user_subscriptions[user_id] = set()
        
        self._user_subscriptions[user_id].update(notification_types)
        self.logger.info(f"[SchemaNotificationService] ✅ Usuario {user_id} suscrito a {len(notification_types)} tipos")
    
    def unsubscribe_user(self, user_id: UUID, notification_types: List[str] = None) -> None:
        """
        Desuscribe un usuario de tipos específicos de notificaciones.
        
        Args:
            user_id: ID del usuario
            notification_types: Lista de tipos de notificación (None = todos)
        """
        if user_id not in self._user_subscriptions:
            return
        
        if notification_types is None:
            del self._user_subscriptions[user_id]
        else:
            self._user_subscriptions[user_id].difference_update(notification_types)
            
            if not self._user_subscriptions[user_id]:
                del self._user_subscriptions[user_id]
        
        self.logger.info(f"[SchemaNotificationService] ✅ Usuario {user_id} desuscrito")
    
    def get_user_subscriptions(self, user_id: UUID) -> Set[str]:
        """Obtiene las suscripciones activas de un usuario"""
        return self._user_subscriptions.get(user_id, set())
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del servicio de notificaciones"""
        return {
            'total_subscribed_users': len(self._user_subscriptions),
            'notification_types': len(NotificationType),
            'rate_limiting_enabled': True,
            'cooldown_duration': self._cooldown_duration,
            'active_cooldowns': len(self._notification_cooldowns)
        }
    
    async def broadcast_system_notification(self, message: str, priority: NotificationPriority = NotificationPriority.NORMAL) -> None:
        """
        Envía una notificación del sistema a todos los usuarios suscritos.
        
        Args:
            message: Mensaje de la notificación
            priority: Prioridad de la notificación
        """
        notification = {
            'type': 'system_notification',
            'priority': priority.value,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': {
                'message': message,
                'source': 'system'
            }
        }
        
        # Enviar a todos los usuarios suscritos
        for user_id in self._user_subscriptions.keys():
            try:
                await self.ws_emitter.emit_to_user(
                    user_id=str(user_id),
                    event="system_notification",
                    data=notification
                )
            except Exception as e:
                self.logger.warning(f"[SchemaNotificationService] ⚠️ Error enviando notificación del sistema a {user_id}: {e}")
        
        self.logger.info(f"[SchemaNotificationService] 📢 Notificación del sistema enviada a {len(self._user_subscriptions)} usuarios")


# Instancia global del servicio de notificaciones
schema_notification_service = None


def get_schema_notification_service(factory) -> SchemaNotificationService:
    """Obtiene la instancia global del servicio de notificaciones"""
    global schema_notification_service
    if schema_notification_service is None:
        schema_notification_service = SchemaNotificationService(factory)
    return schema_notification_service
