#!/usr/bin/env python3
"""
ContextResolverService - Servicio de resolución de contexto para la Fase 5
─────────────────────────────────────────────────────────────────────────
Implementa:
- Resolución de snapshot_id activo del dbId seleccionado
- Mapeo appId → DB
- Verificación de readiness del schema
- Carga de contexto completo
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class ContextResolverService:
    """
    Servicio para resolver el contexto completo de una consulta de chat.
    
    Implementa la primera etapa de la Fase 5:
    - Resolución de snapshot_id activo
    - Verificación de readiness del schema
    - Carga de contexto completo
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 5: Servicios necesarios
        self.db_service = None
        self.schema_service = None
        self.graph_service = None
        
        # Intentar obtener servicios
        try:
            self.db_service = factory.get_database_service()
        except:
            pass
            
        try:
            self.schema_service = factory.get_detailed_schema_cache_service()
        except:
            pass
            
        try:
            self.graph_service = factory.get_schema_graph_service()
        except:
            pass
    
    async def resolve_context(
        self, 
        user_id: UUID, 
        db_id: UUID, 
        app_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Resuelve el contexto completo para una consulta.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            app_id: ID de la aplicación (opcional)
            
        Returns:
            Contexto completo con snapshot_id, schema, grafo, etc.
        """
        try:
            start_time = time.time()
            self.logger.info(f"[ContextResolverService] 🔍 Resolviendo contexto para DB {db_id}")
            
            # 🔧 FASE 5: 1. Verificar que la DB existe y pertenece al usuario
            if not self.db_service:
                raise Exception("Servicio de base de datos no disponible")
            
            db_connection = self.db_service.get_record(db_id)
            if not db_connection:
                raise Exception(f"Base de datos {db_id} no encontrada")
            
            if db_connection.user_id != user_id:
                raise Exception(f"No tienes permisos para acceder a la base de datos {db_id}")
            
            # 🔧 FASE 5: 2. Verificar estado del schema
            schema_status = db_connection.schema_status
            if schema_status != "ready":
                raise Exception(f"Schema no está listo. Estado actual: {schema_status}")
            
            # 🔧 FASE 5: 3. Obtener snapshot_id activo
            snapshot_id = await self._get_active_snapshot_id(db_id, user_id)
            if not snapshot_id:
                raise Exception("No se encontró snapshot activo para la base de datos")
            
            # 🔧 FASE 5: 4. Cargar schema completo
            schema_data = await self._load_schema_data(db_id, user_id, snapshot_id)
            if not schema_data:
                raise Exception("No se pudo cargar el schema de la base de datos")
            
            # 🔧 FASE 5: 5. Cargar grafo de relaciones
            graph_data = await self._load_graph_data(db_id, user_id)
            
            # 🔧 FASE 5: 6. Construir contexto completo
            context = {
                # 🔧 FASE 5: Identificación
                "db_id": str(db_id),
                "user_id": str(user_id),
                "app_id": str(app_id) if app_id else None,
                "snapshot_id": str(snapshot_id),
                
                # 🔧 FASE 5: Estado del schema
                "snapshot_ready": True,
                "schema_status": schema_status,
                "schema_version": getattr(db_connection, 'schema_version', '1.0'),
                "last_schema_update": db_connection.last_schema_update.isoformat() if db_connection.last_schema_update else None,
                
                # 🔧 FASE 5: Información del schema
                "total_tables": len(schema_data.get('tables', {})),
                "total_columns": sum(len(table.get('columns', {})) for table in schema_data.get('tables', {}).values()),
                "total_relationships": len(schema_data.get('relationships', [])),
                "total_foreign_keys": len([r for r in schema_data.get('relationships', []) if r.get('type') == 'FK']),
                "total_many_to_many": len([r for r in schema_data.get('relationships', []) if r.get('type') == 'M2M']),
                
                # 🔧 FASE 5: Datos del schema
                "schema": schema_data,
                "graph": graph_data,
                
                # 🔧 FASE 5: Metadatos de la DB
                "database_name": db_connection.name,
                "database_host": db_connection.host,
                "database_port": db_connection.port,
                "database_name_db": db_connection.database,
                "database_dialect": db_connection.dialect,
                
                # 🔧 FASE 5: Timestamps
                "context_resolved_at": datetime.now(timezone.utc).isoformat(),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
            
            self.logger.info(f"[ContextResolverService] ✅ Contexto resuelto: {context['total_tables']} tablas, {context['total_relationships']} relaciones")
            return context
            
        except Exception as e:
            self.logger.error(f"[ContextResolverService] ❌ Error resolviendo contexto: {e}")
            raise
    
    async def _get_active_snapshot_id(self, db_id: UUID, user_id: UUID) -> Optional[UUID]:
        """Obtiene el snapshot_id activo para una base de datos"""
        try:
            # 🔧 FASE 5: Intentar obtener del cache del schema
            if self.schema_service:
                cache_entry = self.schema_service.get_cache_entry(user_id, db_id)
                if cache_entry and cache_entry.schema:
                    # Usar el ID del cache entry como snapshot_id
                    return cache_entry.id
            
            # 🔧 FASE 5: Fallback: usar el ID de la DB como snapshot_id
            # (esto se puede mejorar cuando tengamos el sistema de snapshots completo)
            return db_id
            
        except Exception as e:
            self.logger.warning(f"[ContextResolverService] ⚠️ Error obteniendo snapshot_id: {e}")
            return db_id
    
    async def _load_schema_data(self, db_id: UUID, user_id: UUID, snapshot_id: UUID) -> Optional[Dict[str, Any]]:
        """Carga los datos del schema"""
        try:
            # 🔧 FASE 5: Intentar obtener del cache del schema
            if self.schema_service:
                cache_entry = self.schema_service.get_cache_entry(user_id, db_id)
                if cache_entry and cache_entry.schema:
                    return cache_entry.schema
            
            # 🔧 FASE 5: Fallback: schema básico
            return {
                "tables": {},
                "relationships": [],
                "metadata": {
                    "snapshot_id": str(snapshot_id),
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            self.logger.warning(f"[ContextResolverService] ⚠️ Error cargando schema: {e}")
            return None
    
    async def _load_graph_data(self, db_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Carga los datos del grafo de relaciones"""
        try:
            # 🔧 FASE 5: Intentar obtener del servicio del grafo
            if self.graph_service:
                graph_data = await self.graph_service.get_graph(db_id, user_id)
                if graph_data:
                    return graph_data
            
            # 🔧 FASE 5: Fallback: grafo básico
            return {
                "nodes": [],
                "edges": [],
                "metadata": {
                    "status": "not_available",
                    "message": "Grafo no disponible"
                }
            }
            
        except Exception as e:
            self.logger.warning(f"[ContextResolverService] ⚠️ Error cargando grafo: {e}")
            return None
    
    async def get_context_summary(self, context: Dict[str, Any]) -> str:
        """Genera un resumen del contexto para logging"""
        try:
            summary = f"DB: {context.get('database_name', 'Unknown')} | "
            summary += f"Tables: {context.get('total_tables', 0)} | "
            summary += f"Columns: {context.get('total_columns', 0)} | "
            summary += f"Relationships: {context.get('total_relationships', 0)} | "
            summary += f"Snapshot: {context.get('snapshot_id', 'Unknown')}"
            return summary
        except Exception as e:
            return f"Error generando resumen: {e}"
    
    async def validate_context_readiness(self, context: Dict[str, Any]) -> bool:
        """Valida que el contexto esté listo para procesar consultas"""
        try:
            # 🔧 FASE 5: Validaciones básicas
            required_fields = [
                'snapshot_ready', 'schema_status', 'snapshot_id', 
                'total_tables', 'schema'
            ]
            
            for field in required_fields:
                if field not in context:
                    self.logger.warning(f"[ContextResolverService] ⚠️ Campo requerido faltante: {field}")
                    return False
            
            # 🔧 FASE 5: Validar estado del schema
            if not context.get('snapshot_ready'):
                self.logger.warning(f"[ContextResolverService] ⚠️ Schema no está listo")
                return False
            
            if context.get('schema_status') != 'ready':
                self.logger.warning(f"[ContextResolverService] ⚠️ Estado del schema incorrecto: {context.get('schema_status')}")
                return False
            
            # 🔧 FASE 5: Validar que hay datos
            if context.get('total_tables', 0) == 0:
                self.logger.warning(f"[ContextResolverService] ⚠️ No hay tablas disponibles")
                return False
            
            if not context.get('schema'):
                self.logger.warning(f"[ContextResolverService] ⚠️ Schema vacío")
                return False
            
            self.logger.info(f"[ContextResolverService] ✅ Contexto validado correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"[ContextResolverService] ❌ Error validando contexto: {e}")
            return False
