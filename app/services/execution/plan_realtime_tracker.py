"""
PlanRealtimeTracker - Servicio para seguimiento en tiempo real de ejecución de planes.
Maneja WebSockets y notificaciones de progreso.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Set
from uuid import UUID
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

from app.services.execution.plan_execution_service import PlanExecutionService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Maneja las conexiones WebSocket activas."""
    
    def __init__(self):
        # Diccionario de conexiones por usuario
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
        # Diccionario de conexiones por ejecución
        self.execution_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: UUID, execution_id: Optional[str] = None):
        """Conecta un WebSocket a un usuario y opcionalmente a una ejecución."""
        await websocket.accept()
        
        # Agregar a conexiones del usuario
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        
        # Agregar a conexiones de ejecución si se especifica
        if execution_id:
            if execution_id not in self.execution_connections:
                self.execution_connections[execution_id] = set()
            self.execution_connections[execution_id].add(websocket)
        
        logger.info(f"[RealtimeTracker] 🔌 WebSocket conectado: usuario {user_id}, ejecución {execution_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: UUID, execution_id: Optional[str] = None):
        """Desconecta un WebSocket."""
        # Remover de conexiones del usuario
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        # Remover de conexiones de ejecución
        if execution_id and execution_id in self.execution_connections:
            self.execution_connections[execution_id].discard(websocket)
            if not self.execution_connections[execution_id]:
                del self.execution_connections[execution_id]
        
        logger.info(f"[RealtimeTracker] 🔌 WebSocket desconectado: usuario {user_id}, ejecución {execution_id}")
    
    async def send_to_user(self, user_id: UUID, message: Dict[str, Any]):
        """Envía un mensaje a todas las conexiones de un usuario."""
        if user_id in self.active_connections:
            disconnected = set()
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"[RealtimeTracker] ⚠️ Error enviando mensaje: {e}")
                    disconnected.add(websocket)
            
            # Limpiar conexiones desconectadas
            for websocket in disconnected:
                self.active_connections[user_id].discard(websocket)
    
    async def send_to_execution(self, execution_id: str, message: Dict[str, Any]):
        """Envía un mensaje a todas las conexiones de una ejecución."""
        if execution_id in self.execution_connections:
            disconnected = set()
            for websocket in self.execution_connections[execution_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"[RealtimeTracker] ⚠️ Error enviando mensaje: {e}")
                    disconnected.add(websocket)
            
            # Limpiar conexiones desconectadas
            for websocket in disconnected:
                self.execution_connections[execution_id].discard(websocket)


