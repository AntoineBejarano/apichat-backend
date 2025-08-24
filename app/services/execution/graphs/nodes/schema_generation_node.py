#!/usr/bin/env python3
"""
SchemaGenerationNode - Genera schemas de DB en background
──────────────────────────────────────────────────────────
Este nodo se ejecuta cuando se añade una nueva DB para generar
el schema completo antes de que el usuario intente usarla.
"""

import time
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.data.database_service import DatabaseService
from app.utils.logger import logger

logger = logging.getLogger(__name__)


class SchemaGenerationNode:
    """
    Nodo para generar schemas de base de datos en background.
    
    Se ejecuta cuando se añade una nueva DB para pre-generar
    el schema completo y cachearlo para uso inmediato.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.node_name = "schema_generation"
        
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la generación de schema en background.
        
        Args:
            state: Estado del grafo con información de la DB
            
        Returns:
            Estado actualizado con resultado de la generación
        """
        node_start_time = time.time()
        logger.info(f"[SchemaGenerationNode] 🚀 Iniciando generación de schema para DB")
        
        try:
            # Extraer información del estado
            db_id = state.get("db_id")
            user_id = state.get("user_id")
            
            if not db_id or not user_id:
                logger.error("[SchemaGenerationNode] ❌ db_id o user_id no encontrados en state")
                return state
            
            logger.info(f"[SchemaGenerationNode] 🔍 Generando schema para DB {db_id}")
            
            # 1. Actualizar estado de la DB a "generating"
            await self._update_db_status(db_id, "generating")
            
            # 2. Generar schema usando DetailedSchemaCacheService
            schema_generated = await self._generate_schema(user_id, db_id)
            
            if schema_generated:
                # 3. Actualizar estado a "ready"
                await self._update_db_status(db_id, "ready")
                logger.info(f"[SchemaGenerationNode] ✅ Schema generado exitosamente para DB {db_id}")
                
                # 4. Actualizar estado del grafo
                state["schema_status"] = "ready"
                state["schema_generated_at"] = time.time()
                
            else:
                # 5. Si falla, actualizar estado a "error"
                await self._update_db_status(db_id, "error")
                logger.error(f"[SchemaGenerationNode] ❌ Error generando schema para DB {db_id}")
                
                state["schema_status"] = "error"
                state["schema_error"] = "Failed to generate schema"
            
            # 6. Calcular métricas de performance
            execution_time = time.time() - node_start_time
            logger.info(f"[SchemaGenerationNode] ⏱️ Schema generado en {execution_time:.3f}s")
            
            return state
            
        except Exception as e:
            logger.exception(f"[SchemaGenerationNode] ❌ Error inesperado: {e}")
            
            # Actualizar estado de la DB a "error"
            if "db_id" in state:
                await self._update_db_status(state["db_id"], "error")
            
            # Retornar estado con error
            state["schema_status"] = "error"
            state["schema_error"] = str(e)
            return state
    
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
                logger.error("[SchemaGenerationNode] ❌ No se pudo obtener DatabaseService")
                return False
            
            # Actualizar estado en la BD
            # NOTA: Necesitamos añadir método update_schema_status al DatabaseService
            # Por ahora, usamos el método existente de update
            from app.schemas.database_schema import DatabaseConnectionUpdate
            
            update_data = DatabaseConnectionUpdate(schema_status=status)
            database_service.update_connection(db_id, update_data)
            
            logger.info(f"[SchemaGenerationNode] 🔄 Estado de DB {db_id} actualizado a: {status}")
            return True
            
        except Exception as e:
            logger.error(f"[SchemaGenerationNode] ❌ Error actualizando estado de DB {db_id}: {e}")
            return False
    
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
                logger.error("[SchemaGenerationNode] ❌ No se pudo obtener DetailedSchemaCacheService")
                return False
            
            # Generar schema automáticamente
            # Este método ya existe y funciona correctamente
            schema_response = await detailed_cache_service.get_schema_cache(user_id, db_id)
            
            if schema_response:
                logger.info(f"[SchemaGenerationNode] ✅ Schema generado y cacheado para DB {db_id}")
                return True
            else:
                logger.error(f"[SchemaGenerationNode] ❌ No se pudo generar schema para DB {db_id}")
                return False
                
        except Exception as e:
            logger.exception(f"[SchemaGenerationNode] ❌ Error generando schema: {e}")
            return False
