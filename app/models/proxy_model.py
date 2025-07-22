# app/models/proxy_model.py

from sqlalchemy import (
    Column, Integer, String, JSON, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class Proxy(Base):
    __tablename__ = "proxies"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    name            = Column(String, nullable=False)
    base_url        = Column(String, nullable=False)
    default_headers = Column(JSON, nullable=True, default={})
    auth            = Column(JSON, nullable=True)            # tokens, keys, etc.
    active          = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 🔗 Relación con User
    user = relationship(
        "User",
        back_populates="proxies"
    )

    # Relación inversa a App.proxy
    apps = relationship(
        "App",
        back_populates="proxy",
        cascade="all, delete-orphan"
    )
