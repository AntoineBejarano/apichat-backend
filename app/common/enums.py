# app/common/enums.py
"""
Enums para tipos de eventos WebSocket, niveles de riesgo y modos de operación.
"""
from enum import Enum


class WsEventType(str, Enum):
    """Tipos de eventos WebSocket para comunicación en tiempo real."""
    STATUS_TYPING = "status.typing"
    STATUS_PROGRESS = "status.progress"
    DECISION_REQUEST = "decision.request"
    DECISION_RESPONSE = "decision.response"
    RESOURCE_PROPOSAL = "resource.proposal"
    RESOURCE_PROPOSAL_RESPONSE = "resource.proposal.response"
    RESULT_PARTIAL = "result.partial"
    RESULT_FINAL = "result.final"
    NOTICE_INFO = "notice.info"
    ERROR_USER_FACING = "error.user_facing"
    TELEMETRY_SNAPSHOT = "telemetry.snapshot"


class RiskLevel(str, Enum):
    """Niveles de riesgo para operaciones que requieren confirmación."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Mode(str, Enum):
    """Modos de operación del sistema."""
    EXPLORER = "explorer"
    GUIDED = "guided"
    FAST_SCHEMA = "fast_schema"


class EmbeddingResourceType(str, Enum):
    """Tipos de recursos para embeddings."""
    DATABASE = "database"
    API = "api"
    STRATEGY = "strategy"