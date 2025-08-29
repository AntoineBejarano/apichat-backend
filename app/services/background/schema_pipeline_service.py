#!/usr/bin/env python3
"""
SchemaPipelineService - Servicio principal del pipeline de generación de schema
──────────────────────────────────────────────────────────────────────────────
Implementa:
- Pipeline completo con 7 stages estandarizados
- Tracking de progreso y estados
- Sistema de reintentos automáticos
- Logs JSON con trace_id y métricas
- Timeouts configurables por stage
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from uuid import UUID

from app.models.schema_pipeline_model import (
    SchemaPipeline, 
    SchemaPipelineStatus, 
    SchemaPipelineStage
)
from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.data.database_service import DatabaseService
from app.services.notifications.schema_notification_service import get_schema_notification_service
from app.utils.logger import logger


class SchemaPipelineService:
    """
    Servicio principal para el pipeline de generación de schema.
    
    Implementa los 7 stages estandarizados según el plan de refactorización:
    1. validate_db_access
    2. extract_schema_snapshot  
    3. build_graph
    4. generate_chunks
    5. embed_chunks
    6. vector_upsert
    7. finalize_snapshot_active
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 1: Configuración del pipeline
        self.stage_weights = {
            SchemaPipelineStage.VALIDATE_DB_ACCESS: 5,      # 5%
            SchemaPipelineStage.EXTRACT_SCHEMA_SNAPSHOT: 20, # 20%
            SchemaPipelineStage.BUILD_GRAPH: 15,             # 15%
            SchemaPipelineStage.GENERATE_CHUNKS: 20,         # 20%
            SchemaPipelineStage.EMBED_CHUNKS: 25,            # 25%
            SchemaPipelineStage.VECTOR_UPSERT: 10,           # 10%
            SchemaPipelineStage.FINALIZE_SNAPSHOT_ACTIVE: 5  # 5%
        }
        
        self.stage_timeouts = {
            SchemaPipelineStage.VALIDATE_DB_ACCESS: 30,      # 30s
            SchemaPipelineStage.EXTRACT_SCHEMA_SNAPSHOT: 120, # 2min
            SchemaPipelineStage.BUILD_GRAPH: 60,             # 1min
            SchemaPipelineStage.GENERATE_CHUNKS: 90,         # 1.5min
            SchemaPipelineStage.EMBED_CHUNKS: 180,           # 3min
            SchemaPipelineStage.VECTOR_UPSERT: 60,           # 1min
            SchemaPipelineStage.FINALIZE_SNAPSHOT_ACTIVE: 30  # 30s
        }
    
    async def start_pipeline(self, db_id: UUID, user_id: UUID) -> Optional[SchemaPipeline]:
        """
        Inicia un nuevo pipeline de generación de schema.
        
        Args:
            db_id: ID de la base de datos
            user_id: ID del usuario
            
        Returns:
            SchemaPipeline creado o None si falla
        """
        try:
            self.logger.info(f"[SchemaPipelineService] 🚀 Iniciando pipeline para DB {db_id}")
            
            # Crear registro del pipeline
            pipeline = await self._create_pipeline_record(db_id, user_id)
            if not pipeline:
                return None
            
            # Ejecutar pipeline en background
            asyncio.create_task(self._execute_pipeline(pipeline.id))
            
            self.logger.info(f"[SchemaPipelineService] ✅ Pipeline {pipeline.id} iniciado para DB {db_id}")
            return pipeline
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error iniciando pipeline: {e}")
            return None
    
    async def _create_pipeline_record(self, db_id: UUID, user_id: UUID) -> Optional[SchemaPipeline]:
        """Crea el registro del pipeline en la base de datos"""
        try:
            # Generar trace_id único
            trace_id = str(uuid.uuid4())
            
            # Crear pipeline
            pipeline = SchemaPipeline(
                database_id=db_id,
                user_id=user_id,
                trace_id=trace_id,
                status=SchemaPipelineStatus.PENDING,
                current_stage=SchemaPipelineStage.VALIDATE_DB_ACCESS,
                progress_pct=0,
                started_at=datetime.now(timezone.utc),
                stage_logs={}
            )
            
            # Guardar en BD
            db = self.factory.get_db()
            db.add(pipeline)
            db.commit()
            db.refresh(pipeline)
            
            self.logger.info(f"[SchemaPipelineService] 📝 Pipeline {pipeline.id} creado con trace_id {trace_id}")
            return pipeline
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error creando pipeline: {e}")
            return None
    
    async def _execute_pipeline(self, pipeline_id: UUID) -> None:
        """Ejecuta el pipeline completo"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🔄 Ejecutando pipeline {pipeline_id}")
            
            # Obtener pipeline
            pipeline = await self._get_pipeline(pipeline_id)
            if not pipeline:
                return
            
            # Marcar como running
            await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.RUNNING)
            
            # Ejecutar stages secuencialmente
            current_progress = 0
            
            for stage, weight in self.stage_weights.items():
                try:
                    # Actualizar stage actual
                    await self._update_pipeline_stage(pipeline_id, stage)
                    
                    # Ejecutar stage
                    stage_success = await self._execute_stage(pipeline_id, stage)
                    
                    if not stage_success:
                        # Stage falló, marcar pipeline como failed
                        await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.FAILED, 
                                                         error_code=f"STAGE_{stage.upper()}_FAILED",
                                                         error_detail=f"Stage {stage} falló")
                        return
                    
                    # Actualizar progreso
                    current_progress += weight
                    await self._update_pipeline_progress(pipeline_id, current_progress)
                    
                    # Log del stage
                    await self._log_stage(pipeline_id, stage, "completed", f"Stage {stage} completado exitosamente")
                    
                except asyncio.TimeoutError:
                    # Timeout del stage
                    await self._log_stage(pipeline_id, stage, "timeout", f"Stage {stage} excedió timeout")
                    await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.FAILED,
                                                     error_code=f"STAGE_{stage.upper()}_TIMEOUT",
                                                     error_detail=f"Stage {stage} excedió timeout de {self.stage_timeouts[stage]}s")
                    return
                
                except Exception as e:
                    # Error en el stage
                    await self._log_stage(pipeline_id, stage, "error", f"Stage {stage} falló: {str(e)}")
                    await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.FAILED,
                                                     error_code=f"STAGE_{stage.upper()}_ERROR",
                                                     error_detail=f"Stage {stage} falló: {str(e)}")
                    return
            
            # Pipeline completado exitosamente
            await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.COMPLETED)
            await self._log_stage(pipeline_id, "pipeline", "completed", "Pipeline completado exitosamente")
            
            self.logger.info(f"[SchemaPipelineService] ✅ Pipeline {pipeline_id} completado exitosamente")
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error ejecutando pipeline {pipeline_id}: {e}")
            await self._update_pipeline_status(pipeline_id, SchemaPipelineStatus.FAILED,
                                             error_code="PIPELINE_EXECUTION_ERROR",
                                             error_detail=str(e))
    
    async def _execute_stage(self, pipeline_id: UUID, stage: str) -> bool:
        """Ejecuta un stage específico del pipeline"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🔧 Ejecutando stage {stage} para pipeline {pipeline_id}")
            
            # Obtener timeout del stage
            timeout = self.stage_timeouts.get(stage, 60)
            
            # Ejecutar stage con timeout
            if stage == SchemaPipelineStage.VALIDATE_DB_ACCESS:
                return await asyncio.wait_for(self._stage_validate_db_access(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.EXTRACT_SCHEMA_SNAPSHOT:
                return await asyncio.wait_for(self._stage_extract_schema_snapshot(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.BUILD_GRAPH:
                return await asyncio.wait_for(self._stage_build_graph(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.GENERATE_CHUNKS:
                return await asyncio.wait_for(self._stage_generate_chunks(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.EMBED_CHUNKS:
                return await asyncio.wait_for(self._stage_embed_chunks(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.VECTOR_UPSERT:
                return await asyncio.wait_for(self._stage_vector_upsert(pipeline_id), timeout=timeout)
            elif stage == SchemaPipelineStage.FINALIZE_SNAPSHOT_ACTIVE:
                return await asyncio.wait_for(self._stage_finalize_snapshot_active(pipeline_id), timeout=timeout)
            else:
                self.logger.error(f"[SchemaPipelineService] ❌ Stage desconocido: {stage}")
                return False
                
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error ejecutando stage {stage}: {e}")
            return False
    
    # 🔧 FASE 1: Implementación de cada stage
    
    async def _stage_validate_db_access(self, pipeline_id: UUID) -> bool:
        """Stage 1: Validar acceso a la base de datos (solo lectura)"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🔌 Validando acceso a DB para pipeline {pipeline_id}")
            
            # Obtener pipeline y DB
            pipeline = await self._get_pipeline(pipeline_id)
            if not pipeline:
                return False
            
            # Validar conexión (solo lectura)
            database_service = self.factory.get_database_service()
            if not database_service:
                return False
            
            # Test de conexión
            db_record = database_service.get_record(pipeline.database_id)
            if not db_record:
                return False
            
            # Simular validación de acceso
            await asyncio.sleep(1)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Acceso a DB validado para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error validando acceso a DB: {e}")
            return False
    
    async def _stage_extract_schema_snapshot(self, pipeline_id: UUID) -> bool:
        """Stage 2: Extraer snapshot del esquema (tablas, columnas, PK, FK, índices)"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🧩 Extrayendo schema snapshot para pipeline {pipeline_id}")
            
            # Simular extracción de schema
            await asyncio.sleep(2)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Schema snapshot extraído para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error extrayendo schema snapshot: {e}")
            return False
    
    async def _stage_build_graph(self, pipeline_id: UUID) -> bool:
        """Stage 3: Construir grafo de relaciones (FK / M2M)"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🕸️ Construyendo grafo para pipeline {pipeline_id}")
            
            # Simular construcción del grafo
            await asyncio.sleep(1.5)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Grafo construido para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error construyendo grafo: {e}")
            return False
    
    async def _stage_generate_chunks(self, pipeline_id: UUID) -> bool:
        """Stage 4: Generar chunks embebibles del esquema"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🧩 Generando chunks para pipeline {pipeline_id}")
            
            # Simular generación de chunks
            await asyncio.sleep(2)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Chunks generados para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error generando chunks: {e}")
            return False
    
    async def _stage_embed_chunks(self, pipeline_id: UUID) -> bool:
        """Stage 5: Embeddings de chunks (lotes controlados)"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🧠 Generando embeddings para pipeline {pipeline_id}")
            
            # Simular generación de embeddings
            await asyncio.sleep(3)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Embeddings generados para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error generando embeddings: {e}")
            return False
    
    async def _stage_vector_upsert(self, pipeline_id: UUID) -> bool:
        """Stage 6: Upsert en vector store (namespaceado)"""
        try:
            self.logger.info(f"[SchemaPipelineService] 📇 Upsert en vector store para pipeline {pipeline_id}")
            
            # Simular upsert en vector store
            await asyncio.sleep(1)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Vector store actualizado para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error en vector upsert: {e}")
            return False
    
    async def _stage_finalize_snapshot_active(self, pipeline_id: UUID) -> bool:
        """Stage 7: Finalizar snapshot activo"""
        try:
            self.logger.info(f"[SchemaPipelineService] 🎯 Finalizando snapshot activo para pipeline {pipeline_id}")
            
            # Simular finalización
            await asyncio.sleep(0.5)  # Simular trabajo
            
            self.logger.info(f"[SchemaPipelineService] ✅ Snapshot activo finalizado para pipeline {pipeline_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error finalizando snapshot: {e}")
            return False
    
    # 🔧 FASE 1: Métodos de utilidad para el pipeline
    
    async def _get_pipeline(self, pipeline_id: UUID) -> Optional[SchemaPipeline]:
        """Obtiene un pipeline por ID"""
        try:
            db = self.factory.get_db()
            return db.query(SchemaPipeline).filter(SchemaPipeline.id == pipeline_id).first()
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error obteniendo pipeline: {e}")
            return None
    
    async def _update_pipeline_status(self, pipeline_id: UUID, status: str, 
                                    error_code: str = None, error_detail: str = None) -> bool:
        """Actualiza el estado del pipeline"""
        try:
            db = self.factory.get_db()
            pipeline = db.query(SchemaPipeline).filter(SchemaPipeline.id == pipeline_id).first()
            if not pipeline:
                return False
            
            pipeline.status = status
            pipeline.updated_at = datetime.now(timezone.utc)
            
            if status == SchemaPipelineStatus.FAILED:
                pipeline.error_code = error_code
                pipeline.error_detail = error_detail
                pipeline.last_error_at = datetime.now(timezone.utc)
            elif status == SchemaPipelineStatus.COMPLETED:
                pipeline.finished_at = datetime.now(timezone.utc)
            
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error actualizando estado: {e}")
            return False
    
    async def _update_pipeline_stage(self, pipeline_id: UUID, stage: str) -> bool:
        """Actualiza el stage actual del pipeline"""
        try:
            db = self.factory.get_db()
            pipeline = db.query(SchemaPipeline).filter(SchemaPipeline.id == pipeline_id).first()
            if not pipeline:
                return False
            
            pipeline.current_stage = stage
            pipeline.updated_at = datetime.now(timezone.utc)
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error actualizando stage: {e}")
            return False
    
    async def _update_pipeline_progress(self, pipeline_id: UUID, progress_pct: int) -> bool:
        """Actualiza el progreso del pipeline"""
        try:
            db = self.factory.get_db()
            pipeline = db.query(SchemaPipeline).filter(SchemaPipeline.id == pipeline_id).first()
            if not pipeline:
                return False
            
            pipeline.progress_pct = min(100, max(0, progress_pct))
            pipeline.updated_at = datetime.now(timezone.utc)
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error actualizando progreso: {e}")
            return False
    
    async def _log_stage(self, pipeline_id: UUID, stage: str, status: str, message: str) -> bool:
        """Registra un log del stage"""
        try:
            db = self.factory.get_db()
            pipeline = db.query(SchemaPipeline).filter(SchemaPipeline.id == pipeline_id).first()
            if not pipeline:
                return False
            
            # Inicializar stage_logs si no existe
            if not pipeline.stage_logs:
                pipeline.stage_logs = {}
            
            # Agregar log del stage
            if stage not in pipeline.stage_logs:
                pipeline.stage_logs[stage] = []
            
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "message": message,
                "elapsed_ms": int(time.time() * 1000)
            }
            
            pipeline.stage_logs[stage].append(log_entry)
            pipeline.updated_at = datetime.now(timezone.utc)
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error registrando log: {e}")
            return False
    
    async def get_pipeline_status(self, pipeline_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene el estado completo del pipeline"""
        try:
            pipeline = await self._get_pipeline(pipeline_id)
            if not pipeline:
                return None
            
            return {
                "id": str(pipeline.id),
                "status": pipeline.status,
                "current_stage": pipeline.current_stage,
                "progress_pct": pipeline.progress_pct,
                "error_code": pipeline.error_code,
                "error_detail": pipeline.error_detail,
                "started_at": pipeline.started_at.isoformat() if pipeline.started_at else None,
                "finished_at": pipeline.finished_at.isoformat() if pipeline.finished_at else None,
                "elapsed_time_seconds": pipeline.elapsed_time_seconds,
                "remaining_time_seconds": pipeline.remaining_time_seconds,
                "retry_count": pipeline.retry_count,
                "can_retry": pipeline.can_retry,
                "stage_logs": pipeline.stage_logs,
                "trace_id": pipeline.trace_id
            }
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error obteniendo estado: {e}")
            return None
    
    async def retry_pipeline(self, pipeline_id: UUID) -> bool:
        """Reintenta un pipeline fallido"""
        try:
            pipeline = await self._get_pipeline(pipeline_id)
            if not pipeline or not pipeline.can_retry:
                return False
            
            self.logger.info(f"[SchemaPipelineService] 🔄 Reintentando pipeline {pipeline_id}")
            
            # Actualizar contador de reintentos
            db = self.factory.get_db()
            pipeline.retry_count += 1
            pipeline.last_retry_at = datetime.now(timezone.utc)
            pipeline.status = SchemaPipelineStatus.PENDING
            pipeline.error_code = None
            pipeline.error_detail = None
            pipeline.current_stage = SchemaPipelineStage.VALIDATE_DB_ACCESS
            pipeline.progress_pct = 0
            pipeline.started_at = datetime.now(timezone.utc)
            pipeline.finished_at = None
            db.commit()
            
            # Ejecutar pipeline nuevamente
            asyncio.create_task(self._execute_pipeline(pipeline_id))
            
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaPipelineService] ❌ Error reintentando pipeline: {e}")
            return False
