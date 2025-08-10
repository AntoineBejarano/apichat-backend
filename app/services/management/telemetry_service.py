from typing import Dict, Any, Optional, List
from uuid import UUID
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum

from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Tipos de eventos de telemetría"""
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    CACHE_REFRESH = "cache_refresh"
    SCHEMA_WARM_UP = "schema_warm_up"
    APP_DESCRIPTOR_LOAD = "app_descriptor_load"
    INTENT_CLASSIFICATION = "intent_classification"
    PLAN_GENERATION = "plan_generation"
    PLAN_EXECUTION = "plan_execution"
    ERROR_RECOVERY = "error_recovery"
    GUIDED_MODE_FLOW = "guided_mode_flow"


@dataclass
class TelemetryEvent:
    """Evento de telemetría"""
    event_type: EventType
    user_id: UUID
    timestamp: datetime
    duration_ms: Optional[float] = None
    success: bool = True
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el evento a diccionario para logging"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['user_id'] = str(self.user_id)
        return data


class TelemetryService(BaseService):
    """
    Servicio para recolectar y procesar telemetría del sistema.
    Rastrea eventos de cache, performance y errores.
    """
    
    def __init__(self, factory):
        super().__init__(factory)
        self._events: List[TelemetryEvent] = []
        self._session_stats: Dict[str, Any] = {}
        self.max_events = 1000  # Límite de eventos en memoria
    
    def track_event(
        self,
        event_type: EventType,
        user_id: UUID,
        duration_ms: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Registra un evento de telemetría"""
        try:
            event = TelemetryEvent(
                event_type=event_type,
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                success=success,
                metadata=metadata or {},
                error_message=error_message
            )
            
            self._events.append(event)
            
            # Limpiar eventos antiguos si excedemos el límite
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events//2:]  # Mantener la mitad más reciente
            
            # Log del evento
            self._log_event(event)
            
            # Actualizar estadísticas de sesión
            self._update_session_stats(event)
            
        except Exception as e:
            logger.exception(f"[TelemetryService] ❌ Error registrando evento {event_type}: {e}")
    
    def track_cache_operation(
        self,
        user_id: UUID,
        operation: str,  # "hit", "miss", "refresh"
        resource_type: str,  # "db_schema", "app_descriptor"
        resource_id: str,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Registra operación de cache específica"""
        event_type_map = {
            "hit": EventType.CACHE_HIT,
            "miss": EventType.CACHE_MISS,
            "refresh": EventType.CACHE_REFRESH
        }
        
        event_type = event_type_map.get(operation, EventType.CACHE_HIT)
        
        combined_metadata = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            **(metadata or {})
        }
        
        self.track_event(
            event_type=event_type,
            user_id=user_id,
            duration_ms=duration_ms,
            success=True,
            metadata=combined_metadata
        )
    
    def track_guided_mode_flow(
        self,
        user_id: UUID,
        flow_step: str,  # "classify_intent", "check_resources", "warm_up", "plan_or_reply"
        duration_ms: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Registra paso del flujo de Guided Mode"""
        combined_metadata = {
            "flow_step": flow_step,
            **(metadata or {})
        }
        
        self.track_event(
            event_type=EventType.GUIDED_MODE_FLOW,
            user_id=user_id,
            duration_ms=duration_ms,
            success=success,
            metadata=combined_metadata,
            error_message=error_message
        )
    
    def get_session_stats(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Obtiene estadísticas de la sesión actual"""
        if user_id:
            return self._session_stats.get(str(user_id), {})
        return self._session_stats
    
    def get_recent_events(
        self,
        user_id: Optional[UUID] = None,
        event_type: Optional[EventType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Obtiene eventos recientes con filtros opcionales"""
        filtered_events = self._events
        
        if user_id:
            filtered_events = [e for e in filtered_events if e.user_id == user_id]
        
        if event_type:
            filtered_events = [e for e in filtered_events if e.event_type == event_type]
        
        # Ordenar por timestamp descendente y limitar
        sorted_events = sorted(filtered_events, key=lambda x: x.timestamp, reverse=True)
        return [event.to_dict() for event in sorted_events[:limit]]
    
    def get_cache_metrics(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Obtiene métricas específicas de cache"""
        events = self._events
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        cache_events = [e for e in events if e.event_type in [EventType.CACHE_HIT, EventType.CACHE_MISS, EventType.CACHE_REFRESH]]
        
        if not cache_events:
            return {
                "total_operations": 0,
                "hit_rate": 0.0,
                "avg_duration_ms": 0.0,
                "refresh_count": 0
            }
        
        hits = [e for e in cache_events if e.event_type == EventType.CACHE_HIT]
        misses = [e for e in cache_events if e.event_type == EventType.CACHE_MISS]
        refreshes = [e for e in cache_events if e.event_type == EventType.CACHE_REFRESH]
        
        total_ops = len(hits) + len(misses)
        hit_rate = len(hits) / total_ops if total_ops > 0 else 0.0
        
        # Calcular duración promedio (solo eventos con duración)
        events_with_duration = [e for e in cache_events if e.duration_ms is not None]
        avg_duration = sum(e.duration_ms for e in events_with_duration) / len(events_with_duration) if events_with_duration else 0.0
        
        return {
            "total_operations": total_ops,
            "hits": len(hits),
            "misses": len(misses),
            "hit_rate": hit_rate,
            "avg_duration_ms": avg_duration,
            "refresh_count": len(refreshes)
        }
    
    def get_performance_metrics(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Obtiene métricas de performance"""
        events = self._events
        if user_id:
            events = [e for e in events if e.user_id == user_id]
        
        # Filtrar eventos con duración
        timed_events = [e for e in events if e.duration_ms is not None]
        
        if not timed_events:
            return {
                "total_events": 0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0
            }
        
        durations = [e.duration_ms for e in timed_events]
        
        return {
            "total_events": len(timed_events),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "success_rate": len([e for e in timed_events if e.success]) / len(timed_events)
        }
    
    def clear_events(self, user_id: Optional[UUID] = None):
        """Limpia eventos (opcionalmente solo de un usuario)"""
        if user_id:
            self._events = [e for e in self._events if e.user_id != user_id]
            if str(user_id) in self._session_stats:
                del self._session_stats[str(user_id)]
        else:
            self._events.clear()
            self._session_stats.clear()
        
        logger.info(f"[TelemetryService] 🗑️ Eventos limpiados para usuario: {user_id or 'todos'}")
    
    def _log_event(self, event: TelemetryEvent):
        """Log interno del evento"""
        duration_str = f" ({event.duration_ms:.1f}ms)" if event.duration_ms else ""
        success_str = "✅" if event.success else "❌"
        
        metadata_str = ""
        if event.metadata:
            key_items = []
            for key, value in event.metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    key_items.append(f"{key}={value}")
            if key_items:
                metadata_str = f" [{', '.join(key_items)}]"
        
        error_str = f" Error: {event.error_message}" if event.error_message else ""
        
        logger.info(f"[Telemetry] {success_str} {event.event_type.value}{duration_str}{metadata_str}{error_str}")
    
    def _update_session_stats(self, event: TelemetryEvent):
        """Actualiza estadísticas de sesión"""
        user_key = str(event.user_id)
        
        if user_key not in self._session_stats:
            self._session_stats[user_key] = {
                "total_events": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "errors": 0,
                "last_activity": None
            }
        
        stats = self._session_stats[user_key]
        stats["total_events"] += 1
        stats["last_activity"] = event.timestamp.isoformat()
        
        if event.event_type == EventType.CACHE_HIT:
            stats["cache_hits"] += 1
        elif event.event_type == EventType.CACHE_MISS:
            stats["cache_misses"] += 1
        
        if not event.success:
            stats["errors"] += 1


class TelemetryContextManager:
    """Context manager para medir duración de operaciones"""
    
    def __init__(
        self,
        telemetry_service: TelemetryService,
        event_type: EventType,
        user_id: UUID,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.telemetry_service = telemetry_service
        self.event_type = event_type
        self.user_id = user_id
        self.metadata = metadata or {}
        self.start_time = None
        self.success = True
        self.error_message = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)
        
        self.telemetry_service.track_event(
            event_type=self.event_type,
            user_id=self.user_id,
            duration_ms=duration_ms,
            success=self.success,
            metadata=self.metadata,
            error_message=self.error_message
        )
        
        return False  # No suprimir excepciones
