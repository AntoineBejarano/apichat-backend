#!/usr/bin/env python3
"""
NotificationRouter - Router para gestión de notificaciones de schema
───────────────────────────────────────────────────────────────────
Endpoints para:
- Suscribir/desuscribir usuarios a notificaciones
- Obtener estadísticas de notificaciones
- Gestionar preferencias de notificación
- Broadcast de notificaciones del sistema
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.core.service_factory import ServiceFactory
from app.core.database import get_db
from sqlalchemy.orm import Session
from app.services.notifications.schema_notification_service import get_schema_notification_service, NotificationType, NotificationPriority
from app.utils.logger import logger

router = APIRouter(
    prefix="/notifications",
    tags=["🔔 Notificaciones"],
    responses={
        400: {"description": "❌ Invalid request"},
        401: {"description": "❌ Unauthorized"},
        500: {"description": "❌ Internal server error"},
    },
)

# 🧩 Inyección del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post("/subscribe")
async def subscribe_to_notifications(
    notification_types: Optional[List[str]] = None,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Suscribe al usuario actual a tipos específicos de notificaciones.
    
    Args:
        notification_types: Lista de tipos de notificación (None = todos)
        
    Returns:
        Confirmación de suscripción
    """
    try:
        user_id = factory.user.id
        notification_service = get_schema_notification_service(factory)
        
        # Si no se especifican tipos, usar todos
        if notification_types is None:
            notification_types = [nt.value for nt in NotificationType]
        
        # Validar tipos de notificación
        valid_types = [nt.value for nt in NotificationType]
        invalid_types = [nt for nt in notification_types if nt not in valid_types]
        
        if invalid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipos de notificación inválidos: {invalid_types}"
            )
        
        # Suscribir usuario
        notification_service.subscribe_user(user_id, notification_types)
        
        logger.info(f"[NotificationRouter] ✅ Usuario {user_id} suscrito a {len(notification_types)} tipos")
        
        return {
            "success": True,
            "message": f"Subscribed to {len(notification_types)} notification types",
            "subscribed_types": notification_types,
            "user_id": str(user_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error suscribiendo usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during subscription"
        )


@router.post("/unsubscribe")
async def unsubscribe_from_notifications(
    notification_types: Optional[List[str]] = None,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Desuscribe al usuario actual de tipos específicos de notificaciones.
    
    Args:
        notification_types: Lista de tipos de notificación (None = todos)
        
    Returns:
        Confirmación de desuscripción
    """
    try:
        user_id = factory.user.id
        notification_service = get_schema_notification_service(factory)
        
        # Desuscribir usuario
        notification_service.unsubscribe_user(user_id, notification_types)
        
        action = "all notification types" if notification_types is None else f"{len(notification_types)} types"
        logger.info(f"[NotificationRouter] ✅ Usuario {user_id} desuscrito de {action}")
        
        return {
            "success": True,
            "message": f"Unsubscribed from {action}",
            "user_id": str(user_id)
        }
        
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error desuscribiendo usuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during unsubscription"
        )


@router.get("/subscriptions")
async def get_user_subscriptions(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene las suscripciones activas del usuario actual.
    
    Returns:
        Lista de tipos de notificación suscritos
    """
    try:
        user_id = factory.user.id
        notification_service = get_schema_notification_service(factory)
        
        subscriptions = notification_service.get_user_subscriptions(user_id)
        
        return {
            "user_id": str(user_id),
            "subscriptions": list(subscriptions),
            "total_subscribed": len(subscriptions),
            "available_types": [nt.value for nt in NotificationType]
        }
        
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error obteniendo suscripciones: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting subscriptions"
        )


@router.get("/stats")
async def get_notification_stats(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Obtiene estadísticas del servicio de notificaciones.
    
    Returns:
        Estadísticas del servicio
    """
    try:
        notification_service = get_schema_notification_service(factory)
        stats = notification_service.get_notification_stats()
        
        return {
            "service_stats": stats,
            "available_types": [nt.value for nt in NotificationType],
            "priorities": [np.value for np in NotificationPriority]
        }
        
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error getting stats"
        )


@router.post("/test")
async def send_test_notification(
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Envía una notificación de prueba al usuario actual.
    
    Returns:
        Confirmación de envío
    """
    try:
        user_id = factory.user.id
        notification_service = get_schema_notification_service(factory)
        
        # Enviar notificación de prueba
        await notification_service.notify_schema_generation_started(
            user_id=user_id,
            db_id=UUID('00000000-0000-0000-0000-000000000000'),  # UUID de prueba
            db_name="Test Database"
        )
        
        logger.info(f"[NotificationRouter] ✅ Notificación de prueba enviada a usuario {user_id}")
        
        return {
            "success": True,
            "message": "Test notification sent successfully",
            "user_id": str(user_id),
            "notification_type": "test"
        }
        
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error enviando notificación de prueba: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error sending test notification"
        )


@router.post("/system/broadcast")
async def broadcast_system_notification(
    message: str,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Envía una notificación del sistema a todos los usuarios suscritos.
    
    Args:
        message: Mensaje de la notificación
        priority: Prioridad de la notificación
        
    Returns:
        Confirmación de broadcast
    """
    try:
        # Verificar que el usuario sea admin (implementar lógica de permisos)
        # if not factory.user.is_admin:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Admin access required for system broadcasts"
        #     )
        
        notification_service = get_schema_notification_service(factory)
        
        # Enviar broadcast
        await notification_service.broadcast_system_notification(message, priority)
        
        logger.info(f"[NotificationRouter] 📢 Broadcast del sistema enviado por usuario {factory.user.id}")
        
        return {
            "success": True,
            "message": "System notification broadcasted successfully",
            "broadcast_message": message,
            "priority": priority.value,
            "sent_by": str(factory.user.id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[NotificationRouter] ❌ Error en broadcast del sistema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during system broadcast"
        )


@router.get("/types")
async def get_notification_types():
    """
    Obtiene todos los tipos de notificación disponibles.
    
    Returns:
        Lista de tipos de notificación con descripciones
    """
    notification_types = {
        "schema_generation_started": "Notificación cuando comienza la generación de schema",
        "schema_generation_progress": "Progreso en la generación de schema",
        "schema_generation_completed": "Schema generado exitosamente",
        "schema_generation_failed": "Error en la generación de schema",
        "schema_refresh_started": "Inicio de refresh de schema",
        "schema_refresh_completed": "Refresh de schema completado",
        "schema_refresh_failed": "Error en refresh de schema",
        "schema_changes_detected": "Cambios detectados en el schema",
        "schema_cache_invalidated": "Cache de schema invalidado",
        "database_status_changed": "Cambio en el estado de la base de datos"
    }
    
    return {
        "available_types": notification_types,
        "total_types": len(notification_types),
        "description": "Tipos de notificación disponibles para suscripción"
    }


@router.get("/priorities")
async def get_notification_priorities():
    """
    Obtiene todas las prioridades de notificación disponibles.
    
    Returns:
        Lista de prioridades con descripciones
    """
    priorities = {
        "low": "Notificación de baja prioridad",
        "normal": "Notificación estándar",
        "high": "Notificación de alta prioridad",
        "urgent": "Notificación urgente que requiere atención inmediata"
    }
    
    return {
        "available_priorities": priorities,
        "total_priorities": len(priorities),
        "description": "Niveles de prioridad para las notificaciones"
    }
