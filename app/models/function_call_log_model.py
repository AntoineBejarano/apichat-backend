from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class FunctionCallLog(Base):
    __tablename__ = "function_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    function_id = Column(Integer, ForeignKey("functions.id"), nullable=False)
    token_count = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Relación inversa a ChatHistory
    chat_history = relationship(
        "ChatHistory",
        back_populates="function_call",
        uselist=False
    )
