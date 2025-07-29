import uuid
from sqlalchemy import Column, String, ForeignKey, JSON, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base
from app.models.function_group_model import function_group_association


class Function(Base):
    __tablename__ = "functions"

    id             = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    app_id         = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=False)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("openapi_integrations.id"), nullable=True)

    name           = Column(String, nullable=False)
    description    = Column(Text, nullable=True)
    parameters     = Column(JSON, nullable=True)

    code           = Column(Text, nullable=True)
    execution_type = Column(String, default="python")
    method         = Column(String, nullable=True)
    url            = Column(String, nullable=True)
    headers        = Column(JSON, nullable=True)
    body           = Column(JSON, nullable=True)
    active         = Column(Boolean, default=True)
    timeout = Column(Integer, default=30)
    is_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones a modelos padres
    app         = relationship("App", back_populates="functions")

    # Relación many-to-many con FunctionGroup
    groups = relationship(
        "FunctionGroup",
        secondary=function_group_association,
        back_populates="functions"
    )

    # 🔗 Nueva relación con FunctionCallLog (uno a muchos)
    calls = relationship("FunctionCallLog", back_populates="function", cascade="all, delete-orphan")
