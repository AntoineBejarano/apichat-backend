from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base_model import Base

class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    model = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="token_usage")
