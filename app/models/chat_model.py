from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Configuración asociada al chat
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    database_id = Column(Integer, ForeignKey("database_connections.id"), nullable=True)
    system_prompt = Column(Text, nullable=True)

    title = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    user = relationship("User", back_populates="chats")
    app = relationship("App")
    agent = relationship("Agent")
    database = relationship("DatabaseConnection")
    history = relationship("ChatHistory", back_populates="chat", cascade="all, delete-orphan")
