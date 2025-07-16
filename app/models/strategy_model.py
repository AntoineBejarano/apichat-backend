from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null si es global
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    steps = Column(JSON, nullable=False)  # Array de steps con funciones y dependencias

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="strategies")
