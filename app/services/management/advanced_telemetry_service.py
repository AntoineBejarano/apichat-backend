"""
🎯 FASE 13: Servicio de telemetría avanzado a nivel super pro.

Este servicio proporciona métricas detalladas y KPIs para medir el impacto UX
y optimizar la performance del sistema de chat.
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json
import statistics

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from sqlalchemy.exc import SQLAlchemyError

from app.models.telemetry_models import (
    ConversationMetrics, StepMetrics, CacheMetrics, 
    ErrorMetrics, AggregatedMetrics
)
from app.schemas.telemetry_schema import (
    ConversationMetricsCreate, StepMetricsCreate, CacheMetricsCreate,
    ErrorMetricsCreate, AggregatedMetricsCreate, TelemetrySnapshotResponse,
    TelemetryDashboardResponse, TelemetryExportRequest
)
from app.services.base_service import BaseService
from app.common.events import TelemetrySnapshotEvent
from app.common.ws_emitter import WebSocketEmitter

logger = logging.getLogger(__name__)


@dataclass
class TelemetryContext:
    """Contexto de telemetría para una conversación."""
    conversation_id: UUID
    user_id: UUID
    chat_id: UUID
    session_id: Optional[UUID]
    mode: str
    started_at: datetime
    
    # Métricas acumulativas
    tokens_in: int = 0
    tokens_out: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    steps_executed: int = 0
    confirmations_required: int = 0
    errors_encountered: int = 0
    
    # Latencias
    latency_llm_ms: float = 0.0
    latency_db_ms: float = 0.0
    latency_cache_ms: float = 0.0
    
    # Recursos accedidos
    databases_accessed: set = None
    apps_accessed: set = None
    functions_executed: set = None
    
    # Preferencias del usuario
    user_preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.databases_accessed is None:
            self.databases_accessed = set()
        if self.apps_accessed is None:
            self.apps_accessed = set()
        if self.functions_executed is None:
            self.functions_executed = set()
        if self.user_preferences is None:
            self.user_preferences = {}

    def add_tokens(self, tokens_in: int = 0, tokens_out: int = 0):
        """Añade tokens a las métricas."""
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out

    def add_cache_operation(self, hit: bool):
        """Añade una operación de cache."""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def add_latency(self, latency_type: str, duration_ms: float):
        """Añade latencia de un tipo específico."""
        if latency_type == "llm":
            self.latency_llm_ms += duration_ms
        elif latency_type == "db":
            self.latency_db_ms += duration_ms
        elif latency_type == "cache":
            self.latency_cache_ms += duration_ms

    def add_resource_access(self, resource_type: str, resource_id: str):
        """Añade acceso a un recurso."""
        if resource_type == "database":
            self.databases_accessed.add(resource_id)
        elif resource_type == "app":
            self.apps_accessed.add(resource_id)
        elif resource_type == "function":
            self.functions_executed.add(resource_id)

    def get_cache_hit_ratio(self) -> float:
        """Calcula el ratio de aciertos de cache."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def get_total_latency_ms(self) -> float:
        """Calcula la latencia total."""
        return self.latency_llm_ms + self.latency_db_ms + self.latency_cache_ms

    def to_conversation_metrics(self, completed_at: datetime, user_agent: str = None, 
                               ip_address: str = None, country_code: str = None) -> ConversationMetricsCreate:
        """Convierte el contexto a métricas de conversación."""
        return ConversationMetricsCreate(
            chat_id=self.chat_id,
            user_id=self.user_id,
            session_id=self.session_id,
            tokens_in=self.tokens_in,
            tokens_out=self.tokens_out,
            estimated_cost_usd=self._calculate_cost(),
            latency_total_ms=Decimal(str(self.get_total_latency_ms())),
            latency_llm_ms=Decimal(str(self.latency_llm_ms)),
            latency_db_ms=Decimal(str(self.latency_db_ms)),
            latency_cache_ms=Decimal(str(self.latency_cache_ms)),
            cache_hit_ratio=Decimal(str(self.get_cache_hit_ratio())),
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            steps_executed=self.steps_executed,
            confirmations_required=self.confirmations_required,
            errors_encountered=self.errors_encountered,
            mode=self.mode,
            databases_accessed=len(self.databases_accessed),
            apps_accessed=len(self.apps_accessed),
            functions_executed=len(self.functions_executed),
            started_at=self.started_at,
            completed_at=completed_at,
            user_agent=user_agent,
            ip_address=ip_address,
            country_code=country_code,
            timezone=self.user_preferences.get("timezone"),
            user_response_format=self.user_preferences.get("response_format"),
            user_detail_level=self.user_preferences.get("detail_level"),
            user_risk_tolerance=self.user_preferences.get("risk_tolerance"),
            user_language=self.user_preferences.get("language")
        )

    def _calculate_cost(self) -> Decimal:
        """Calcula el costo estimado en USD."""
        # Precios aproximados por 1K tokens (GPT-4)
        input_cost_per_1k = Decimal("0.0015")
        output_cost_per_1k = Decimal("0.006")
        
        input_cost = (Decimal(str(self.tokens_in)) / Decimal("1000")) * input_cost_per_1k
        output_cost = (Decimal(str(self.tokens_out)) / Decimal("1000")) * output_cost_per_1k
        
        return input_cost + output_cost


