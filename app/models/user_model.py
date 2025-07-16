from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    apps = relationship("App", back_populates="user", cascade="all, delete-orphan")
    databases = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    functions = relationship("Function", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    chat_histories = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    token_usages = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")
