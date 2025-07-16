from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    contextai: Optional[str] = None  # Prompt opcional
    app_id: Optional[int] = None
    agent_id: Optional[int] = None
    database_id: Optional[int] = None
    user_id: Optional[int] = None  # Lo necesitas si no usas JWT

class ChatResponse(BaseModel):
    content: str
    function_call: Optional[dict] = None
    tokens_used: Optional[int] = None
    timestamp: datetime