class AdvancedTelemetryService(BaseService):
    """
    Servicio de telemetría avanzado a nivel super pro.
    
    Proporciona métricas detalladas, KPIs y análisis de performance
    para optimizar la experiencia del usuario.
    """
    
    def __init__(self, factory):
        super().__init__(factory)
        self._active_contexts: Dict[UUID, TelemetryContext] = {}
        self._metrics_buffer: deque = deque(maxlen=1000)
        self._aggregation_cache: Dict[str, Any] = {}
        self._last_aggregation: Optional[datetime] = None
        
        # Configuración
        self.auto_aggregate_interval = timedelta(hours=1)
        self.retention_days = 90
        self.max_contexts = 1000
        
        logger.info("[AdvancedTelemetryService] 🚀 Inicializado con capacidades avanzadas")

    # 🎯 Gestión de contexto de telemetría

    def start_conversation_tracking(
        self,
        conversation_id: UUID,
        user_id: UUID,
        chat_id: UUID,
        session_id: Optional[UUID] = None,
        mode: str = "guided",
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> TelemetryContext:
        """Inicia el tracking de una conversación."""
        try:
            # Limpiar contextos antiguos si excedemos el límite
            if len(self._active_contexts) >= self.max_contexts:
                self._cleanup_old_contexts()
            
            context = TelemetryContext(
                conversation_id=conversation_id,
                user_id=user_id,
                chat_id=chat_id,
                session_id=session_id,
                mode=mode,
                started_at=datetime.now(timezone.utc),
                user_preferences=user_preferences or {}
            )
            
            self._active_contexts[conversation_id] = context
            
            logger.info(f"[AdvancedTelemetryService] 📊 Iniciado tracking para conversación {conversation_id}")
            return context
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error iniciando tracking: {e}")
            # Retornar contexto dummy en caso de error
            return TelemetryContext(
                conversation_id=conversation_id,
                user_id=user_id,
                chat_id=chat_id,
                mode=mode,
                started_at=datetime.now(timezone.utc)
            )

    def get_conversation_context(self, conversation_id: UUID) -> Optional[TelemetryContext]:
        """Obtiene el contexto de una conversación."""
        return self._active_contexts.get(conversation_id)

    def end_conversation_tracking(
        self,
        conversation_id: UUID,
        user_agent: str = None,
        ip_address: str = None,
        country_code: str = None
    ) -> Optional[ConversationMetrics]:
        """Finaliza el tracking de una conversación y retorna las métricas."""
        try:
            context = self._active_contexts.pop(conversation_id, None)
            if not context:
                logger.warning(f"[AdvancedTelemetryService] ⚠️ Contexto no encontrado para {conversation_id}")
                return None
            
            completed_at = datetime.now(timezone.utc)
            
            # Crear métricas de conversación
            metrics_data = context.to_conversation_metrics(
                completed_at=completed_at,
                user_agent=user_agent,
                ip_address=ip_address,
                country_code=country_code
            )
            
            # Guardar en base de datos
            metrics = self._save_conversation_metrics(metrics_data)
            
            # Añadir al buffer para agregación
            self._metrics_buffer.append(metrics)
            
            # Auto-agregación si es necesario
            if self._should_auto_aggregate():
                asyncio.create_task(self._auto_aggregate_metrics())
            
            logger.info(f"[AdvancedTelemetryService] ✅ Finalizado tracking para {conversation_id}")
            return metrics
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error finalizando tracking: {e}")
            return None

    # 🎯 Tracking de métricas en tiempo real

    def track_step_execution(
        self,
        conversation_id: UUID,
        step_number: int,
        step_type: str,
        duration_ms: float,
        success: bool = True,
        error_message: str = None,
        tokens_used: int = 0,
        cache_operations: int = 0,
        database_queries: int = 0,
        llm_calls: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra la ejecución de un paso."""
        try:
            context = self.get_conversation_context(conversation_id)
            if not context:
                return
            
            # Actualizar contexto
            context.steps_executed += 1
            if not success:
                context.errors_encountered += 1
            
            # Crear métricas del paso
            step_metrics = StepMetricsCreate(
                conversation_metrics_id=context.conversation_id,  # Temporal, se actualizará
                step_number=step_number,
                step_type=step_type,
                duration_ms=Decimal(str(duration_ms)),
                success=success,
                error_message=error_message,
                tokens_used=tokens_used,
                cache_operations=cache_operations,
                database_queries=database_queries,
                llm_calls=llm_calls,
                metadata=metadata,
                started_at=datetime.now(timezone.utc) - timedelta(milliseconds=duration_ms),
                completed_at=datetime.now(timezone.utc)
            )
            
            # Guardar en base de datos (asíncrono)
            asyncio.create_task(self._save_step_metrics(step_metrics))
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error tracking step: {e}")

    def track_cache_operation(
        self,
        conversation_id: UUID,
        resource_type: str,
        resource_id: str,
        operation: str,
        duration_ms: Optional[float] = None,
        size_bytes: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
        cache_layer: str = "memory",
        compression_ratio: Optional[float] = None
    ):
        """Registra una operación de cache."""
        try:
            context = self.get_conversation_context(conversation_id)
            if not context:
                return
            
            # Actualizar contexto
            context.add_cache_operation(operation == "hit")
            if duration_ms:
                context.add_latency("cache", duration_ms)
            
            # Crear métricas de cache
            cache_metrics = CacheMetricsCreate(
                conversation_metrics_id=conversation_id,  # Temporal
                resource_type=resource_type,
                resource_id=resource_id,
                operation=operation,
                duration_ms=Decimal(str(duration_ms)) if duration_ms else None,
                size_bytes=size_bytes,
                ttl_seconds=ttl_seconds,
                cache_layer=cache_layer,
                compression_ratio=Decimal(str(compression_ratio)) if compression_ratio else None
            )
            
            # Guardar en base de datos (asíncrono)
            asyncio.create_task(self._save_cache_metrics(cache_metrics))
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error tracking cache: {e}")

    def track_error(
        self,
        conversation_id: UUID,
        error_type: str,
        error_message: str,
        error_code: str = None,
        error_stack: str = None,
        step_number: int = None,
        step_type: str = None,
        user_input: str = None,
        severity: str = "medium",
        recovered: bool = False,
        recovery_action: str = None
    ):
        """Registra un error."""
        try:
            context = self.get_conversation_context(conversation_id)
            if not context:
                return
            
            # Actualizar contexto
            context.errors_encountered += 1
            
            # Crear métricas de error
            error_metrics = ErrorMetricsCreate(
                conversation_metrics_id=conversation_id,  # Temporal
                error_type=error_type,
                error_code=error_code,
                error_message=error_message,
                error_stack=error_stack,
                step_number=step_number,
                step_type=step_type,
                user_input=user_input,
                severity=severity,
                recovered=recovered,
                recovery_action=recovery_action
            )
            
            # Guardar en base de datos (asíncrono)
            asyncio.create_task(self._save_error_metrics(error_metrics))
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error tracking error: {e}")

    # 🎯 Persistencia en base de datos

    def _save_conversation_metrics(self, metrics_data: ConversationMetricsCreate) -> ConversationMetrics:
        """Guarda las métricas de conversación en la base de datos."""
        try:
            metrics = ConversationMetrics(**metrics_data.model_dump())
            self.db.add(metrics)
            self.db.commit()
            self.db.refresh(metrics)
            
            # Actualizar IDs en métricas relacionadas
            self._update_related_metrics_ids(metrics.id, metrics_data)
            
            return metrics
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"[AdvancedTelemetryService] ❌ Error guardando métricas: {e}")
            raise

    async def _save_step_metrics(self, step_metrics: StepMetricsCreate):
        """Guarda las métricas de un paso."""
        try:
            # Buscar la conversación correspondiente
            conversation = self.db.query(ConversationMetrics).filter(
                ConversationMetrics.chat_id == step_metrics.conversation_metrics_id
            ).first()
            
            if conversation:
                step_metrics.conversation_metrics_id = conversation.id
                step = StepMetrics(**step_metrics.model_dump())
                self.db.add(step)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error guardando step metrics: {e}")

    async def _save_cache_metrics(self, cache_metrics: CacheMetricsCreate):
        """Guarda las métricas de cache."""
        try:
            # Buscar la conversación correspondiente
            conversation = self.db.query(ConversationMetrics).filter(
                ConversationMetrics.chat_id == cache_metrics.conversation_metrics_id
            ).first()
            
            if conversation:
                cache_metrics.conversation_metrics_id = conversation.id
                cache = CacheMetrics(**cache_metrics.model_dump())
                self.db.add(cache)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error guardando cache metrics: {e}")

    async def _save_error_metrics(self, error_metrics: ErrorMetricsCreate):
        """Guarda las métricas de error."""
        try:
            # Buscar la conversación correspondiente
            conversation = self.db.query(ConversationMetrics).filter(
                ConversationMetrics.chat_id == error_metrics.conversation_metrics_id
            ).first()
            
            if conversation:
                error_metrics.conversation_metrics_id = conversation.id
                error = ErrorMetrics(**error_metrics.model_dump())
                self.db.add(error)
                self.db.commit()
                
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error guardando error metrics: {e}")

    def _update_related_metrics_ids(self, conversation_id: UUID, metrics_data: ConversationMetricsCreate):
        """Actualiza los IDs de métricas relacionadas."""
        # Esta función se implementaría para actualizar las métricas relacionadas
        # cuando se guarda la conversación principal
        pass

    # 🎯 Agregación y análisis de métricas

    def _should_auto_aggregate(self) -> bool:
        """Determina si se debe ejecutar la agregación automática."""
        if not self._last_aggregation:
            return True
        
        return datetime.now(timezone.utc) - self._last_aggregation >= self.auto_aggregate_interval

    async def _auto_aggregate_metrics(self):
        """Ejecuta la agregación automática de métricas."""
        try:
            logger.info("[AdvancedTelemetryService] 🔄 Ejecutando agregación automática")
            
            # Agregar métricas por hora
            await self.aggregate_metrics_by_period("hour")
            
            # Agregar métricas por día
            await self.aggregate_metrics_by_period("day")
            
            self._last_aggregation = datetime.now(timezone.utc)
            
            # Limpiar métricas antiguas
            await self._cleanup_old_metrics()
            
            logger.info("[AdvancedTelemetryService] ✅ Agregación automática completada")
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error en agregación automática: {e}")

    async def aggregate_metrics_by_period(self, period_type: str) -> AggregatedMetrics:
        """Agrega métricas por un período específico."""
        try:
            now = datetime.now(timezone.utc)
            
            if period_type == "hour":
                period_start = now.replace(minute=0, second=0, microsecond=0)
                period_end = period_start + timedelta(hours=1)
            elif period_type == "day":
                period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                period_end = period_start + timedelta(days=1)
            elif period_type == "week":
                period_start = now - timedelta(days=now.weekday())
                period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
                period_end = period_start + timedelta(weeks=1)
            elif period_type == "month":
                period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 12:
                    period_end = period_start.replace(year=now.year + 1, month=1)
                else:
                    period_end = period_start.replace(month=now.month + 1)
            else:
                raise ValueError(f"Período no válido: {period_type}")
            
            # Verificar si ya existe agregación para este período
            existing = self.db.query(AggregatedMetrics).filter(
                and_(
                    AggregatedMetrics.period_type == period_type,
                    AggregatedMetrics.period_start == period_start
                )
            ).first()
            
            if existing:
                logger.debug(f"[AdvancedTelemetryService] Agregación ya existe para {period_type}: {period_start}")
                return existing
            
            # Calcular métricas agregadas
            aggregated_data = await self._calculate_aggregated_metrics(period_start, period_end)
            
            # Crear métricas agregadas
            aggregated_metrics = AggregatedMetricsCreate(
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                **aggregated_data
            )
            
            # Guardar en base de datos
            metrics = AggregatedMetrics(**aggregated_metrics.model_dump())
            self.db.add(metrics)
            self.db.commit()
            self.db.refresh(metrics)
            
            logger.info(f"[AdvancedTelemetryService] ✅ Métricas agregadas para {period_type}: {period_start}")
            return metrics
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error agregando métricas: {e}")
            raise

    async def _calculate_aggregated_metrics(self, period_start: datetime, period_end: datetime) -> Dict[str, Any]:
        """Calcula métricas agregadas para un período."""
        try:
            # Consultar métricas del período
            metrics = self.db.query(ConversationMetrics).filter(
                and_(
                    ConversationMetrics.created_at >= period_start,
                    ConversationMetrics.created_at < period_end
                )
            ).all()
            
            if not metrics:
                return self._get_empty_aggregated_metrics()
            
            # Calcular métricas agregadas
            total_conversations = len(metrics)
            total_tokens = sum(m.total_tokens for m in metrics)
            total_cost_usd = sum(m.estimated_cost_usd or Decimal('0') for m in metrics)
            
            latencies = [float(m.latency_total_ms) for m in metrics if m.latency_total_ms]
            avg_latency_ms = Decimal(str(statistics.mean(latencies))) if latencies else Decimal('0')
            
            cache_ratios = [float(m.cache_hit_ratio) for m in metrics if m.cache_hit_ratio is not None]
            avg_cache_hit_ratio = Decimal(str(statistics.mean(cache_ratios))) if cache_ratios else Decimal('0')
            
            satisfaction_scores = [m.user_satisfaction_score for m in metrics if m.user_satisfaction_score]
            avg_user_satisfaction = Decimal(str(statistics.mean(satisfaction_scores))) if satisfaction_scores else None
            
            total_errors = sum(m.errors_encountered for m in metrics)
            error_rate = Decimal(str(total_errors / total_conversations)) if total_conversations > 0 else Decimal('0')
            
            unique_users = len(set(m.user_id for m in metrics))
            active_sessions = len(set(m.session_id for m in metrics if m.session_id))
            
            # Calcular recursos más accedidos
            most_accessed_databases = self._calculate_most_accessed_resources(metrics, "databases_accessed")
            most_accessed_apps = self._calculate_most_accessed_resources(metrics, "apps_accessed")
            most_used_functions = self._calculate_most_accessed_resources(metrics, "functions_executed")
            
            return {
                "total_conversations": total_conversations,
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost_usd,
                "avg_latency_ms": avg_latency_ms,
                "avg_cache_hit_ratio": avg_cache_hit_ratio,
                "avg_user_satisfaction": avg_user_satisfaction,
                "total_errors": total_errors,
                "error_rate": error_rate,
                "unique_users": unique_users,
                "active_sessions": active_sessions,
                "most_accessed_databases": most_accessed_databases,
                "most_accessed_apps": most_accessed_apps,
                "most_used_functions": most_used_functions
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando métricas agregadas: {e}")
            return self._get_empty_aggregated_metrics()

    def _calculate_most_accessed_resources(self, metrics: List[ConversationMetrics], field: str) -> Dict[str, Any]:
        """Calcula los recursos más accedidos."""
        try:
            resource_counts = defaultdict(int)
            
            for metric in metrics:
                count = getattr(metric, field, 0)
                if count > 0:
                    # Aquí se podrían mapear IDs a nombres más legibles
                    resource_counts[f"resource_{metric.id}"] = count
            
            # Ordenar por uso y tomar top 10
            sorted_resources = sorted(resource_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "top_resources": [{"id": rid, "count": count} for rid, count in sorted_resources],
                "total_accesses": sum(resource_counts.values())
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando recursos más accedidos: {e}")
            return {"top_resources": [], "total_accesses": 0}

    def _get_empty_aggregated_metrics(self) -> Dict[str, Any]:
        """Retorna métricas vacías para un período sin datos."""
        return {
            "total_conversations": 0,
            "total_tokens": 0,
            "total_cost_usd": Decimal('0'),
            "avg_latency_ms": Decimal('0'),
            "avg_cache_hit_ratio": Decimal('0'),
            "avg_user_satisfaction": None,
            "total_errors": 0,
            "error_rate": Decimal('0'),
            "unique_users": 0,
            "active_sessions": 0,
            "most_accessed_databases": {"top_resources": [], "total_accesses": 0},
            "most_accessed_apps": {"top_resources": [], "total_accesses": 0},
            "most_used_functions": {"top_resources": [], "total_accesses": 0}
        }

    # 🎯 Dashboard y reportes

    async def get_telemetry_dashboard(self, user_id: Optional[UUID] = None) -> TelemetryDashboardResponse:
        """Obtiene el dashboard de telemetría."""
        try:
            # Métricas del período actual (hora)
            current_period = await self.aggregate_metrics_by_period("hour")
            
            # Métricas históricas (últimas 24 horas)
            historical_data = await self._get_historical_metrics(hours=24)
            
            # Top conversaciones
            top_conversations = await self._get_top_conversations(user_id, limit=10)
            
            # Top errores
            top_errors = await self._get_top_errors(user_id, limit=10)
            
            # Tendencias
            trends = await self._calculate_trends(hours=24)
            
            # Alertas
            alerts = await self._generate_alerts()
            
            return TelemetryDashboardResponse(
                current_period=current_period,
                historical_data=historical_data,
                top_conversations=top_conversations,
                top_errors=top_errors,
                trends=trends,
                alerts=alerts
            )
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo dashboard: {e}")
            raise

    async def _get_historical_metrics(self, hours: int) -> List[AggregatedMetrics]:
        """Obtiene métricas históricas."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            metrics = self.db.query(AggregatedMetrics).filter(
                and_(
                    AggregatedMetrics.period_start >= start_time,
                    AggregatedMetrics.period_start < end_time
                )
            ).order_by(AggregatedMetrics.period_start).all()
            
            return metrics
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo métricas históricas: {e}")
            return []

    async def _get_top_conversations(self, user_id: Optional[UUID], limit: int = 10) -> List[ConversationMetrics]:
        """Obtiene las mejores conversaciones."""
        try:
            query = self.db.query(ConversationMetrics)
            
            if user_id:
                query = query.filter(ConversationMetrics.user_id == user_id)
            
            top_conversations = query.order_by(
                desc(ConversationMetrics.user_satisfaction_score),
                desc(ConversationMetrics.cache_hit_ratio)
            ).limit(limit).all()
            
            return top_conversations
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo top conversaciones: {e}")
            return []

    async def _get_top_errors(self, user_id: Optional[UUID], limit: int = 10) -> List[ErrorMetrics]:
        """Obtiene los errores más frecuentes."""
        try:
            query = self.db.query(ErrorMetrics).join(ConversationMetrics)
            
            if user_id:
                query = query.filter(ConversationMetrics.user_id == user_id)
            
            top_errors = query.order_by(desc(ErrorMetrics.created_at)).limit(limit).all()
            
            return top_errors
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo top errores: {e}")
            return []

    async def _calculate_trends(self, hours: int) -> Dict[str, Any]:
        """Calcula tendencias de métricas clave."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # Obtener métricas del período
            metrics = self.db.query(ConversationMetrics).filter(
                and_(
                    ConversationMetrics.created_at >= start_time,
                    ConversationMetrics.created_at < end_time
                )
            ).all()
            
            if not metrics:
                return {"status": "insufficient_data"}
            
            # Calcular tendencias
            trends = {
                "latency_trend": self._calculate_metric_trend(metrics, "latency_total_ms"),
                "cache_trend": self._calculate_metric_trend(metrics, "cache_hit_ratio"),
                "error_trend": self._calculate_metric_trend(metrics, "errors_encountered"),
                "token_efficiency": self._calculate_token_efficiency(metrics),
                "user_satisfaction_trend": self._calculate_satisfaction_trend(metrics)
            }
            
            return trends
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando tendencias: {e}")
            return {"status": "error", "message": str(e)}

    def _calculate_metric_trend(self, metrics: List[ConversationMetrics], field: str) -> Dict[str, Any]:
        """Calcula la tendencia de una métrica específica."""
        try:
            if not metrics:
                return {"trend": "stable", "change_percent": 0.0}
            
            # Dividir en dos períodos para comparar
            mid_point = len(metrics) // 2
            first_half = metrics[:mid_point]
            second_half = metrics[mid_point:]
            
            if not first_half or not second_half:
                return {"trend": "stable", "change_percent": 0.0}
            
            # Calcular promedios
            first_avg = statistics.mean([getattr(m, field) or 0 for m in first_half])
            second_avg = statistics.mean([getattr(m, field) or 0 for m in second_half])
            
            if first_avg == 0:
                change_percent = 0.0
            else:
                change_percent = ((second_avg - first_avg) / first_avg) * 100
            
            # Determinar tendencia
            if change_percent > 5:
                trend = "increasing"
            elif change_percent < -5:
                trend = "decreasing"
            else:
                trend = "stable"
            
            return {
                "trend": trend,
                "change_percent": round(change_percent, 2),
                "first_period_avg": round(first_avg, 2),
                "second_period_avg": round(second_avg, 2)
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando tendencia de {field}: {e}")
            return {"trend": "error", "change_percent": 0.0}

    def _calculate_token_efficiency(self, metrics: List[ConversationMetrics]) -> Dict[str, Any]:
        """Calcula la eficiencia de uso de tokens."""
        try:
            if not metrics:
                return {"efficiency_score": 0.0, "status": "insufficient_data"}
            
            # Calcular eficiencia basada en tokens vs satisfacción
            efficiency_scores = []
            
            for metric in metrics:
                if metric.total_tokens > 0 and metric.user_satisfaction_score:
                    # Fórmula: satisfacción / (tokens / 1000) - normalizar por 1K tokens
                    efficiency = metric.user_satisfaction_score / (metric.total_tokens / 1000)
                    efficiency_scores.append(efficiency)
            
            if not efficiency_scores:
                return {"efficiency_score": 0.0, "status": "insufficient_data"}
            
            avg_efficiency = statistics.mean(efficiency_scores)
            
            # Clasificar eficiencia
            if avg_efficiency >= 8:
                status = "excellent"
            elif avg_efficiency >= 6:
                status = "good"
            elif avg_efficiency >= 4:
                status = "fair"
            else:
                status = "poor"
            
            return {
                "efficiency_score": round(avg_efficiency, 2),
                "status": status,
                "total_conversations": len(efficiency_scores)
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando eficiencia de tokens: {e}")
            return {"efficiency_score": 0.0, "status": "error"}

    def _calculate_satisfaction_trend(self, metrics: List[ConversationMetrics]) -> Dict[str, Any]:
        """Calcula la tendencia de satisfacción del usuario."""
        try:
            satisfaction_scores = [m.user_satisfaction_score for m in metrics if m.user_satisfaction_score]
            
            if not satisfaction_scores:
                return {"trend": "stable", "change_percent": 0.0, "status": "insufficient_data"}
            
            # Dividir en dos períodos
            mid_point = len(satisfaction_scores) // 2
            first_half = satisfaction_scores[:mid_point]
            second_half = satisfaction_scores[mid_point:]
            
            if not first_half or not second_half:
                return {"trend": "stable", "change_percent": 0.0}
            
            first_avg = statistics.mean(first_half)
            second_avg = statistics.mean(second_half)
            
            if first_avg == 0:
                change_percent = 0.0
            else:
                change_percent = ((second_avg - first_avg) / first_avg) * 100
            
            # Determinar tendencia
            if change_percent > 2:
                trend = "improving"
            elif change_percent < -2:
                trend = "declining"
            else:
                trend = "stable"
            
            return {
                "trend": trend,
                "change_percent": round(change_percent, 2),
                "first_period_avg": round(first_avg, 2),
                "second_period_avg": round(second_avg, 2),
                "overall_avg": round(statistics.mean(satisfaction_scores), 2)
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error calculando tendencia de satisfacción: {e}")
            return {"trend": "error", "change_percent": 0.0}

    async def _generate_alerts(self) -> List[Dict[str, Any]]:
        """Genera alertas basadas en métricas."""
        try:
            alerts = []
            
            # Obtener métricas recientes
            recent_metrics = self.db.query(ConversationMetrics).filter(
                ConversationMetrics.created_at >= datetime.now(timezone.utc) - timedelta(hours=1)
            ).all()
            
            if not recent_metrics:
                return alerts
            
            # Alerta de latencia alta
            avg_latency = statistics.mean([float(m.latency_total_ms) for m in recent_metrics])
            if avg_latency > 5000:  # 5 segundos
                alerts.append({
                    "type": "high_latency",
                    "severity": "warning",
                    "message": f"Latencia promedio alta: {avg_latency:.0f}ms",
                    "threshold": 5000,
                    "current_value": avg_latency
                })
            
            # Alerta de ratio de cache bajo
            avg_cache_ratio = statistics.mean([float(m.cache_hit_ratio) for m in recent_metrics if m.cache_hit_ratio])
            if avg_cache_ratio < 0.7:  # 70%
                alerts.append({
                    "type": "low_cache_ratio",
                    "severity": "info",
                    "message": f"Ratio de cache bajo: {avg_cache_ratio:.1%}",
                    "threshold": 0.7,
                    "current_value": avg_cache_ratio
                })
            
            # Alerta de errores altos
            total_errors = sum(m.errors_encountered for m in recent_metrics)
            total_steps = sum(m.steps_executed for m in recent_metrics)
            if total_steps > 0:
                error_rate = total_errors / total_steps
                if error_rate > 0.1:  # 10%
                    alerts.append({
                        "type": "high_error_rate",
                        "severity": "warning",
                        "message": f"Tasa de errores alta: {error_rate:.1%}",
                        "threshold": 0.1,
                        "current_value": error_rate
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error generando alertas: {e}")
            return []

    # 🎯 Limpieza y mantenimiento

    def _cleanup_old_contexts(self):
        """Limpia contextos antiguos."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
            old_contexts = [
                conv_id for conv_id, context in self._active_contexts.items()
                if context.started_at < cutoff_time
            ]
            
            for conv_id in old_contexts:
                del self._active_contexts[conv_id]
            
            if old_contexts:
                logger.info(f"[AdvancedTelemetryService] 🗑️ Limpiados {len(old_contexts)} contextos antiguos")
                
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error limpiando contextos: {e}")

    async def _cleanup_old_metrics(self):
        """Limpia métricas antiguas según la política de retención."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            # Limpiar métricas de conversación antiguas
            deleted_conversations = self.db.query(ConversationMetrics).filter(
                ConversationMetrics.created_at < cutoff_date
            ).delete()
            
            # Limpiar métricas agregadas antiguas
            deleted_aggregated = self.db.query(AggregatedMetrics).filter(
                AggregatedMetrics.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            if deleted_conversations > 0 or deleted_aggregated > 0:
                logger.info(f"[AdvancedTelemetryService] 🗑️ Limpiadas {deleted_conversations} conversaciones y {deleted_aggregated} métricas agregadas")
                
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error limpiando métricas antiguas: {e}")

    # 🎯 Métodos de utilidad

    def get_conversation_summary(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene un resumen de una conversación específica."""
        try:
            context = self.get_conversation_context(conversation_id)
            if not context:
                return None
            
            return {
                "conversation_id": str(conversation_id),
                "user_id": str(context.user_id),
                "chat_id": str(context.chat_id),
                "mode": context.mode,
                "started_at": context.started_at.isoformat(),
                "duration_seconds": (datetime.now(timezone.utc) - context.started_at).total_seconds(),
                "tokens_in": context.tokens_in,
                "tokens_out": context.tokens_out,
                "total_tokens": context.tokens_in + context.tokens_out,
                "cache_hit_ratio": context.get_cache_hit_ratio(),
                "steps_executed": context.steps_executed,
                "errors_encountered": context.errors_encountered,
                "databases_accessed": list(context.databases_accessed),
                "apps_accessed": list(context.apps_accessed),
                "functions_executed": list(context.functions_executed)
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo resumen: {e}")
            return None

    def get_system_health(self) -> Dict[str, Any]:
        """Obtiene el estado de salud del sistema de telemetría."""
        try:
            return {
                "status": "healthy",
                "active_contexts": len(self._active_contexts),
                "metrics_buffer_size": len(self._metrics_buffer),
                "last_aggregation": self._last_aggregation.isoformat() if self._last_aggregation else None,
                "auto_aggregate_interval_hours": self.auto_aggregate_interval.total_seconds() / 3600,
                "retention_days": self.retention_days,
                "max_contexts": self.max_contexts,
                "uptime": "active"  # Se podría calcular el tiempo real de actividad
            }
            
        except Exception as e:
            logger.error(f"[AdvancedTelemetryService] ❌ Error obteniendo health: {e}")
            return {"status": "error", "message": str(e)}
