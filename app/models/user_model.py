from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_model import Base
from app.models.role_model import user_roles
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación con Plan (opcional)
    plan_id = Column(ForeignKey("plans.id"), nullable=True)
    plan = relationship("Plan")

    # Relaciones 1:N
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    apps = relationship("App", back_populates="user", cascade="all, delete-orphan")
    databases = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    token_usages = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    openapi_integrations = relationship("OpenAPIIntegration", back_populates="user", cascade="all, delete-orphan")
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan")

    # Relaciones N:M
    roles = relationship("Role", secondary=user_roles, back_populates="users")

    # Métodos para gestionar contraseñas
    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        if not self.hashed_password:
            return False
        return pwd_context.verify(password, self.hashed_password)