class PlanRealtimeTracker:
    """Servicio para seguimiento en tiempo real de ejecución de planes."""
    
    def __init__(self, factory=None):
        self.factory = factory
        self.connection_manager = ConnectionManager()
        self.execution_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Inicializa los servicios necesarios."""
        if self.factory:
            self.execution_service = PlanExecutionService(self.factory)
    
    async def handle_websocket_connection(
        self,
        websocket: WebSocket,
        user_id: UUID,
        execution_id: Optional[str] = None
    ):
        """
        Maneja una conexión WebSocket para seguimiento en tiempo real.
        
        Args:
            websocket: Conexión WebSocket
            user_id: ID del usuario
            execution_id: ID de ejecución específica (opcional)
        """
        await self.connection_manager.connect(websocket, user_id, execution_id)
        
        try:
            # Enviar estado inicial si hay una ejecución específica
            if execution_id:
                initial_status = await self.execution_service.get_execution_status(execution_id, user_id)
                if initial_status:
                    await websocket.send_text(json.dumps({
                        "type": "initial_status",
                        "data": initial_status
                    }))
            
            # Mantener conexión activa y escuchar mensajes
            while True:
                try:
                    # Esperar mensajes del cliente
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Procesar mensaje del cliente
                    await self._handle_client_message(websocket, user_id, message)
                    
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"[RealtimeTracker] ❌ Error procesando mensaje: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Error procesando mensaje: {str(e)}"
                    }))
        
        except WebSocketDisconnect:
            logger.info(f"[RealtimeTracker] 🔌 WebSocket desconectado: {user_id}")
        except Exception as e:
            logger.error(f"[RealtimeTracker] ❌ Error en conexión WebSocket: {e}")
        finally:
            self.connection_manager.disconnect(websocket, user_id, execution_id)
    
    async def _handle_client_message(
        self,
        websocket: WebSocket,
        user_id: UUID,
        message: Dict[str, Any]
    ):
        """Maneja mensajes del cliente WebSocket."""
        message_type = message.get("type")
        
        if message_type == "ping":
            # Responder a ping con pong
            await websocket.send_text(json.dumps({
                "type": "pong",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
        
        elif message_type == "get_status":
            # Obtener estado de ejecución
            execution_id = message.get("execution_id")
            if execution_id:
                status = await self.execution_service.get_execution_status(execution_id, user_id)
                await websocket.send_text(json.dumps({
                    "type": "status_update",
                    "data": status
                }))
        
        elif message_type == "pause_execution":
            # Pausar ejecución
            execution_id = message.get("execution_id")
            if execution_id:
                success = await self.execution_service.pause_execution(execution_id, user_id)
                await websocket.send_text(json.dumps({
                    "type": "execution_paused",
                    "success": success,
                    "execution_id": execution_id
                }))
        
        elif message_type == "resume_execution":
            # Reanudar ejecución
            execution_id = message.get("execution_id")
            if execution_id:
                success = await self.execution_service.resume_execution(execution_id, user_id)
                await websocket.send_text(json.dumps({
                    "type": "execution_resumed",
                    "success": success,
                    "execution_id": execution_id
                }))
        
        elif message_type == "cancel_execution":
            # Cancelar ejecución
            execution_id = message.get("execution_id")
            if execution_id:
                success = await self.execution_service.cancel_execution(execution_id, user_id)
                await websocket.send_text(json.dumps({
                    "type": "execution_cancelled",
                    "success": success,
                    "execution_id": execution_id
                }))
        
        else:
            # Mensaje no reconocido
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Tipo de mensaje no reconocido: {message_type}"
            }))
    
    # ===== MÉTODOS DE NOTIFICACIÓN =====
    
    async def notify_execution_started(
        self,
        user_id: UUID,
        execution_id: str,
        plan_id: UUID,
        total_tasks: int
    ):
        """Notifica que una ejecución ha comenzado."""
        message = {
            "type": "execution_started",
            "data": {
                "execution_id": execution_id,
                "plan_id": str(plan_id),
                "total_tasks": total_tasks,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "message": f"Ejecución iniciada con {total_tasks} tareas"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: ejecución iniciada - {execution_id}")
    
    async def notify_task_started(
        self,
        user_id: UUID,
        execution_id: str,
        task_id: UUID,
        task_title: str,
        task_index: int,
        total_tasks: int
    ):
        """Notifica que una tarea ha comenzado."""
        message = {
            "type": "task_started",
            "data": {
                "execution_id": execution_id,
                "task_id": str(task_id),
                "task_title": task_title,
                "task_index": task_index,
                "total_tasks": total_tasks,
                "progress_percentage": int((task_index / total_tasks) * 100),
                "started_at": datetime.now(timezone.utc).isoformat(),
                "message": f"Ejecutando tarea {task_index + 1}/{total_tasks}: {task_title}"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: tarea iniciada - {task_title}")
    
    async def notify_task_completed(
        self,
        user_id: UUID,
        execution_id: str,
        task_id: UUID,
        task_title: str,
        task_index: int,
        total_tasks: int,
        result: Dict[str, Any],
        execution_time: float
    ):
        """Notifica que una tarea ha sido completada."""
        message = {
            "type": "task_completed",
            "data": {
                "execution_id": execution_id,
                "task_id": str(task_id),
                "task_title": task_title,
                "task_index": task_index,
                "total_tasks": total_tasks,
                "progress_percentage": int(((task_index + 1) / total_tasks) * 100),
                "result": result,
                "execution_time": execution_time,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "message": f"✅ Tarea {task_index + 1}/{total_tasks} completada: {task_title}"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: tarea completada - {task_title}")
    
    async def notify_task_failed(
        self,
        user_id: UUID,
        execution_id: str,
        task_id: UUID,
        task_title: str,
        task_index: int,
        total_tasks: int,
        error: str
    ):
        """Notifica que una tarea ha fallado."""
        message = {
            "type": "task_failed",
            "data": {
                "execution_id": execution_id,
                "task_id": str(task_id),
                "task_title": task_title,
                "task_index": task_index,
                "total_tasks": total_tasks,
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "message": f"❌ Tarea {task_index + 1}/{total_tasks} falló: {task_title} - {error}"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: tarea falló - {task_title}")
    
    async def notify_execution_completed(
        self,
        user_id: UUID,
        execution_id: str,
        plan_id: UUID,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        success_rate: float
    ):
        """Notifica que una ejecución ha sido completada."""
        message = {
            "type": "execution_completed",
            "data": {
                "execution_id": execution_id,
                "plan_id": str(plan_id),
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "success_rate": success_rate,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "message": f"🎉 Ejecución completada: {completed_tasks}/{total_tasks} tareas exitosas ({success_rate:.1f}%)"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: ejecución completada - {execution_id}")
    
    async def notify_execution_failed(
        self,
        user_id: UUID,
        execution_id: str,
        plan_id: UUID,
        error: str
    ):
        """Notifica que una ejecución ha fallado."""
        message = {
            "type": "execution_failed",
            "data": {
                "execution_id": execution_id,
                "plan_id": str(plan_id),
                "error": error,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "message": f"💥 Ejecución falló: {error}"
            }
        }
        
        await self.connection_manager.send_to_user(user_id, message)
        await self.connection_manager.send_to_execution(execution_id, message)
        
        logger.info(f"[RealtimeTracker] 📢 Notificación enviada: ejecución falló - {execution_id}")
    
    # ===== MÉTODOS DE UTILIDAD =====
    
    def get_connection_count(self, user_id: Optional[UUID] = None) -> int:
        """Obtiene el número de conexiones activas."""
        if user_id:
            return len(self.connection_manager.active_connections.get(user_id, set()))
        else:
            return sum(len(connections) for connections in self.connection_manager.active_connections.values())
    
    def get_execution_connection_count(self, execution_id: str) -> int:
        """Obtiene el número de conexiones para una ejecución específica."""
        return len(self.connection_manager.execution_connections.get(execution_id, set()))
    
    async def broadcast_system_message(self, message: str, user_id: Optional[UUID] = None):
        """Envía un mensaje del sistema a todos los usuarios conectados."""
        broadcast_message = {
            "type": "system_message",
            "data": {
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        
        if user_id:
            await self.connection_manager.send_to_user(user_id, broadcast_message)
        else:
            # Enviar a todos los usuarios conectados
            for user_id in list(self.connection_manager.active_connections.keys()):
                await self.connection_manager.send_to_user(user_id, broadcast_message)
        
        logger.info(f"[RealtimeTracker] 📢 Mensaje del sistema enviado: {message}")
