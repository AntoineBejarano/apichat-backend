"""
PlanRecommendationService - Servicio para generar recomendaciones de planes.
Analiza patrones históricos y sugiere optimizaciones y automatizaciones.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum

from app.services.execution.plan_outcome_service import PlanOutcomeService, PlanExecutionMetrics
from app.services.management.plan_service import PlanService
from app.schemas.plan_schema import PlanOutcomeOut

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Tipos de recomendaciones."""
    SIMILAR_PLAN = "similar_plan"
    OPTIMIZATION = "optimization"
    AUTOMATION = "automation"
    PATTERN_DETECTION = "pattern_detection"
    RESOURCE_OPTIMIZATION = "resource_optimization"


@dataclass
class PlanRecommendation:
    """Recomendación de plan."""
    id: str
    type: RecommendationType
    title: str
    description: str
    confidence: float
    priority: str  # "low", "medium", "high", "critical"
    action_required: bool
    metadata: Dict[str, Any]
    created_at: datetime


@dataclass
class AutomationCandidate:
    """Candidato para automatización."""
    pattern_id: str
    pattern_name: str
    frequency: int
    success_rate: float
    average_execution_time: float
    tasks_sequence: List[str]
    automation_benefit: str
    confidence: float


class PlanRecommendationService:
    """
    Servicio para generar recomendaciones inteligentes de planes.
    """
    
    def __init__(self, factory=None):
        self.factory = factory
        self.outcome_service = None
        self.plan_service = None
        self._initialize_services()
    
    def _initialize_services(self):
        """Inicializa los servicios necesarios."""
        if self.factory:
            self.outcome_service = PlanOutcomeService(self.factory)
            self.plan_service = self.factory.get_plan_service()
    
    async def generate_recommendations(
        self,
        user_id: UUID,
        current_plan_context: Optional[Dict[str, Any]] = None
    ) -> List[PlanRecommendation]:
        """
        Genera recomendaciones para el usuario basadas en su historial.
        
        Args:
            user_id: ID del usuario
            current_plan_context: Contexto del plan actual (opcional)
            
        Returns:
            Lista de recomendaciones
        """
        try:
            logger.info(f"[PlanRecommendationService] 💡 Generando recomendaciones para usuario {user_id}")
            
            recommendations = []
            
            # 1. Obtener historial del usuario
            execution_history = await self.outcome_service.get_user_execution_history(user_id, limit=50)
            
            if not execution_history:
                # Si no hay historial, generar recomendaciones básicas
                return await self._generate_basic_recommendations(user_id)
            
            # 2. Analizar patrones históricos
            patterns = await self._analyze_historical_patterns(execution_history)
            
            # 3. Generar recomendaciones basadas en patrones
            recommendations.extend(await self._generate_pattern_based_recommendations(patterns, user_id))
            
            # 4. Generar recomendaciones de optimización
            recommendations.extend(await self._generate_optimization_recommendations(execution_history, user_id))
            
            # 5. Generar candidatos de automatización
            automation_candidates = await self._identify_automation_candidates(execution_history)
            recommendations.extend(await self._generate_automation_recommendations(automation_candidates, user_id))
            
            # 6. Generar recomendaciones de recursos
            recommendations.extend(await self._generate_resource_recommendations(execution_history, user_id))
            
            # 7. Filtrar y ordenar recomendaciones
            filtered_recommendations = self._filter_and_rank_recommendations(recommendations)
            
            logger.info(f"[PlanRecommendationService] ✅ {len(filtered_recommendations)} recomendaciones generadas")
            return filtered_recommendations
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error generando recomendaciones: {e}")
            return []
    
    async def _generate_basic_recommendations(self, user_id: UUID) -> List[PlanRecommendation]:
        """Genera recomendaciones básicas para usuarios nuevos."""
        recommendations = [
            PlanRecommendation(
                id="basic_1",
                type=RecommendationType.PATTERN_DETECTION,
                title="🎯 Comienza con planes simples",
                description="Para empezar, te recomendamos crear planes con 2-3 tareas para familiarizarte con el sistema.",
                confidence=0.9,
                priority="medium",
                action_required=False,
                metadata={"category": "onboarding"},
                created_at=datetime.now(timezone.utc)
            ),
            PlanRecommendation(
                id="basic_2",
                type=RecommendationType.OPTIMIZATION,
                title="📊 Usa comandos de chat",
                description="Puedes usar comandos como 'listar planes', 'estado ejecución' para gestionar tus planes más fácilmente.",
                confidence=0.8,
                priority="low",
                action_required=False,
                metadata={"category": "tips"},
                created_at=datetime.now(timezone.utc)
            )
        ]
        
        return recommendations
    
    async def _analyze_historical_patterns(
        self,
        execution_history: List[PlanOutcomeOut]
    ) -> Dict[str, Any]:
        """Analiza patrones en el historial de ejecución."""
        try:
            patterns = {
                "common_action_types": {},
                "execution_times": [],
                "success_rates": [],
                "failure_patterns": [],
                "resource_usage": [],
                "temporal_patterns": {}
            }
            
            for outcome in execution_history:
                # Analizar tipos de acción comunes
                metadata = outcome.execution_metadata or {}
                action_types = metadata.get("action_types", [])
                for action_type in action_types:
                    patterns["common_action_types"][action_type] = patterns["common_action_types"].get(action_type, 0) + 1
                
                # Analizar tiempos de ejecución
                execution_time = metadata.get("total_execution_time", 0)
                if execution_time > 0:
                    patterns["execution_times"].append(execution_time)
                
                # Analizar tasas de éxito
                patterns["success_rates"].append(outcome.success_rate)
                
                # Analizar patrones temporales
                created_date = outcome.created_at.date()
                patterns["temporal_patterns"][created_date] = patterns["temporal_patterns"].get(created_date, 0) + 1
            
            return patterns
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error analizando patrones: {e}")
            return {}
    
    async def _generate_pattern_based_recommendations(
        self,
        patterns: Dict[str, Any],
        user_id: UUID
    ) -> List[PlanRecommendation]:
        """Genera recomendaciones basadas en patrones detectados."""
        recommendations = []
        
        try:
            # Recomendación basada en tipos de acción comunes
            common_actions = patterns.get("common_action_types", {})
            if common_actions:
                most_common = max(common_actions.items(), key=lambda x: x[1])
                recommendations.append(PlanRecommendation(
                    id=f"pattern_1_{user_id}",
                    type=RecommendationType.PATTERN_DETECTION,
                    title=f"🔍 Patrón detectado: {most_common[0]}",
                    description=f"Has ejecutado {most_common[1]} planes con acciones de tipo '{most_common[0]}'. Considera crear plantillas para este tipo de trabajo.",
                    confidence=0.8,
                    priority="medium",
                    action_required=False,
                    metadata={"pattern_type": "action_frequency", "action_type": most_common[0]},
                    created_at=datetime.now(timezone.utc)
                ))
            
            # Recomendación basada en tiempos de ejecución
            execution_times = patterns.get("execution_times", [])
            if execution_times:
                avg_time = sum(execution_times) / len(execution_times)
                if avg_time > 300:  # > 5 minutos
                    recommendations.append(PlanRecommendation(
                        id=f"pattern_2_{user_id}",
                        type=RecommendationType.OPTIMIZATION,
                        title="⏱️ Optimización de tiempo",
                        description=f"Tus planes tardan en promedio {avg_time:.1f} segundos. Considera dividir planes largos en sub-planes más pequeños.",
                        confidence=0.7,
                        priority="medium",
                        action_required=False,
                        metadata={"pattern_type": "execution_time", "average_time": avg_time},
                        created_at=datetime.now(timezone.utc)
                    ))
            
            # Recomendación basada en tasas de éxito
            success_rates = patterns.get("success_rates", [])
            if success_rates:
                avg_success = sum(success_rates) / len(success_rates)
                if avg_success < 80:
                    recommendations.append(PlanRecommendation(
                        id=f"pattern_3_{user_id}",
                        type=RecommendationType.OPTIMIZATION,
                        title="⚠️ Mejora de confiabilidad",
                        description=f"Tu tasa de éxito promedio es {avg_success:.1f}%. Revisa los planes fallidos para identificar problemas comunes.",
                        confidence=0.9,
                        priority="high",
                        action_required=True,
                        metadata={"pattern_type": "success_rate", "average_success": avg_success},
                        created_at=datetime.now(timezone.utc)
                    ))
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error generando recomendaciones de patrones: {e}")
        
        return recommendations
    
    async def _generate_optimization_recommendations(
        self,
        execution_history: List[PlanOutcomeOut],
        user_id: UUID
    ) -> List[PlanRecommendation]:
        """Genera recomendaciones de optimización."""
        recommendations = []
        
        try:
            # Analizar planes fallidos para optimizaciones
            failed_plans = [outcome for outcome in execution_history if outcome.success_rate < 100]
            
            if failed_plans:
                recommendations.append(PlanRecommendation(
                    id=f"optimization_1_{user_id}",
                    type=RecommendationType.OPTIMIZATION,
                    title="🔧 Optimización de planes fallidos",
                    description=f"Tienes {len(failed_plans)} planes con errores. Considera revisar las tareas que fallan frecuentemente y agregar validaciones.",
                    confidence=0.8,
                    priority="high",
                    action_required=True,
                    metadata={"failed_plans_count": len(failed_plans)},
                    created_at=datetime.now(timezone.utc)
                ))
            
            # Recomendación de paralelización
            long_plans = [outcome for outcome in execution_history 
                         if outcome.execution_metadata and outcome.execution_metadata.get("total_execution_time", 0) > 180]
            
            if long_plans:
                recommendations.append(PlanRecommendation(
                    id=f"optimization_2_{user_id}",
                    type=RecommendationType.OPTIMIZATION,
                    title="⚡ Paralelización de tareas",
                    description=f"Tienes {len(long_plans)} planes que tardan más de 3 minutos. Considera ejecutar tareas independientes en paralelo.",
                    confidence=0.6,
                    priority="medium",
                    action_required=False,
                    metadata={"long_plans_count": len(long_plans)},
                    created_at=datetime.now(timezone.utc)
                ))
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error generando recomendaciones de optimización: {e}")
        
        return recommendations
    
    async def _identify_automation_candidates(
        self,
        execution_history: List[PlanOutcomeOut]
    ) -> List[AutomationCandidate]:
        """Identifica candidatos para automatización."""
        candidates = []
        
        try:
            # Agrupar planes por secuencia de tareas similares
            task_sequences = {}
            
            for outcome in execution_history:
                if outcome.success_rate >= 80:  # Solo planes exitosos
                    metadata = outcome.execution_metadata or {}
                    task_sequence = metadata.get("task_sequence", [])
                    
                    if task_sequence:
                        sequence_key = " -> ".join(task_sequence)
                        if sequence_key not in task_sequences:
                            task_sequences[sequence_key] = {
                                "count": 0,
                                "success_rates": [],
                                "execution_times": []
                            }
                        
                        task_sequences[sequence_key]["count"] += 1
                        task_sequences[sequence_key]["success_rates"].append(outcome.success_rate)
                        
                        execution_time = metadata.get("total_execution_time", 0)
                        if execution_time > 0:
                            task_sequences[sequence_key]["execution_times"].append(execution_time)
            
            # Crear candidatos de automatización
            for sequence_key, data in task_sequences.items():
                if data["count"] >= 3:  # Al menos 3 ejecuciones
                    avg_success = sum(data["success_rates"]) / len(data["success_rates"])
                    avg_time = sum(data["execution_times"]) / len(data["execution_times"]) if data["execution_times"] else 0
                    
                    if avg_success >= 90:  # Alta tasa de éxito
                        candidates.append(AutomationCandidate(
                            pattern_id=f"auto_{hash(sequence_key)}",
                            pattern_name=f"Secuencia: {sequence_key[:50]}...",
                            frequency=data["count"],
                            success_rate=avg_success,
                            average_execution_time=avg_time,
                            tasks_sequence=sequence_key.split(" -> "),
                            automation_benefit=f"Ahorraría {avg_time * data['count']:.1f} segundos en {data['count']} ejecuciones",
                            confidence=0.8
                        ))
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error identificando candidatos de automatización: {e}")
        
        return candidates
    
    async def _generate_automation_recommendations(
        self,
        automation_candidates: List[AutomationCandidate],
        user_id: UUID
    ) -> List[PlanRecommendation]:
        """Genera recomendaciones de automatización."""
        recommendations = []
        
        try:
            for i, candidate in enumerate(automation_candidates[:3]):  # Top 3 candidatos
                recommendations.append(PlanRecommendation(
                    id=f"automation_{i}_{user_id}",
                    type=RecommendationType.AUTOMATION,
                    title="🤖 Candidato para automatización",
                    description=f"La secuencia '{candidate.pattern_name}' se ejecutó {candidate.frequency} veces con {candidate.success_rate:.1f}% de éxito. {candidate.automation_benefit}.",
                    confidence=candidate.confidence,
                    priority="high" if candidate.frequency >= 5 else "medium",
                    action_required=True,
                    metadata={
                        "pattern_id": candidate.pattern_id,
                        "frequency": candidate.frequency,
                        "success_rate": candidate.success_rate,
                        "tasks_sequence": candidate.tasks_sequence
                    },
                    created_at=datetime.now(timezone.utc)
                ))
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error generando recomendaciones de automatización: {e}")
        
        return recommendations
    
    async def _generate_resource_recommendations(
        self,
        execution_history: List[PlanOutcomeOut],
        user_id: UUID
    ) -> List[PlanRecommendation]:
        """Genera recomendaciones de optimización de recursos."""
        recommendations = []
        
        try:
            # Analizar uso de recursos
            high_memory_plans = []
            high_cpu_plans = []
            
            for outcome in execution_history:
                metadata = outcome.execution_metadata or {}
                resource_usage = metadata.get("resource_usage", {})
                
                memory_usage = resource_usage.get("memory_usage", 0)
                if memory_usage > 1000:  # > 1GB
                    high_memory_plans.append(outcome)
                
                cpu_usage = resource_usage.get("cpu_usage", 0)
                if cpu_usage > 80:  # > 80%
                    high_cpu_plans.append(outcome)
            
            if high_memory_plans:
                recommendations.append(PlanRecommendation(
                    id=f"resource_1_{user_id}",
                    type=RecommendationType.RESOURCE_OPTIMIZATION,
                    title="💾 Optimización de memoria",
                    description=f"Tienes {len(high_memory_plans)} planes que usan mucha memoria. Considera optimizar consultas SQL o dividir tareas grandes.",
                    confidence=0.7,
                    priority="medium",
                    action_required=False,
                    metadata={"high_memory_plans": len(high_memory_plans)},
                    created_at=datetime.now(timezone.utc)
                ))
            
            if high_cpu_plans:
                recommendations.append(PlanRecommendation(
                    id=f"resource_2_{user_id}",
                    type=RecommendationType.RESOURCE_OPTIMIZATION,
                    title="⚡ Optimización de CPU",
                    description=f"Tienes {len(high_cpu_plans)} planes que usan mucha CPU. Considera ejecutar tareas en horarios de menor carga.",
                    confidence=0.6,
                    priority="low",
                    action_required=False,
                    metadata={"high_cpu_plans": len(high_cpu_plans)},
                    created_at=datetime.now(timezone.utc)
                ))
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error generando recomendaciones de recursos: {e}")
        
        return recommendations
    
    def _filter_and_rank_recommendations(
        self,
        recommendations: List[PlanRecommendation]
    ) -> List[PlanRecommendation]:
        """Filtra y ordena las recomendaciones por prioridad y confianza."""
        try:
            # Filtrar recomendaciones con baja confianza
            filtered = [rec for rec in recommendations if rec.confidence >= 0.5]
            
            # Ordenar por prioridad y confianza
            priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
            filtered.sort(key=lambda x: (priority_order.get(x.priority, 0), x.confidence), reverse=True)
            
            # Limitar a 10 recomendaciones
            return filtered[:10]
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error filtrando recomendaciones: {e}")
            return recommendations
    
    # ===== MÉTODOS DE CONSULTA =====
    
    async def get_recommendation_by_id(
        self,
        recommendation_id: str,
        user_id: UUID
    ) -> Optional[PlanRecommendation]:
        """Obtiene una recomendación específica por ID."""
        try:
            # TODO: Implementar consulta real a base de datos
            # Por ahora, generar recomendaciones y buscar por ID
            recommendations = await self.generate_recommendations(user_id)
            
            for rec in recommendations:
                if rec.id == recommendation_id:
                    return rec
            
            return None
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error obteniendo recomendación: {e}")
            return None
    
    async def mark_recommendation_as_applied(
        self,
        recommendation_id: str,
        user_id: UUID,
        application_notes: Optional[str] = None
    ) -> bool:
        """Marca una recomendación como aplicada."""
        try:
            # TODO: Implementar persistencia de aplicación de recomendaciones
            logger.info(f"[PlanRecommendationService] ✅ Recomendación {recommendation_id} marcada como aplicada por usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[PlanRecommendationService] ❌ Error marcando recomendación: {e}")
            return False
