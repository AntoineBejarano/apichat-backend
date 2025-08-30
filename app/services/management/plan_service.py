"""
PlanService - Servicio para gestión de planes y to-dos.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc

from app.models.plan_model import UserPlan, PlanTask, PlanExecutionState, PlanOutcome
from app.schemas.plan_schema import (
    UserPlanCreate, UserPlanUpdate, UserPlanOut,
    PlanTaskCreate, PlanTaskUpdate, PlanTaskOut,
    PlanExecutionStateCreate, PlanExecutionStateUpdate, PlanExecutionStateOut,
    PlanOutcomeCreate, PlanOutcomeOut,
    PlanQuery, PlanListResponse,
    PlanStatus, TaskStatus, ExecutionStatus
)

logger = logging.getLogger(__name__)


class PlanService:
    """Servicio para gestión de planes y to-dos."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    # ===== OPERACIONES DE PLANES =====
    
    async def create_plan(self, plan_data: UserPlanCreate, user_id: UUID) -> UserPlanOut:
        """Crea un nuevo plan para el usuario."""
        try:
            logger.info(f"[PlanService] 🚀 Creando plan: {plan_data.title}")
            
            # Crear plan en la base de datos
            plan = UserPlan(
                user_id=user_id,
                title=plan_data.title,
                description=plan_data.description,
                priority=plan_data.priority,
                estimated_duration=plan_data.estimated_duration,
                plan_metadata=plan_data.plan_metadata,
                status=PlanStatus.DRAFT
            )
            
            self.db.add(plan)
            self.db.commit()
            self.db.refresh(plan)
            
            logger.info(f"[PlanService] ✅ Plan creado: {plan.id}")
            return UserPlanOut.from_orm(plan)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error creando plan: {e}")
            self.db.rollback()
            raise
    
    async def get_plan(self, plan_id: UUID, user_id: UUID) -> Optional[UserPlanOut]:
        """Obtiene un plan específico del usuario."""
        try:
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return None
            
            return UserPlanOut.from_orm(plan)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error obteniendo plan: {e}")
            raise
    
    async def update_plan(self, plan_id: UUID, user_id: UUID, plan_data: UserPlanUpdate) -> Optional[UserPlanOut]:
        """Actualiza un plan existente."""
        try:
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return None
            
            # Actualizar campos
            update_data = plan_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(plan, field, value)
            
            plan.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(plan)
            
            logger.info(f"[PlanService] ✅ Plan actualizado: {plan.id}")
            return UserPlanOut.from_orm(plan)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error actualizando plan: {e}")
            self.db.rollback()
            raise
    
    async def delete_plan(self, plan_id: UUID, user_id: UUID) -> bool:
        """Elimina un plan y todas sus tareas."""
        try:
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return False
            
            self.db.delete(plan)
            self.db.commit()
            
            logger.info(f"[PlanService] ✅ Plan eliminado: {plan_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error eliminando plan: {e}")
            self.db.rollback()
            raise
    
    async def list_plans(self, user_id: UUID, query: PlanQuery) -> PlanListResponse:
        """Lista los planes del usuario con filtros."""
        try:
            # Construir query base
            db_query = self.db.query(UserPlan).filter(UserPlan.user_id == user_id)
            
            # Aplicar filtros
            if query.status:
                db_query = db_query.filter(UserPlan.status == query.status)
            
            if query.priority:
                db_query = db_query.filter(UserPlan.priority == query.priority)
            
            # Contar total
            total = db_query.count()
            
            # Aplicar paginación y ordenamiento
            plans = db_query.order_by(desc(UserPlan.created_at)).offset(query.offset).limit(query.limit).all()
            
            # Convertir a schemas
            plan_outs = [UserPlanOut.from_orm(plan) for plan in plans]
            
            return PlanListResponse(
                plans=plan_outs,
                total=total,
                limit=query.limit,
                offset=query.offset
            )
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error listando planes: {e}")
            raise
    
    # ===== OPERACIONES DE TAREAS =====
    
    async def create_task(self, plan_id: UUID, user_id: UUID, task_data: PlanTaskCreate) -> Optional[PlanTaskOut]:
        """Crea una nueva tarea en un plan."""
        try:
            # Verificar que el plan existe y pertenece al usuario
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return None
            
            # Crear tarea
            task = PlanTask(
                plan_id=plan_id,
                title=task_data.title,
                description=task_data.description,
                order_index=task_data.order_index,
                estimated_effort=task_data.estimated_effort,
                dependencies=task_data.dependencies,
                status=TaskStatus.PENDING
            )
            
            self.db.add(task)
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"[PlanService] ✅ Tarea creada: {task.id}")
            return PlanTaskOut.from_orm(task)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error creando tarea: {e}")
            self.db.rollback()
            raise
    
    async def update_task(self, task_id: UUID, user_id: UUID, task_data: PlanTaskUpdate) -> Optional[PlanTaskOut]:
        """Actualiza una tarea existente."""
        try:
            # Verificar que la tarea existe y pertenece al usuario
            task = self.db.query(PlanTask).join(UserPlan).filter(
                and_(
                    PlanTask.id == task_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not task:
                return None
            
            # Actualizar campos
            update_data = task_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(task, field, value)
            
            # Actualizar timestamps según el estado
            if task_data.status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            elif task_data.status in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED] and not task.completed_at:
                task.completed_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(task)
            
            logger.info(f"[PlanService] ✅ Tarea actualizada: {task.id}")
            return PlanTaskOut.from_orm(task)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error actualizando tarea: {e}")
            self.db.rollback()
            raise
    
    async def get_plan_tasks(self, plan_id: UUID, user_id: UUID) -> List[PlanTaskOut]:
        """Obtiene todas las tareas de un plan."""
        try:
            # Verificar que el plan existe y pertenece al usuario
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return []
            
            # Obtener tareas ordenadas por order_index
            tasks = self.db.query(PlanTask).filter(
                PlanTask.plan_id == plan_id
            ).order_by(asc(PlanTask.order_index)).all()
            
            return [PlanTaskOut.from_orm(task) for task in tasks]
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error obteniendo tareas: {e}")
            raise
    
    # ===== OPERACIONES DE ESTADO DE EJECUCIÓN =====
    
    async def create_execution_state(self, plan_id: UUID, user_id: UUID, state_data: PlanExecutionStateCreate) -> Optional[PlanExecutionStateOut]:
        """Crea un nuevo estado de ejecución para un plan."""
        try:
            # Verificar que el plan existe y pertenece al usuario
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return None
            
            # Crear estado de ejecución
            execution_state = PlanExecutionState(
                plan_id=plan_id,
                run_id=state_data.run_id,
                redis_key=state_data.redis_key,
                current_task_index=state_data.current_task_index,
                execution_metadata=state_data.execution_metadata,
                status=ExecutionStatus.INITIALIZED
            )
            
            self.db.add(execution_state)
            self.db.commit()
            self.db.refresh(execution_state)
            
            logger.info(f"[PlanService] ✅ Estado de ejecución creado: {execution_state.id}")
            return PlanExecutionStateOut.from_orm(execution_state)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error creando estado de ejecución: {e}")
            self.db.rollback()
            raise
    
    async def update_execution_state(self, execution_id: UUID, user_id: UUID, state_data: PlanExecutionStateUpdate) -> Optional[PlanExecutionStateOut]:
        """Actualiza el estado de ejecución."""
        try:
            # Verificar que el estado existe y pertenece al usuario
            execution_state = self.db.query(PlanExecutionState).join(UserPlan).filter(
                and_(
                    PlanExecutionState.id == execution_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not execution_state:
                return None
            
            # Actualizar campos
            update_data = state_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(execution_state, field, value)
            
            execution_state.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(execution_state)
            
            logger.info(f"[PlanService] ✅ Estado de ejecución actualizado: {execution_state.id}")
            return PlanExecutionStateOut.from_orm(execution_state)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error actualizando estado de ejecución: {e}")
            self.db.rollback()
            raise
    
    # ===== OPERACIONES DE RESULTADOS =====
    
    async def create_plan_outcome(self, plan_id: UUID, user_id: UUID, outcome_data: PlanOutcomeCreate) -> Optional[PlanOutcomeOut]:
        """Crea un resultado para un plan completado."""
        try:
            # Verificar que el plan existe y pertenece al usuario
            plan = self.db.query(UserPlan).filter(
                and_(
                    UserPlan.id == plan_id,
                    UserPlan.user_id == user_id
                )
            ).first()
            
            if not plan:
                return None
            
            # Crear resultado
            outcome = PlanOutcome(
                plan_id=plan_id,
                total_tasks=outcome_data.total_tasks,
                completed_tasks=outcome_data.completed_tasks,
                failed_tasks=outcome_data.failed_tasks,
                skipped_tasks=outcome_data.skipped_tasks,
                total_estimated_time=outcome_data.total_estimated_time,
                total_actual_time=outcome_data.total_actual_time,
                success_rate=outcome_data.success_rate,
                outcome_summary=outcome_data.outcome_summary,
                execution_metadata=outcome_data.execution_metadata
            )
            
            self.db.add(outcome)
            self.db.commit()
            self.db.refresh(outcome)
            
            logger.info(f"[PlanService] ✅ Resultado de plan creado: {outcome.id}")
            return PlanOutcomeOut.from_orm(outcome)
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error creando resultado: {e}")
            self.db.rollback()
            raise
    
    # ===== MÉTODOS DE UTILIDAD =====
    
    async def get_plan_statistics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene estadísticas de planes del usuario."""
        try:
            # Contar planes por estado
            status_counts = {}
            for status in PlanStatus:
                count = self.db.query(UserPlan).filter(
                    and_(
                        UserPlan.user_id == user_id,
                        UserPlan.status == status
                    )
                ).count()
                status_counts[status.value] = count
            
            # Contar tareas por estado
            task_status_counts = {}
            for status in TaskStatus:
                count = self.db.query(PlanTask).join(UserPlan).filter(
                    and_(
                        UserPlan.user_id == user_id,
                        PlanTask.status == status
                    )
                ).count()
                task_status_counts[status.value] = count
            
            # Tiempo total estimado vs real
            total_estimated = self.db.query(UserPlan).filter(
                UserPlan.user_id == user_id
            ).with_entities(UserPlan.estimated_duration).all()
            
            total_actual = self.db.query(UserPlan).filter(
                UserPlan.user_id == user_id
            ).with_entities(UserPlan.actual_duration).all()
            
            estimated_sum = sum(duration[0] for duration in total_estimated if duration[0])
            actual_sum = sum(duration[0] for duration in total_actual if duration[0])
            
            return {
                "plans_by_status": status_counts,
                "tasks_by_status": task_status_counts,
                "total_estimated_time": estimated_sum or 0,
                "total_actual_time": actual_sum or 0,
                "efficiency_rate": (actual_sum / estimated_sum * 100) if estimated_sum > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error obteniendo estadísticas: {e}")
            raise
    
    # ===== MÉTODOS PARA OUTCOMES Y MÉTRICAS =====
    
    async def get_user_plan_outcomes(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[PlanOutcomeOut]:
        """Obtiene los resultados de planes del usuario."""
        try:
            outcomes = self.db.query(PlanOutcome).join(UserPlan).filter(
                UserPlan.user_id == user_id
            ).order_by(desc(PlanOutcome.created_at)).offset(offset).limit(limit).all()
            
            return [PlanOutcomeOut.from_orm(outcome) for outcome in outcomes]
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error obteniendo resultados: {e}")
            return []
    
    async def update_task_metrics(
        self,
        task_id: UUID,
        user_id: UUID,
        metrics: Dict[str, Any]
    ) -> bool:
        """Actualiza métricas de una tarea."""
        try:
            task = self.db.query(PlanTask).join(UserPlan).filter(
                and_(PlanTask.id == task_id, UserPlan.user_id == user_id)
            ).first()
            
            if not task:
                return False
            
            # Actualizar métricas
            if "execution_time" in metrics:
                task.actual_effort = int(metrics["execution_time"])
            
            if "success" in metrics:
                task.status = TaskStatus.DONE if metrics["success"] else TaskStatus.FAILED
            
            if "error_message" in metrics:
                task.errors = [metrics["error_message"]]
            
            if "result_data" in metrics:
                task.outcome = metrics["result_data"]
            
            if "completed_at" in metrics:
                task.completed_at = datetime.fromisoformat(metrics["completed_at"].replace('Z', '+00:00'))
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error actualizando métricas: {e}")
            self.db.rollback()
            return False
    
    async def update_plan_metadata(
        self,
        plan_id: UUID,
        user_id: UUID,
        metadata: Dict[str, Any]
    ) -> bool:
        """Actualiza metadatos de un plan."""
        try:
            plan = self.db.query(UserPlan).filter(
                and_(UserPlan.id == plan_id, UserPlan.user_id == user_id)
            ).first()
            
            if not plan:
                return False
            
            # Fusionar metadatos existentes con nuevos
            existing_metadata = plan.plan_metadata or {}
            existing_metadata.update(metadata)
            plan.plan_metadata = existing_metadata
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"[PlanService] ❌ Error actualizando metadatos: {e}")
            self.db.rollback()
            return False
