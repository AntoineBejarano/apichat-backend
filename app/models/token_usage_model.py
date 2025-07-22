# app/models/token_usage_model.py

from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base_model import Base  # Asegúrate de usar el mismo Base

class TokenUsage(Base):
    __tablename__ = "token_usages"  # Plural para coincidir con la relación

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=False)
    prompt_tokens     = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens      = Column(Integer, default=0)
    model             = Column(String, nullable=False)
    timestamp         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # back_populates debe coincidir con el atributo en User.token_usages
    user = relationship("User", back_populates="token_usages")
