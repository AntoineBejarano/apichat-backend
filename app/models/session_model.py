from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")