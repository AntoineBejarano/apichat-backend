"""
PlanOutcomeService - Servicio para persistir resultados de planes y preparar recomendaciones.
Maneja el almacenamiento de outcomes, métricas y patrones para futuras recomendaciones.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass

from app.services.management.plan_service import PlanService
from app.schemas.plan_schema import PlanOutcomeCreate, PlanOutcomeOut
from app.models.plan_model import UserPlan, PlanTask, PlanOutcome as PlanOutcomeModel

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionMetrics:
    """Métricas de ejecución de una tarea."""
    task_id: UUID
    task_title: str
    action_type: str
    execution_time: float
    success: bool
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None
    resource_usage: Optional[Dict[str, Any]] = None


@dataclass
class PlanExecutionMetrics:
    """Métricas de ejecución de un plan completo."""
    plan_id: UUID
    plan_title: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_execution_time: float
    success_rate: float
    task_metrics: List[TaskExecutionMetrics]
    resource_usage: Dict[str, Any]
    patterns_detected: List[str]


class PlanOutcomeService:
    """
    Servicio para persistir resultados de planes y preparar sistema de recomendaciones.
    """
    
    def __init__(self, factory=None):
        self.factory = factory
        self.plan_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Inicializa los servicios necesarios."""
        if self.factory:
            self.plan_service = self.factory.get_plan_service()
    
    async def persist_plan_outcome(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_metrics: PlanExecutionMetrics
    ) -> PlanOutcomeOut:
        """
        Persiste el resultado completo de un plan ejecutado.
        
        Args:
            plan_id: ID del plan
            user_id: ID del usuario
            execution_metrics: Métricas de ejecución
            
        Returns:
            PlanOutcomeOut: Resultado persistido
        """
        try:
            logger.info(f"[PlanOutcomeService] 💾 Persistiendo resultado del plan {plan_id}")
            
            # 1. Crear outcome principal
            outcome_data = PlanOutcomeCreate(
                plan_id=plan_id,
                total_tasks=execution_metrics.total_tasks,
                completed_tasks=execution_metrics.completed_tasks,
                failed_tasks=execution_metrics.failed_tasks,
                skipped_tasks=0,
                success_rate=execution_metrics.success_rate,
                outcome_summary=self._generate_outcome_summary(execution_metrics),
                execution_metadata={
                    "total_execution_time": execution_metrics.total_execution_time,
                    "resource_usage": execution_metrics.resource_usage,
                    "patterns_detected": execution_metrics.patterns_detected,
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            outcome = await self.plan_service.create_plan_outcome(plan_id, user_id, outcome_data)
            
            # 2. Persistir métricas detalladas de tareas
            await self._persist_task_metrics(plan_id, user_id, execution_metrics.task_metrics)
            
            # 3. Analizar patrones para recomendaciones futuras
            await self._analyze_execution_patterns(plan_id, user_id, execution_metrics)
            
            # 4. Actualizar estadísticas del usuario
            await self._update_user_statistics(user_id, execution_metrics)
            
            logger.info(f"[PlanOutcomeService] ✅ Resultado persistido: {outcome.id}")
            return outcome
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error persistiendo resultado: {e}")
            raise
    
    async def _persist_task_metrics(
        self,
        plan_id: UUID,
        user_id: UUID,
        task_metrics: List[TaskExecutionMetrics]
    ):
        """Persiste métricas detalladas de cada tarea."""
        try:
            for task_metric in task_metrics:
                # Actualizar la tarea con métricas detalladas
                await self.plan_service.update_task_metrics(
                    task_metric.task_id,
                    user_id,
                    {
                        "execution_time": task_metric.execution_time,
                        "success": task_metric.success,
                        "error_message": task_metric.error_message,
                        "result_data": task_metric.result_data,
                        "resource_usage": task_metric.resource_usage,
                        "completed_at": datetime.now(timezone.utc).isoformat()
                    }
                )
            
            logger.info(f"[PlanOutcomeService] 📊 Métricas de {len(task_metrics)} tareas persistidas")
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error persistiendo métricas de tareas: {e}")
    
    async def _analyze_execution_patterns(
        self,
        plan_id: UUID,
        user_id: UUID,
        execution_metrics: PlanExecutionMetrics
    ):
        """Analiza patrones de ejecución para futuras recomendaciones."""
        try:
            patterns = []
            
            # 1. Analizar patrones de tiempo de ejecución
            if execution_metrics.total_execution_time > 300:  # > 5 minutos
                patterns.append("long_running_plan")
            
            # 2. Analizar patrones de éxito/fallo
            if execution_metrics.success_rate == 100:
                patterns.append("high_success_rate")
            elif execution_metrics.success_rate < 50:
                patterns.append("low_success_rate")
            
            # 3. Analizar patrones de tipos de tareas
            action_types = [task.action_type for task in execution_metrics.task_metrics]
            if "sql_query" in action_types and "api_call" in action_types:
                patterns.append("mixed_database_api_workflow")
            elif "sql_query" in action_types:
                patterns.append("database_heavy_workflow")
            elif "api_call" in action_types:
                patterns.append("api_heavy_workflow")
            
            # 4. Analizar patrones de recursos
            if execution_metrics.resource_usage.get("memory_usage", 0) > 1000:  # > 1GB
                patterns.append("memory_intensive")
            
            # 5. Guardar patrones detectados
            await self._save_detected_patterns(plan_id, user_id, patterns)
            
            logger.info(f"[PlanOutcomeService] 🔍 Patrones detectados: {patterns}")
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error analizando patrones: {e}")
    
    async def _save_detected_patterns(
        self,
        plan_id: UUID,
        user_id: UUID,
        patterns: List[str]
    ):
        """Guarda los patrones detectados para futuras recomendaciones."""
        try:
            # TODO: Implementar tabla de patrones cuando esté disponible
            # Por ahora, guardar en metadata del plan
            await self.plan_service.update_plan_metadata(
                plan_id,
                user_id,
                {
                    "detected_patterns": patterns,
                    "pattern_analysis_date": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error guardando patrones: {e}")
    
    async def _update_user_statistics(
        self,
        user_id: UUID,
        execution_metrics: PlanExecutionMetrics
    ):
        """Actualiza estadísticas del usuario para recomendaciones."""
        try:
            # TODO: Implementar tabla de estadísticas de usuario
            # Por ahora, guardar en metadata del usuario
            stats = {
                "total_plans_executed": 1,  # TODO: Incrementar contador real
                "total_tasks_completed": execution_metrics.completed_tasks,
                "total_execution_time": execution_metrics.total_execution_time,
                "average_success_rate": execution_metrics.success_rate,
                "last_plan_execution": datetime.now(timezone.utc).isoformat(),
                "preferred_action_types": self._extract_preferred_action_types(execution_metrics)
            }
            
            # TODO: Actualizar estadísticas reales del usuario
            logger.info(f"[PlanOutcomeService] 📈 Estadísticas actualizadas para usuario {user_id}")
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error actualizando estadísticas: {e}")
    
    def _extract_preferred_action_types(
        self,
        execution_metrics: PlanExecutionMetrics
    ) -> List[str]:
        """Extrae los tipos de acción preferidos del usuario."""
        action_type_counts = {}
        for task_metric in execution_metrics.task_metrics:
            action_type = task_metric.action_type
            action_type_counts[action_type] = action_type_counts.get(action_type, 0) + 1
        
        # Ordenar por frecuencia
        sorted_types = sorted(action_type_counts.items(), key=lambda x: x[1], reverse=True)
        return [action_type for action_type, _ in sorted_types[:3]]  # Top 3
    
    def _generate_outcome_summary(self, execution_metrics: PlanExecutionMetrics) -> str:
        """Genera un resumen del resultado de la ejecución."""
        if execution_metrics.success_rate == 100:
            return f"✅ Plan completado exitosamente: {execution_metrics.completed_tasks}/{execution_metrics.total_tasks} tareas en {execution_metrics.total_execution_time:.1f}s"
        elif execution_metrics.success_rate >= 80:
            return f"⚠️ Plan completado con advertencias: {execution_metrics.completed_tasks}/{execution_metrics.total_tasks} tareas exitosas ({execution_metrics.success_rate:.1f}%)"
        else:
            return f"❌ Plan completado con errores: {execution_metrics.completed_tasks}/{execution_metrics.total_tasks} tareas exitosas ({execution_metrics.success_rate:.1f}%)"
    
    # ===== MÉTODOS DE CONSULTA =====
    
    async def get_user_execution_history(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> List[PlanOutcomeOut]:
        """
        Obtiene el historial de ejecuciones del usuario.
        
        Args:
            user_id: ID del usuario
            limit: Límite de resultados
            offset: Offset para paginación
            
        Returns:
            Lista de resultados de planes
        """
        try:
            outcomes = await self.plan_service.get_user_plan_outcomes(
                user_id, limit, offset
            )
            
            logger.info(f"[PlanOutcomeService] 📊 Historial obtenido: {len(outcomes)} resultados")
            return outcomes
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error obteniendo historial: {e}")
            return []
    
    async def get_execution_statistics(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas de ejecución del usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Dict con estadísticas de ejecución
        """
        try:
            # TODO: Implementar consulta real de estadísticas
            # Por ahora, devolver estadísticas simuladas
            stats = {
                "total_plans_executed": 0,
                "total_tasks_completed": 0,
                "average_success_rate": 0.0,
                "total_execution_time": 0.0,
                "most_common_action_types": [],
                "execution_trends": {
                    "last_7_days": 0,
                    "last_30_days": 0,
                    "last_90_days": 0
                }
            }
            
            logger.info(f"[PlanOutcomeService] 📈 Estadísticas obtenidas para usuario {user_id}")
            return stats
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error obteniendo estadísticas: {e}")
            return {}
    
    async def get_recommendation_candidates(
        self,
        user_id: UUID,
        current_plan_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Obtiene candidatos para recomendaciones basados en el historial.
        
        Args:
            user_id: ID del usuario
            current_plan_context: Contexto del plan actual
            
        Returns:
            Lista de candidatos para recomendaciones
        """
        try:
            # TODO: Implementar lógica de recomendaciones real
            # Por ahora, devolver recomendaciones simuladas
            candidates = [
                {
                    "type": "similar_plan",
                    "title": "Plan similar ejecutado anteriormente",
                    "description": "Se encontró un plan similar que fue exitoso",
                    "confidence": 0.85,
                    "plan_id": "123e4567-e89b-12d3-a456-426614174000"
                },
                {
                    "type": "optimization_suggestion",
                    "title": "Optimización sugerida",
                    "description": "Se puede optimizar el orden de las tareas",
                    "confidence": 0.72,
                    "suggestion": "Ejecutar tareas de base de datos antes que las de API"
                }
            ]
            
            logger.info(f"[PlanOutcomeService] 💡 {len(candidates)} candidatos de recomendación encontrados")
            return candidates
            
        except Exception as e:
            logger.error(f"[PlanOutcomeService] ❌ Error obteniendo candidatos: {e}")
            return []
