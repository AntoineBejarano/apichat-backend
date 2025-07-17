from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=True)

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)  # OpenAI function calling

    code = Column(Text, nullable=True)  # Si es función local
    execution_type = Column(String, default="python")  # "python" o "http"
    method = Column(String, nullable=True)
    url = Column(String, nullable=True)
    headers = Column(JSON, nullable=True)
    body = Column(JSON, nullable=True)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    app = relationship("App", back_populates="functions")
    integration = relationship("Integration", back_populates="functions")
    groups = relationship("FunctionGroup", secondary="function_group_association", back_populates="functions")
