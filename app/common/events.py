# app/common/events.py
"""
Modelos de eventos WebSocket para comunicación en tiempo real.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime

from .enums import WsEventType, RiskLevel, Mode


class BaseWsEvent(BaseModel):
    """Evento base WebSocket con timestamp y tipo."""
    type: WsEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None


class StatusTypingEvent(BaseWsEvent):
    """Evento de estado: usuario está escribiendo."""
    type: WsEventType = WsEventType.STATUS_TYPING
    is_typing: bool = True


class StatusProgressEvent(BaseWsEvent):
    """Evento de progreso: paso actual de la ejecución."""
    type: WsEventType = WsEventType.STATUS_PROGRESS
    step: int
    total_steps: int
    message: str
    percentage: Optional[float] = None


class DecisionRequestEvent(BaseWsEvent):
    """Evento de solicitud de decisión: requiere confirmación del usuario."""
    type: WsEventType = WsEventType.DECISION_REQUEST
    decision_id: str
    title: str
    description: str
    options: List[Dict[str, Any]]
    timeout_seconds: int = 30
    default_action: str = "cancel"


class DecisionResponseEvent(BaseWsEvent):
    """Evento de respuesta a decisión: confirmación del usuario."""
    type: WsEventType = WsEventType.DECISION_RESPONSE
    decision_id: str
    action: str  # "confirm", "edit", "cancel"
    user_message: Optional[str] = None  # Mensaje adicional del usuario
    selected_options: Optional[Dict[str, Any]] = None  # Opciones seleccionadas si aplica


class ResourceProposalEvent(BaseWsEvent):
    """Evento de propuesta de recursos: Explorer propone combinaciones para Guided."""
    type: WsEventType = WsEventType.RESOURCE_PROPOSAL
    proposal_id: str
    title: str
    description: str
    options: List[Dict[str, Any]]  # Lista de combinaciones DB+App
    user_message: str  # Mensaje original del usuario
    timeout_seconds: int = 60
    default_action: str = "explore_only"


class ResourceProposalResponseEvent(BaseWsEvent):
    """Evento de respuesta a propuesta de recursos: usuario elige opción."""
    type: WsEventType = WsEventType.RESOURCE_PROPOSAL_RESPONSE
    proposal_id: str
    action: str  # "guided_option_1", "guided_option_2", "see_more", "explore_only"
    selected_option: Optional[Dict[str, Any]] = None  # Opción seleccionada si aplica
    user_message: Optional[str] = None  # Mensaje adicional del usuario


class ResultPartialEvent(BaseWsEvent):
    """Evento de resultado parcial: preview de datos o progreso."""
    type: WsEventType = WsEventType.RESULT_PARTIAL
    step: int
    data: Dict[str, Any]
    preview: Optional[str] = None


class ResultFinalEvent(BaseWsEvent):
    """Evento de resultado final: respuesta completa con resumen."""
    type: WsEventType = WsEventType.RESULT_FINAL
    summary: str
    data: Dict[str, Any]
    next_actions: List[str]
    usage_stats: Optional[Dict[str, Any]] = None


class NoticeInfoEvent(BaseWsEvent):
    """Evento de información: notificaciones no críticas."""
    type: WsEventType = WsEventType.NOTICE_INFO
    message: str
    level: str = "info"  # info, warning, success
    actions: Optional[List[str]] = None


class ErrorUserFacingEvent(BaseWsEvent):
    """Evento de error: errores que el usuario debe conocer."""
    type: WsEventType = WsEventType.ERROR_USER_FACING
    code: str
    human_message: str
    suggested_actions: List[str]
    technical_details: Optional[str] = None


class TelemetrySnapshotEvent(BaseWsEvent):
    """Evento de telemetría: métricas de rendimiento y uso."""
    type: WsEventType = WsEventType.TELEMETRY_SNAPSHOT
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cache_hit_ratio: float
    steps_executed: int
    confirmations_required: int
    mode: Mode
