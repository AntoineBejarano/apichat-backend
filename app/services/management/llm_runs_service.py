"""
🔧 FASE 6: Servicio para LLM Runs (LangSmith integration)
──────────────────────────────────────────────────────────
Servicio para gestionar el almacenamiento y consulta de LLM runs.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models.llm_runs_model import LLMRun
from app.schemas.llm_runs_schema import LLMRunCreate, LLMRunUpdate, LLMRunStats
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class LLMRunsService(BaseService):
    """Servicio para gestionar LLM runs con trazabilidad completa."""
    
    def __init__(self, factory):
        super().__init__(factory)
        logger.info("[LLMRunsService] 🚀 Inicializado para trazabilidad de LLM")
    
    async def create_llm_run(self, llm_run_data: LLMRunCreate) -> Optional[LLMRun]:
        """Crea un nuevo LLM run en la base de datos."""
        try:
            llm_run = LLMRun(**llm_run_data.model_dump())
            self.db.add(llm_run)
            self.db.commit()
            self.db.refresh(llm_run)
            
            logger.info(f"[LLMRunsService] ✅ LLM run creado: {llm_run.id}")
            return llm_run
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"[LLMRunsService] ❌ Error creando LLM run: {e}")
            return None
    
    async def update_llm_run(self, run_id: UUID, update_data: LLMRunUpdate) -> Optional[LLMRun]:
        """Actualiza un LLM run existente."""
        try:
            llm_run = self.db.query(LLMRun).filter(LLMRun.id == run_id).first()
            if not llm_run:
                logger.warning(f"[LLMRunsService] ⚠️ LLM run no encontrado: {run_id}")
                return None
            
            # Actualizar solo los campos proporcionados
            for field, value in update_data.model_dump(exclude_unset=True).items():
                setattr(llm_run, field, value)
            
            self.db.commit()
            self.db.refresh(llm_run)
            
            logger.info(f"[LLMRunsService] ✅ LLM run actualizado: {run_id}")
            return llm_run
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"[LLMRunsService] ❌ Error actualizando LLM run: {e}")
            return None
    
    async def get_llm_run(self, run_id: UUID) -> Optional[LLMRun]:
        """Obtiene un LLM run por ID."""
        try:
            return self.db.query(LLMRun).filter(LLMRun.id == run_id).first()
        except SQLAlchemyError as e:
            logger.error(f"[LLMRunsService] ❌ Error obteniendo LLM run: {e}")
            return None
    
    async def get_llm_runs_by_chat(self, chat_id: UUID, limit: int = 50, offset: int = 0) -> List[LLMRun]:
        """Obtiene LLM runs de un chat específico."""
        try:
            return self.db.query(LLMRun)\
                .filter(LLMRun.chat_id == chat_id)\
                .order_by(desc(LLMRun.created_at))\
                .offset(offset)\
                .limit(limit)\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"[LLMRunsService] ❌ Error obteniendo LLM runs del chat: {e}")
            return []
    
    async def get_llm_runs_by_user(self, user_id: UUID, limit: int = 100, offset: int = 0) -> List[LLMRun]:
        """Obtiene LLM runs de un usuario específico."""
        try:
            return self.db.query(LLMRun)\
                .filter(LLMRun.user_id == user_id)\
                .order_by(desc(LLMRun.created_at))\
                .offset(offset)\
                .limit(limit)\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"[LLMRunsService] ❌ Error obteniendo LLM runs del usuario: {e}")
            return []
    
    async def get_llm_runs_stats(self, user_id: Optional[UUID] = None, chat_id: Optional[UUID] = None) -> Optional[LLMRunStats]:
        """Obtiene estadísticas de LLM runs."""
        try:
            query = self.db.query(LLMRun)
            
            # Aplicar filtros si se proporcionan
            if user_id:
                query = query.filter(LLMRun.user_id == user_id)
            if chat_id:
                query = query.filter(LLMRun.chat_id == chat_id)
            
            # Calcular estadísticas
            total_runs = query.count()
            successful_runs = query.filter(LLMRun.status == "success").count()
            failed_runs = query.filter(LLMRun.status == "error").count()
            
            # Calcular tokens totales
            tokens_result = query.with_entities(func.sum(LLMRun.total_tokens)).scalar()
            total_tokens = tokens_result or 0
            
            # Calcular tiempo de respuesta promedio
            avg_time_result = query.with_entities(func.avg(LLMRun.response_time_ms)).scalar()
            avg_response_time_ms = float(avg_time_result) if avg_time_result else 0.0
            
            # Calcular tasa de éxito
            success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
            
            return LLMRunStats(
                total_runs=total_runs,
                successful_runs=successful_runs,
                failed_runs=failed_runs,
                total_tokens=total_tokens,
                avg_response_time_ms=avg_response_time_ms,
                success_rate=success_rate
            )
            
        except SQLAlchemyError as e:
            logger.error(f"[LLMRunsService] ❌ Error calculando estadísticas: {e}")
            return None
    
    async def mark_sql_executed(self, run_id: UUID, executed: bool = True) -> bool:
        """Marca un LLM run como SQL ejecutado."""
        try:
            llm_run = self.db.query(LLMRun).filter(LLMRun.id == run_id).first()
            if not llm_run:
                logger.warning(f"[LLMRunsService] ⚠️ LLM run no encontrado para marcar SQL ejecutado: {run_id}")
                return False
            
            llm_run.sql_executed = executed
            self.db.commit()
            
            logger.info(f"[LLMRunsService] ✅ LLM run marcado como SQL ejecutado: {run_id}")
            return True
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"[LLMRunsService] ❌ Error marcando SQL ejecutado: {e}")
            return False
    
    async def get_failed_sql_runs(self, limit: int = 20) -> List[LLMRun]:
        """Obtiene LLM runs donde falló la generación de SQL."""
        try:
            return self.db.query(LLMRun)\
                .filter(
                    or_(
                        LLMRun.status == "error",
                        and_(LLMRun.sql_generated.isnot(None), LLMRun.sql_validated == False)
                    )
                )\
                .order_by(desc(LLMRun.created_at))\
                .limit(limit)\
                .all()
        except SQLAlchemyError as e:
            logger.error(f"[LLMRunsService] ❌ Error obteniendo runs fallidos: {e}")
            return []
