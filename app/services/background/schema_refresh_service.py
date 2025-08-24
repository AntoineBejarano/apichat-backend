#!/usr/bin/env python3
"""
SchemaRefreshService - Servicio de background para refresh de schemas
────────────────────────────────────────────────────────────────────
Permite al usuario actualizar manualmente el schema de su DB con:
- Regeneración en background
- Fallback a schema anterior si falla
- Contador de intentos
- Notificaciones de estado
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone

from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.data.database_service import DatabaseService
from app.services.cache.redis_schema_cache import redis_schema_cache
from app.services.notifications.schema_notification_service import get_schema_notification_service
from app.utils.logger import logger

logger = logging.getLogger(__name__)


class SchemaRefreshService:
    """
    Servicio para refrescar schemas de bases de datos en background.
    
    Características:
    - Refresh manual a demanda del usuario
    - Regeneración completa del schema
    - Fallback a schema anterior si falla
    - Contador de intentos para evitar loops
    - Invalidación de cache Redis
    - Actualización de estado en BD
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # Contador de intentos por DB (para evitar loops infinitos)
        self._refresh_attempts: Dict[str, int] = {}
        self.max_attempts = 3
    
    async def refresh_schema_for_db(self, db_id: UUID, user_id: UUID, force: bool = False) -> Dict[str, Any]:
        """
        Refresca el schema de una base de datos específica.
        
        Args:
            db_id: ID de la base de datos
            user_id: ID del usuario
            force: Si True, fuerza refresh aunque haya errores previos
            
        Returns:
            Resultado del refresh con estado y mensajes
        """
        start_time = time.time()
        db_key = f"{user_id}:{db_id}"
        
        try:
            logger.info(f"[SchemaRefreshService] 🔄 Iniciando refresh de schema para DB {db_id}")
            
            # 🔧 FASE 5: Servicio de notificaciones
            notification_service = get_schema_notification_service(self.factory)
            
            # Obtener nombre de la DB para notificaciones
            db_name = await self._get_db_name(db_id)
            
            # Verificar intentos previos
            if not force and self._refresh_attempts.get(db_key, 0) >= self.max_attempts:
                logger.warning(f"[SchemaRefreshService] ⚠️ Máximo de intentos alcanzado para DB {db_id}")
                
                # Notificar fallo por máximo de intentos
                await notification_service.notify_schema_refresh_failed(
                    user_id, db_id, db_name, 
                    "Maximum refresh attempts reached. Please contact support."
                )
                
                return {
                    'success': False,
                    'status': 'max_attempts_reached',
                    'message': 'Maximum refresh attempts reached. Please contact support.',
                    'attempts': self._refresh_attempts.get(db_key, 0),
                    'execution_time': (time.time() - start_time) * 1000
                }
            
            # Incrementar contador de intentos
            self._refresh_attempts[db_key] = self._refresh_attempts.get(db_key, 0) + 1
            current_attempt = self._refresh_attempts[db_key]
            
            logger.info(f"[SchemaRefreshService] 📊 Intento {current_attempt}/{self.max_attempts} para DB {db_id}")
            
            # 1. Notificar inicio de refresh
            await notification_service.notify_schema_refresh_started(user_id, db_id, db_name)
            
            # 2. Actualizar estado a "updating"
            await self._update_db_status(db_id, user_id, "updating")
            
            # 2. Invalidar cache Redis
            redis_schema_cache.invalidate_schema(user_id, db_id)
            logger.info(f"[SchemaRefreshService] 🗑️ Cache Redis invalidado para DB {db_id}")
            
            # 3. Generar nuevo schema
            new_schema = await self._generate_new_schema(db_id, user_id)
            
            if new_schema:
                # 4. Actualizar cache en BD
                await self._update_cache_in_db(db_id, user_id, new_schema)
                
                # 5. Cachear en Redis
                redis_schema_cache.set_schema(user_id, db_id, new_schema)
                
                # 6. Actualizar estado a "ready"
                await self._update_db_status(db_id, user_id, "ready")
                
                # 7. Resetear contador de intentos (éxito)
                self._refresh_attempts[db_key] = 0
                
                # 8. Notificar éxito
                await notification_service.notify_schema_refresh_completed(user_id, db_id, db_name, False)
                
                execution_time = (time.time() - start_time) * 1000
                logger.info(f"[SchemaRefreshService] ✅ Schema refresh completado para DB {db_id} ({execution_time:.2f}ms)")
                
                return {
                    'success': True,
                    'status': 'completed',
                    'message': 'Schema refreshed successfully',
                    'attempts': current_attempt,
                    'execution_time': execution_time,
                    'new_schema': new_schema
                }
            else:
                # Fallback: mantener schema anterior
                await self._handle_refresh_failure(db_id, user_id, current_attempt)
                
                # Notificar fallo
                await notification_service.notify_schema_refresh_failed(
                    user_id, db_id, db_name, 
                    self._get_error_message(current_attempt)
                )
                
                execution_time = (time.time() - start_time) * 1000
                return {
                    'success': False,
                    'status': 'failed',
                    'message': self._get_error_message(current_attempt),
                    'attempts': current_attempt,
                    'execution_time': execution_time
                }
                
        except Exception as e:
            logger.error(f"[SchemaRefreshService] ❌ Error en refresh de schema para DB {db_id}: {e}")
            
            # Fallback: mantener schema anterior
            await self._handle_refresh_failure(db_id, user_id, current_attempt)
            
            # Notificar fallo inesperado
            try:
                await notification_service.notify_schema_refresh_failed(
                    user_id, db_id, db_name, f"Unexpected error: {str(e)}"
                )
            except Exception as notify_error:
                logger.warning(f"[SchemaRefreshService] ⚠️ Error enviando notificación de fallo: {notify_error}")
            
            execution_time = (time.time() - start_time) * 1000
            return {
                'success': False,
                'status': 'error',
                'message': f'Unexpected error: {str(e)}',
                'attempts': current_attempt,
                'execution_time': execution_time
            }
    
    async def _update_db_status(self, db_id: UUID, user_id: UUID, status: str) -> bool:
        """Actualiza el estado de la DB en la base de datos"""
        try:
            database_service = self.factory.get_database_service()
            if database_service:
                # Actualizar estado en la tabla database_connections
                from app.models.database_model import DatabaseConnection
                from sqlalchemy import update
                
                stmt = update(DatabaseConnection).where(
                    DatabaseConnection.id == db_id,
                    DatabaseConnection.user_id == user_id
                ).values(schema_status=status, updated_at=datetime.now(timezone.utc))
                
                database_service.db.execute(stmt)
                database_service.db.commit()
                
                logger.info(f"[SchemaRefreshService] ✅ Estado de DB {db_id} actualizado a '{status}'")
                return True
            else:
                logger.error("[SchemaRefreshService] ❌ No se pudo obtener DatabaseService")
                return False
                
        except Exception as e:
            logger.error(f"[SchemaRefreshService] ❌ Error actualizando estado de DB {db_id}: {e}")
            return False
    
    async def _get_db_name(self, db_id: UUID) -> str:
        """
        Obtiene el nombre de la base de datos.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Nombre de la DB o "Unknown DB" si no se puede obtener
        """
        try:
            database_service = self.factory.get_database_service()
            if not database_service:
                return "Unknown DB"
            
            db_record = database_service.get_record(db_id)
            if db_record:
                return db_record.name or "Unknown DB"
            
            return "Unknown DB"
            
        except Exception as e:
            self.logger.warning(f"[SchemaRefreshService] ⚠️ Error obteniendo nombre de DB {db_id}: {e}")
            return "Unknown DB"
    
    async def _generate_new_schema(self, db_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Genera un nuevo schema para la base de datos"""
        try:
            logger.info(f"[SchemaRefreshService] 🔧 Generando nuevo schema para DB {db_id}")
            
            # Usar el servicio de cache para generar schema
            cache_service = DetailedSchemaCacheService(self.factory)
            
            # Generar schema automáticamente
            new_schema_response = await cache_service._generate_schema_automatically(user_id, db_id)
            
            if new_schema_response:
                logger.info(f"[SchemaRefreshService] ✅ Nuevo schema generado para DB {db_id}")
                return new_schema_response.model_dump()
            else:
                logger.error(f"[SchemaRefreshService] ❌ No se pudo generar nuevo schema para DB {db_id}")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaRefreshService] ❌ Error generando nuevo schema para DB {db_id}: {e}")
            return None
    
    async def _update_cache_in_db(self, db_id: UUID, user_id: UUID, new_schema: Dict[str, Any]) -> bool:
        """Actualiza el cache en la base de datos"""
        try:
            cache_service = DetailedSchemaCacheService(self.factory)
            
            # Convertir schema a SchemaSnapshot
            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
            
            snapshot = SchemaSnapshot(
                tables=new_schema.get('snapshot', {}).get('tables', {}),
                enrichment_level=EnrichmentLevel.BASIC,
                dialect=new_schema.get('snapshot', {}).get('dialect', 'postgresql'),
                generated_at=datetime.now(timezone.utc)
            )
            
            # Actualizar cache
            await cache_service.create_or_update_cache(
                user_id=user_id,
                db_id=db_id,
                snapshot=snapshot,
                enrichment_level=EnrichmentLevel.BASIC
            )
            
            logger.info(f"[SchemaRefreshService] ✅ Cache en BD actualizado para DB {db_id}")
            return True
            
        except Exception as e:
            logger.error(f"[SchemaRefreshService] ❌ Error actualizando cache en BD para DB {db_id}: {e}")
            return False
    
    async def _handle_refresh_failure(self, db_id: UUID, user_id: UUID, attempt: int) -> None:
        """Maneja el fallo en el refresh del schema"""
        try:
            logger.warning(f"[SchemaRefreshService] ⚠️ Fallo en refresh de DB {db_id}, intento {attempt}")
            
            # Actualizar estado a "error" si es el último intento
            if attempt >= self.max_attempts:
                await self._update_db_status(db_id, user_id, "error")
                logger.error(f"[SchemaRefreshService] ❌ DB {db_id} marcada como error después de {attempt} intentos")
            else:
                # Mantener estado anterior si no es el último intento
                await self._update_db_status(db_id, user_id, "ready")
                logger.info(f"[SchemaRefreshService] 🔄 DB {db_id} mantenida en estado ready para reintento")
                
        except Exception as e:
            logger.error(f"[SchemaRefreshService] ❌ Error manejando fallo de refresh para DB {db_id}: {e}")
    
    def _get_error_message(self, attempt: int) -> str:
        """Genera mensaje de error apropiado según el número de intentos"""
        if attempt >= self.max_attempts:
            return "There was an error loading your database. Please delete it and add it again. If this is your 3rd attempt, please contact support."
        elif attempt == 2:
            return "There was an error refreshing your database. Please try again. If this continues, you may need to delete and re-add the database."
        else:
            return "There was an error refreshing your database. Please try again."
    
    def get_refresh_attempts(self, db_id: UUID, user_id: UUID) -> int:
        """Obtiene el número de intentos de refresh para una DB"""
        db_key = f"{user_id}:{db_id}"
        return self._refresh_attempts.get(db_key, 0)
    
    def reset_refresh_attempts(self, db_id: UUID, user_id: UUID) -> None:
        """Resetea el contador de intentos para una DB"""
        db_key = f"{user_id}:{db_id}"
        if db_key in self._refresh_attempts:
            del self._refresh_attempts[db_key]
            logger.info(f"[SchemaRefreshService] 🔄 Contador de intentos reseteado para DB {db_id}")
    
    def get_all_refresh_attempts(self) -> Dict[str, int]:
        """Obtiene todos los contadores de intentos (para debugging)"""
        return self._refresh_attempts.copy()


# Función helper para usar con FastAPI BackgroundTasks
async def refresh_schema_background(db_id: UUID, user_id: UUID, factory, force: bool = False) -> None:
    """
    Función helper para ejecutar refresh de schema en background con FastAPI BackgroundTasks.
    
    Args:
        db_id: ID de la base de datos
        user_id: ID del usuario
        factory: ServiceFactory para obtener servicios
        force: Si True, fuerza refresh aunque haya errores previos
    """
    try:
        service = SchemaRefreshService(factory)
        result = await service.refresh_schema_for_db(db_id, user_id, force)
        
        if result['success']:
            logger.info(f"[BackgroundTask] ✅ Schema refresh completado para DB {db_id}")
        else:
            logger.warning(f"[BackgroundTask] ⚠️ Schema refresh falló para DB {db_id}: {result['message']}")
            
    except Exception as e:
        logger.error(f"[BackgroundTask] ❌ Error en refresh de schema: {e}")
