#!/usr/bin/env python3
"""
WSEmitter - Servicio común para emisión de eventos WebSocket
─────────────────────────────────────────────────────────────
Implementa:
- Emisión de eventos a usuarios específicos
- Emisión de eventos a todos los usuarios
- Gestión de conexiones WebSocket activas
- Broadcast de mensajes del sistema
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class WSEmitter:
    """
    Servicio para emisión de eventos WebSocket.
    
    Características:
    - Emisión a usuarios específicos
    - Broadcast a todos los usuarios
    - Gestión de conexiones activas
    - Rate limiting básico
    """
    
    def __init__(self):
        self.logger = logger
        
        # Conexiones WebSocket activas por usuario
        self._active_connections: Dict[str, List[Any]] = {}
        
        # Estadísticas de emisión
        self._emission_stats = {
            'total_emissions': 0,
            'successful_emissions': 0,
            'failed_emissions': 0,
            'active_users': 0
        }
        
        # Rate limiting por usuario
        self._user_rate_limits: Dict[str, float] = {}
        self._rate_limit_duration = 0.1  # 100ms entre emisiones al mismo usuario
    
    async def emit_to_user(self, user_id: str, event: str, data: Any) -> bool:
        """
        Emite un evento a un usuario específico.
        
        Args:
            user_id: ID del usuario
            event: Nombre del evento
            data: Datos del evento
            
        Returns:
            True si se emitió correctamente, False en caso contrario
        """
        try:
            if user_id not in self._active_connections:
                self.logger.debug(f"[WSEmitter] ⚠️ Usuario {user_id} no tiene conexiones activas")
                return False
            
            # Verificar rate limiting
            if self._is_rate_limited(user_id):
                self.logger.debug(f"[WSEmitter] ⏳ Rate limited para usuario {user_id}")
                return False
            
            # Preparar mensaje
            message = {
                'event': event,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_id': f"{user_id}_{event}_{int(datetime.now().timestamp() * 1000)}"
            }
            
            # Emitir a todas las conexiones del usuario
            connections = self._active_connections[user_id]
            successful_emissions = 0
            
            for connection in connections:
                try:
                    if hasattr(connection, 'send_text'):
                        await connection.send_text(json.dumps(message))
                        successful_emissions += 1
                    elif hasattr(connection, 'send'):
                        await connection.send(json.dumps(message))
                        successful_emissions += 1
                    else:
                        self.logger.warning(f"[WSEmitter] ⚠️ Conexión sin método send válido: {type(connection)}")
                        
                except Exception as e:
                    self.logger.warning(f"[WSEmitter] ⚠️ Error enviando a conexión: {e}")
                    # Marcar conexión como inactiva
                    connections.remove(connection)
            
            # Actualizar estadísticas
            self._emission_stats['total_emissions'] += 1
            if successful_emissions > 0:
                self._emission_stats['successful_emissions'] += 1
                self._update_rate_limit(user_id)
                self.logger.debug(f"[WSEmitter] ✅ Evento '{event}' emitido a usuario {user_id}")
                return True
            else:
                self._emission_stats['failed_emissions'] += 1
                self.logger.warning(f"[WSEmitter] ❌ No se pudo emitir evento '{event}' a usuario {user_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error emitiendo evento '{event}' a usuario {user_id}: {e}")
            self._emission_stats['failed_emissions'] += 1
            return False
    
    async def emit_to_all_users(self, event: str, data: Any, exclude_user: Optional[str] = None) -> Dict[str, int]:
        """
        Emite un evento a todos los usuarios activos.
        
        Args:
            event: Nombre del evento
            data: Datos del evento
            exclude_user: Usuario a excluir (opcional)
            
        Returns:
            Diccionario con estadísticas de emisión
        """
        try:
            results = {
                'total_users': len(self._active_connections),
                'successful_emissions': 0,
                'failed_emissions': 0,
                'excluded_users': 0
            }
            
            # Preparar mensaje
            message = {
                'event': event,
                'data': data,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_id': f"broadcast_{event}_{int(datetime.now().timestamp() * 1000)}"
            }
            
            for user_id, connections in self._active_connections.items():
                if exclude_user and user_id == exclude_user:
                    results['excluded_users'] += 1
                    continue
                
                # Emitir a todas las conexiones del usuario
                user_success = 0
                for connection in connections:
                    try:
                        if hasattr(connection, 'send_text'):
                            await connection.send_text(json.dumps(message))
                            user_success += 1
                        elif hasattr(connection, 'send'):
                            await connection.send(json.dumps(message))
                            user_success += 1
                            
                    except Exception as e:
                        self.logger.warning(f"[WSEmitter] ⚠️ Error en broadcast a usuario {user_id}: {e}")
                        connections.remove(connection)
                
                if user_success > 0:
                    results['successful_emissions'] += 1
                else:
                    results['failed_emissions'] += 1
            
            # Actualizar estadísticas
            self._emission_stats['total_emissions'] += results['total_users']
            self._emission_stats['successful_emissions'] += results['successful_emissions']
            self._emission_stats['failed_emissions'] += results['failed_emissions']
            
            self.logger.info(f"[WSEmitter] 📢 Broadcast '{event}' completado: {results['successful_emissions']}/{results['total_users']} usuarios")
            return results
            
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error en broadcast '{event}': {e}")
            return {
                'total_users': 0,
                'successful_emissions': 0,
                'failed_emissions': 1,
                'excluded_users': 0
            }
    
    async def emit_to_multiple_users(self, user_ids: List[str], event: str, data: Any) -> Dict[str, int]:
        """
        Emite un evento a múltiples usuarios específicos.
        
        Args:
            user_ids: Lista de IDs de usuarios
            event: Nombre del evento
            data: Datos del evento
            
        Returns:
            Diccionario con estadísticas de emisión
        """
        try:
            results = {
                'target_users': len(user_ids),
                'successful_emissions': 0,
                'failed_emissions': 0
            }
            
            for user_id in user_ids:
                success = await self.emit_to_user(user_id, event, data)
                if success:
                    results['successful_emissions'] += 1
                else:
                    results['failed_emissions'] += 1
            
            self.logger.info(f"[WSEmitter] 📤 Emisión múltiple '{event}': {results['successful_emissions']}/{results['target_users']} usuarios")
            return results
            
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error en emisión múltiple '{event}': {e}")
            return {
                'target_users': len(user_ids),
                'successful_emissions': 0,
                'failed_emissions': len(user_ids)
            }
    
    def register_connection(self, user_id: str, connection: Any) -> None:
        """
        Registra una nueva conexión WebSocket para un usuario.
        
        Args:
            user_id: ID del usuario
            connection: Objeto de conexión WebSocket
        """
        try:
            if user_id not in self._active_connections:
                self._active_connections[user_id] = []
                self._emission_stats['active_users'] += 1
            
            self._active_connections[user_id].append(connection)
            self.logger.info(f"[WSEmitter] ✅ Conexión registrada para usuario {user_id} (total: {len(self._active_connections[user_id])})")
            
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error registrando conexión para usuario {user_id}: {e}")
    
    def unregister_connection(self, user_id: str, connection: Any) -> None:
        """
        Desregistra una conexión WebSocket de un usuario.
        
        Args:
            user_id: ID del usuario
            connection: Objeto de conexión WebSocket
        """
        try:
            if user_id in self._active_connections:
                if connection in self._active_connections[user_id]:
                    self._active_connections[user_id].remove(connection)
                    self.logger.debug(f"[WSEmitter] ✅ Conexión desregistrada para usuario {user_id}")
                
                # Si no quedan conexiones, eliminar usuario
                if not self._active_connections[user_id]:
                    del self._active_connections[user_id]
                    self._emission_stats['active_users'] -= 1
                    self.logger.info(f"[WSEmitter] ✅ Usuario {user_id} sin conexiones activas")
                    
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error desregistrando conexión para usuario {user_id}: {e}")
    
    def get_user_connections_count(self, user_id: str) -> int:
        """Obtiene el número de conexiones activas de un usuario"""
        return len(self._active_connections.get(user_id, []))
    
    def get_active_users_count(self) -> int:
        """Obtiene el número total de usuarios con conexiones activas"""
        return len(self._active_connections)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de conexiones"""
        total_connections = sum(len(connections) for connections in self._active_connections.values())
        
        return {
            'active_users': len(self._active_connections),
            'total_connections': total_connections,
            'average_connections_per_user': total_connections / len(self._active_connections) if self._active_connections else 0,
            'emission_stats': self._emission_stats.copy()
        }
    
    def _is_rate_limited(self, user_id: str) -> bool:
        """Verifica si un usuario está rate limited"""
        last_emission = self._user_rate_limits.get(user_id, 0)
        current_time = asyncio.get_event_loop().time()
        
        return (current_time - last_emission) < self._rate_limit_duration
    
    def _update_rate_limit(self, user_id: str) -> None:
        """Actualiza el rate limit de un usuario"""
        self._user_rate_limits[user_id] = asyncio.get_event_loop().time()
    
    def cleanup_inactive_connections(self) -> int:
        """
        Limpia conexiones inactivas.
        
        Returns:
            Número de conexiones limpiadas
        """
        try:
            cleaned_count = 0
            
            for user_id in list(self._active_connections.keys()):
                # Filtrar conexiones inactivas
                active_connections = []
                for connection in self._active_connections[user_id]:
                    try:
                        # Verificar si la conexión está activa
                        if hasattr(connection, 'closed') and not connection.closed:
                            active_connections.append(connection)
                        elif hasattr(connection, 'is_closed') and not connection.is_closed():
                            active_connections.append(connection)
                        else:
                            cleaned_count += 1
                    except:
                        cleaned_count += 1
                
                # Actualizar lista de conexiones
                if active_connections:
                    self._active_connections[user_id] = active_connections
                else:
                    del self._active_connections[user_id]
                    self._emission_stats['active_users'] -= 1
            
            if cleaned_count > 0:
                self.logger.info(f"[WSEmitter] 🧹 Limpieza completada: {cleaned_count} conexiones inactivas eliminadas")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"[WSEmitter] ❌ Error en limpieza de conexiones: {e}")
            return 0


# Instancia global del WSEmitter
ws_emitter = WSEmitter()


def get_ws_emitter() -> WSEmitter:
    """Obtiene la instancia global del WSEmitter"""
    return ws_emitter
