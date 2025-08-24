#!/usr/bin/env python3
"""
SchemaGenerationService - Servicio de background para generar schemas
────────────────────────────────────────────────────────────────────
Este servicio se ejecuta en background para generar schemas de bases
de datos sin bloquear la respuesta del usuario.
"""

import asyncio
import logging
from typing import Optional
from uuid import UUID

from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.data.database_service import DatabaseService
from app.services.notifications.schema_notification_service import get_schema_notification_service
from app.utils.logger import logger

logger = logging.getLogger(__name__)


class SchemaGenerationService:
    """
    Servicio para generar schemas de bases de datos en background.
    
    Se ejecuta de forma asíncrona para no bloquear la respuesta
    del usuario cuando se añade una nueva DB.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
    
    async def generate_schema_for_db(self, db_id: UUID, user_id: UUID) -> bool:
        """
        Genera el schema completo para una base de datos en background.
        
        Args:
            db_id: ID de la base de datos
            user_id: ID del usuario
            
        Returns:
            True si se generó correctamente
        """
        try:
            self.logger.info(f"[SchemaGenerationService] 🚀 Iniciando generación de schema para DB {db_id}")
            
            # 🔧 FASE 5: Servicio de notificaciones
            notification_service = get_schema_notification_service(self.factory)
            
            # Obtener nombre de la DB para notificaciones
            db_name = await self._get_db_name(db_id)
            
            # 1. Notificar inicio de generación
            await notification_service.notify_schema_generation_started(user_id, db_id, db_name)
            
            # 2. Actualizar estado de la DB a "generating"
            await self._update_db_status(db_id, "generating")
            
            # 3. Generar schema usando DetailedSchemaCacheService
            schema_generated = await self._generate_schema(user_id, db_id)
            
            if schema_generated:
                # 4. Actualizar estado a "ready"
                await self._update_db_status(db_id, "ready")
                
                # 5. Notificar completado
                execution_time = 0  # TODO: Implementar tracking de tiempo real
                await notification_service.notify_schema_generation_completed(user_id, db_id, db_name, execution_time)
                
                self.logger.info(f"[SchemaGenerationService] ✅ Schema generado exitosamente para DB {db_id}")
                return True
                
            else:
                # 6. Si falla, actualizar estado a "error"
                await self._update_db_status(db_id, "error")
                
                # 7. Notificar fallo
                await notification_service.notify_schema_generation_failed(user_id, db_id, db_name, "Error en la generación del schema")
                
                self.logger.error(f"[SchemaGenerationService] ❌ Error generando schema para DB {db_id}")
                return False
                
        except Exception as e:
            self.logger.exception(f"[SchemaGenerationService] ❌ Error inesperado: {e}")
            
            # Actualizar estado de la DB a "error"
            await self._update_db_status(db_id, "error")
            
            # Notificar fallo inesperado
            try:
                notification_service = get_schema_notification_service(self.factory)
                db_name = await self._get_db_name(db_id)
                await notification_service.notify_schema_generation_failed(user_id, db_id, db_name, str(e))
            except Exception as notify_error:
                self.logger.warning(f"[SchemaGenerationService] ⚠️ Error enviando notificación de fallo: {notify_error}")
            
            return False
    
    async def _update_db_status(self, db_id: UUID, status: str) -> bool:
        """
        Actualiza el estado del schema en la base de datos.
        
        Args:
            db_id: ID de la base de datos
            status: Nuevo estado (pending, generating, ready, error)
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Obtener servicio de database
            database_service = self.factory.get_database_service()
            if not database_service:
                self.logger.error("[SchemaGenerationService] ❌ No se pudo obtener DatabaseService")
                return False
            
            # Actualizar estado en la BD
            from app.schemas.database_schema import DatabaseConnectionUpdate
            
            update_data = DatabaseConnectionUpdate(schema_status=status)
            database_service.update_connection(db_id, update_data)
            
            self.logger.info(f"[SchemaGenerationService] 🔄 Estado de DB {db_id} actualizado a: {status}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGenerationService] ❌ Error actualizando estado de DB {db_id}: {e}")
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
            self.logger.warning(f"[SchemaGenerationService] ⚠️ Error obteniendo nombre de DB {db_id}: {e}")
            return "Unknown DB"
    
    async def _generate_schema(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Genera el schema completo para una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            True si se generó correctamente
        """
        try:
            # Obtener servicio de cache de schema
            detailed_cache_service = self.factory.get_detailed_schema_cache_service()
            if not detailed_cache_service:
                self.logger.error("[SchemaGenerationService] ❌ No se pudo obtener DetailedSchemaCacheService")
                return False
            
            # Generar schema automáticamente
            # Este método ya existe y funciona correctamente
            schema_response = await detailed_cache_service.get_schema_cache(user_id, db_id)
            
            if schema_response:
                self.logger.info(f"[SchemaGenerationService] ✅ Schema generado y cacheado para DB {db_id}")
                return True
            else:
                self.logger.error(f"[SchemaGenerationService] ❌ No se pudo generar schema para DB {db_id}")
                return False
                
        except Exception as e:
            self.logger.exception(f"[SchemaGenerationService] ❌ Error generando schema: {e}")
            return False


# Función helper para usar con FastAPI BackgroundTasks
async def generate_schema_background(db_id: UUID, user_id: UUID, factory) -> None:
    """
    Función helper para ejecutar en background con FastAPI BackgroundTasks.
    
    Args:
        db_id: ID de la base de datos
        user_id: ID del usuario
        factory: ServiceFactory para obtener servicios
    """
    try:
        service = SchemaGenerationService(factory)
        await service.generate_schema_for_db(db_id, user_id)
    except Exception as e:
        logger.error(f"[BackgroundTask] ❌ Error en generación de schema: {e}")
