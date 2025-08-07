# app/schemas/chat_history_schema.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ──────────────────────────────────────────────────────
#   Schemas
# ──────────────────────────────────────────────────────
class ChatHistoryBase(BaseModel):
    role: str
    content: str
    name: Optional[str] = None
    token_count: Optional[int] = None
    is_function_call: bool = False
    function_call_id: Optional[UUID] = None   # ID de la llamada a función
    executed_strategy_id: Optional[UUID] = None  # Estrategia ejecutada
    user_id: Optional[UUID] = None            # Para trazabilidad

    # No se construye normalmente desde un ORM
    model_config = ConfigDict(from_attributes=False)


class ChatHistoryCreate(ChatHistoryBase):
    chat_id: UUID   # obligatorio al crear


class ChatHistoryOut(ChatHistoryBase):
    id: UUID
    chat_id: UUID
    timestamp: datetime

    # ✅ Permitimos construir el schema a partir de instancias ORM
    model_config = ConfigDict(from_attributes=True)
