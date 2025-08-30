"""
PlanExecutionService - Servicio para ejecutar planes paso a paso.
Maneja el estado de ejecución en Redis y la persistencia en DB.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timezone
from enum import Enum

from app.services.management.plan_service import PlanService
from app.services.execution.plan_outcome_service import PlanOutcomeService, PlanExecutionMetrics, TaskExecutionMetrics
from app.schemas.plan_schema import (
    PlanExecutionRequest, PlanExecutionResponse, TaskExecutionUpdate,
    PlanStatus, TaskStatus, ExecutionStatus
)
from app.models.plan_model import UserPlan, PlanTask, PlanExecutionState

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Resultado de la ejecución de una tarea."""
    
    def __init__(
        self,
        task_id: UUID,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        execution_time: Optional[float] = None
    ):
        self.task_id = task_id
        self.success = success
        self.result = result or {}
        self.error = error
        self.execution_time = execution_time


class PlanExecutionService:
    """Servicio para ejecutar planes paso a paso con seguimiento en tiempo real."""
    
    def __init__(self, factory=None):
        self.factory = factory
        self.plan_service = None
        self.redis_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Inicializa los servicios necesarios."""
        if self.factory:
            self.plan_service = self.factory.get_plan_service()
            self.outcome_service = PlanOutcomeService(self.factory)
            # TODO: Agregar Redis service cuando esté disponible
            # self.redis_service = self.factory.get_redis_service()
    
    async def start_plan_execution(
        self,
        plan_id: UUID,
        user_id: UUID,
        auto_confirm: bool = False,
        start_from_task: Optional[int] = None
    ) -> PlanExecutionResponse:
        """
        Inicia la ejecución de un plan.
        
        Args:
            plan_id: ID del plan a ejecutar
            user_id: ID del usuario
            auto_confirm: Si confirmar automáticamente las tareas
            start_from_task: Índice de tarea desde la que empezar
            
        Returns:
            PlanExecutionResponse: Respuesta con estado de ejecución
        """
        try:
            logger.info(f"[PlanExecution] 🚀 Iniciando ejecución del plan: {plan_id}")
            
            # 1. Verificar que el plan existe y obtener tareas
            plan = await self.plan_service.get_plan(plan_id, user_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} no encontrado")
            
            tasks = await self.plan_service.get_plan_tasks(plan_id, user_id)
            if not tasks:
                raise ValueError(f"No hay tareas en el plan {plan_id}")
            
            # 2. Crear run_id único para esta ejecución
            run_id = str(uuid4())
            
            # 3. Crear estado de ejecución en Redis
            redis_key = f"plan:{run_id}:execution"
            execution_state = await self._create_execution_state(
                plan_id, user_id, run_id, redis_key, start_from_task or 0
            )
            
            # 4. Actualizar estado del plan a "running"
            await self.plan_service.update_plan(
                plan_id, user_id, 
                {"status": PlanStatus.RUNNING, "started_at": datetime.now(timezone.utc)}
            )
            
            # 5. Iniciar ejecución asíncrona
            asyncio.create_task(self._execute_plan_async(
                plan_id, user_id, run_id, tasks, auto_confirm, start_from_task or 0
            ))
            
            logger.info(f"[PlanExecution] ✅ Ejecución iniciada: {run_id}")
            
            return PlanExecutionResponse(
                execution_id=run_id,
                plan_id=plan_id,
                status=ExecutionStatus.RUNNING,
                current_task_index=start_from_task or 0,
                total_tasks=len(tasks),
                message=f"Ejecución iniciada. Ejecutando {len(tasks)} tareas."
            )
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error iniciando ejecución: {e}")
            raise
    
    async def _create_execution_state(
        self,
        plan_id: UUID,
        user_id: UUID,
        run_id: str,
        redis_key: str,
        current_task_index: int
    ) -> PlanExecutionState:
        """Crea el estado de ejecución en la base de datos."""
        from app.schemas.plan_schema import PlanExecutionStateCreate
        
        state_data = PlanExecutionStateCreate(
            run_id=run_id,
            redis_key=redis_key,
            current_task_index=current_task_index,
            execution_metadata={
                "started_at": datetime.now(timezone.utc).isoformat(),
                "auto_confirm": False,
                "total_tasks": 0  # Se actualizará cuando se obtengan las tareas
            }
        )
        
        return await self.plan_service.create_execution_state(plan_id, user_id, state_data)
    
    async def _execute_plan_async(
        self,
        plan_id: UUID,
        user_id: UUID,
        run_id: str,
        tasks: List[Any],
        auto_confirm: bool,
        start_index: int
    ):
        """Ejecuta el plan de forma asíncrona."""
        try:
            logger.info(f"[PlanExecution] 🔄 Ejecutando plan {plan_id} (run_id: {run_id})")
            
            # Actualizar metadata con total de tareas
            await self._update_execution_metadata(
                run_id, user_id, {"total_tasks": len(tasks)}
            )
            
            completed_tasks = 0
            failed_tasks = 0
            
            # Ejecutar tareas en orden
            for i, task in enumerate(tasks[start_index:], start=start_index):
                try:
                    # Actualizar estado de ejecución
                    await self._update_execution_state(
                        run_id, user_id, i, ExecutionStatus.RUNNING
                    )
                    
                    # Marcar tarea como "running"
                    await self.plan_service.update_task(
                        task.id, user_id,
                        TaskExecutionUpdate(
                            task_id=task.id,
                            status=TaskStatus.RUNNING
                        )
                    )
                    
                    # Ejecutar la tarea
                    result = await self._execute_task(task, user_id, auto_confirm)
                    
                    if result.success:
                        # Marcar tarea como completada
                        await self.plan_service.update_task(
                            task.id, user_id,
                            TaskExecutionUpdate(
                                task_id=task.id,
                                status=TaskStatus.DONE,
                                outcome=result.result,
                                actual_effort=int(result.execution_time or 0)
                            )
                        )
                        completed_tasks += 1
                        logger.info(f"[PlanExecution] ✅ Tarea {i+1}/{len(tasks)} completada: {task.title}")
                    else:
                        # Marcar tarea como fallida
                        await self.plan_service.update_task(
                            task.id, user_id,
                            TaskExecutionUpdate(
                                task_id=task.id,
                                status=TaskStatus.FAILED,
                                errors=[result.error or "Error desconocido"]
                            )
                        )
                        failed_tasks += 1
                        logger.error(f"[PlanExecution] ❌ Tarea {i+1}/{len(tasks)} falló: {task.title} - {result.error}")
                        
                        # Decidir si continuar o parar
                        if not auto_confirm:
                            # Parar ejecución si no es auto-confirmación
                            await self._update_execution_state(
                                run_id, user_id, i, ExecutionStatus.FAILED
                            )
                            break
                
                except Exception as e:
                    logger.error(f"[PlanExecution] ❌ Error ejecutando tarea {i+1}: {e}")
                    failed_tasks += 1
                    
                    # Marcar tarea como fallida
                    await self.plan_service.update_task(
                        task.id, user_id,
                        TaskExecutionUpdate(
                            task_id=task.id,
                            status=TaskStatus.FAILED,
                            errors=[str(e)]
                        )
                    )
                    
                    if not auto_confirm:
                        await self._update_execution_state(
                            run_id, user_id, i, ExecutionStatus.FAILED
                        )
                        break
            
            # Finalizar ejecución
            final_status = ExecutionStatus.COMPLETED if failed_tasks == 0 else ExecutionStatus.FAILED
            await self._update_execution_state(
                run_id, user_id, len(tasks) - 1, final_status
            )
            
            # Actualizar estado del plan
            plan_status = PlanStatus.COMPLETED if failed_tasks == 0 else PlanStatus.FAILED
            await self.plan_service.update_plan(
                plan_id, user_id,
                {
                    "status": plan_status,
                    "completed_at": datetime.now(timezone.utc)
                }
            )
            
            # Crear resultado del plan con métricas detalladas
            await self._create_plan_outcome_with_metrics(
                plan_id, user_id, tasks, completed_tasks, failed_tasks
            )
            
            logger.info(f"[PlanExecution] 🎉 Plan {plan_id} finalizado: {completed_tasks} completadas, {failed_tasks} fallidas")
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error en ejecución asíncrona: {e}")
            await self._update_execution_state(
                run_id, user_id, 0, ExecutionStatus.FAILED
            )
    
    async def _execute_task(
        self,
        task: Any,
        user_id: UUID,
        auto_confirm: bool
    ) -> ExecutionResult:
        """
        Ejecuta una tarea individual.
        
        Args:
            task: Tarea a ejecutar
            user_id: ID del usuario
            auto_confirm: Si confirmar automáticamente
            
        Returns:
            ExecutionResult: Resultado de la ejecución
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"[PlanExecution] 🔧 Ejecutando tarea: {task.title}")
            
            # Simular ejecución basada en el tipo de tarea
            # TODO: Integrar con servicios reales (SQL, APIs, etc.)
            result = await self._simulate_task_execution(task, user_id)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ExecutionResult(
                task_id=task.id,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"[PlanExecution] ❌ Error ejecutando tarea {task.title}: {e}")
            
            return ExecutionResult(
                task_id=task.id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _simulate_task_execution(self, task: Any, user_id: UUID) -> Dict[str, Any]:
        """
        Simula la ejecución de una tarea.
        TODO: Reemplazar con ejecución real basada en el tipo de tarea.
        """
        # Simular tiempo de ejecución
        await asyncio.sleep(1)
        
        # Simular resultado basado en el tipo de tarea
        if "sql" in task.description.lower() or "consulta" in task.description.lower():
            return {
                "type": "sql_execution",
                "rows_affected": 42,
                "execution_time": 1.2,
                "query": "SELECT * FROM users LIMIT 10"
            }
        elif "api" in task.description.lower() or "llamar" in task.description.lower():
            return {
                "type": "api_call",
                "status_code": 200,
                "response_time": 0.8,
                "endpoint": "/api/users"
            }
        else:
            return {
                "type": "general_task",
                "status": "completed",
                "message": f"Tarea '{task.title}' ejecutada exitosamente"
            }
    
    async def _update_execution_state(
        self,
        run_id: str,
        user_id: UUID,
        current_task_index: int,
        status: ExecutionStatus
    ):
        """Actualiza el estado de ejecución."""
        try:
            # TODO: Actualizar en Redis cuando esté disponible
            # await self.redis_service.set_execution_state(run_id, {
            #     "current_task_index": current_task_index,
            #     "status": status.value,
            #     "updated_at": datetime.now(timezone.utc).isoformat()
            # })
            
            # Actualizar en base de datos
            # TODO: Implementar cuando tengamos el método en PlanService
            logger.info(f"[PlanExecution] 📊 Estado actualizado: {run_id} - tarea {current_task_index} - {status.value}")
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error actualizando estado: {e}")
    
    async def _update_execution_metadata(
        self,
        run_id: str,
        user_id: UUID,
        metadata: Dict[str, Any]
    ):
        """Actualiza los metadatos de ejecución."""
        try:
            # TODO: Implementar actualización de metadata
            logger.info(f"[PlanExecution] 📝 Metadata actualizada: {run_id} - {metadata}")
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error actualizando metadata: {e}")
    
    async def _create_plan_outcome_with_metrics(
        self,
        plan_id: UUID,
        user_id: UUID,
        tasks: List[Any],
        completed_tasks: int,
        failed_tasks: int
    ):
        """Crea el resultado del plan con métricas detalladas."""
        try:
            # Obtener información del plan
            plan = await self.plan_service.get_plan(plan_id, user_id)
            if not plan:
                logger.error(f"[PlanExecution] ❌ Plan {plan_id} no encontrado")
                return
            
            # Crear métricas de tareas
            task_metrics = []
            total_execution_time = 0
            
            for task in tasks:
                # Obtener métricas de la tarea desde la base de datos
                task_from_db = await self.plan_service.get_task(task.id, user_id)
                if task_from_db:
                    execution_time = task_from_db.actual_effort or 0
                    total_execution_time += execution_time
                    
                    task_metrics.append(TaskExecutionMetrics(
                        task_id=task.id,
                        task_title=task.title,
                        action_type=getattr(task, 'action_type', 'general'),
                        execution_time=execution_time,
                        success=task_from_db.status == TaskStatus.DONE,
                        error_message=task_from_db.errors[0] if task_from_db.errors else None,
                        result_data=task_from_db.outcome,
                        resource_usage={
                            "memory_usage": 0,  # TODO: Obtener métricas reales
                            "cpu_usage": 0
                        }
                    ))
            
            # Calcular tasa de éxito
            total_tasks = len(tasks)
            success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Crear métricas del plan
            plan_metrics = PlanExecutionMetrics(
                plan_id=plan_id,
                plan_title=plan.title,
                total_tasks=total_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                total_execution_time=total_execution_time,
                success_rate=success_rate,
                task_metrics=task_metrics,
                resource_usage={
                    "total_memory": sum(tm.resource_usage.get("memory_usage", 0) for tm in task_metrics),
                    "total_cpu": sum(tm.resource_usage.get("cpu_usage", 0) for tm in task_metrics),
                    "execution_time": total_execution_time
                },
                patterns_detected=[]  # Se detectarán en el servicio de outcomes
            )
            
            # Persistir resultado usando el servicio de outcomes
            await self.outcome_service.persist_plan_outcome(plan_id, user_id, plan_metrics)
            
            logger.info(f"[PlanExecution] 📊 Resultado persistido: {plan_id} - {success_rate:.1f}% éxito")
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error creando resultado con métricas: {e}")
    
    # ===== MÉTODOS DE CONSULTA =====
    
    async def get_execution_status(
        self,
        run_id: str,
        user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado actual de una ejecución.
        
        Args:
            run_id: ID de la ejecución
            user_id: ID del usuario
            
        Returns:
            Dict con el estado de ejecución o None si no existe
        """
        try:
            # TODO: Obtener de Redis cuando esté disponible
            # redis_state = await self.redis_service.get_execution_state(run_id)
            
            # Por ahora, simular estado
            return {
                "run_id": run_id,
                "status": "running",
                "current_task_index": 2,
                "total_tasks": 5,
                "progress_percentage": 40,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "estimated_completion": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error obteniendo estado: {e}")
            return None
    
    async def pause_execution(
        self,
        run_id: str,
        user_id: UUID
    ) -> bool:
        """
        Pausa la ejecución de un plan.
        
        Args:
            run_id: ID de la ejecución
            user_id: ID del usuario
            
        Returns:
            bool: True si se pausó exitosamente
        """
        try:
            # TODO: Implementar pausa en Redis
            logger.info(f"[PlanExecution] ⏸️ Pausando ejecución: {run_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error pausando ejecución: {e}")
            return False
    
    async def resume_execution(
        self,
        run_id: str,
        user_id: UUID
    ) -> bool:
        """
        Reanuda la ejecución de un plan pausado.
        
        Args:
            run_id: ID de la ejecución
            user_id: ID del usuario
            
        Returns:
            bool: True si se reanudó exitosamente
        """
        try:
            # TODO: Implementar reanudación en Redis
            logger.info(f"[PlanExecution] ▶️ Reanudando ejecución: {run_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error reanudando ejecución: {e}")
            return False
    
    async def cancel_execution(
        self,
        run_id: str,
        user_id: UUID
    ) -> bool:
        """
        Cancela la ejecución de un plan.
        
        Args:
            run_id: ID de la ejecución
            user_id: ID del usuario
            
        Returns:
            bool: True si se canceló exitosamente
        """
        try:
            # TODO: Implementar cancelación en Redis
            logger.info(f"[PlanExecution] 🛑 Cancelando ejecución: {run_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PlanExecution] ❌ Error cancelando ejecución: {e}")
            return False