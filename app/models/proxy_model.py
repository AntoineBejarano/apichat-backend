from sqlalchemy import Column, String, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base
import uuid

class Proxy(Base):
    __tablename__ = "proxies"

    id              = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name            = Column(String, nullable=False)
    base_url        = Column(String, nullable=False)
    default_headers = Column(JSON, nullable=True, default={})
    auth            = Column(JSON, nullable=True)            # tokens, keys, etc.
    active          = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 🔗 Relación con User
    user = relationship("User", back_populates="proxies")

    # Relación inversa a App.proxy
    apps = relationship("App", back_populates="proxy", cascade="all, delete-orphan")
