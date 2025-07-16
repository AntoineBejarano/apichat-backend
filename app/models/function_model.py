from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=True)

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)  # Para OpenAI function calling

    code = Column(Text, nullable=True)  # Solo si es función local
    execution_type = Column(String, default="python")  # "python" o "http"
    method = Column(String, nullable=True)  # GET, POST, etc.
    url = Column(String, nullable=True)  # Si execution_type = "http"
    headers = Column(JSON, nullable=True)
    body = Column(JSON, nullable=True)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="functions")
    app = relationship("App", back_populates="functions")
    integration = relationship("Integration", back_populates="functions")
    groups = relationship("FunctionGroup", secondary="function_group_association", back_populates="functions")
    proxy_id   = Column(Integer, ForeignKey("proxies.id"), nullable=True)
    proxy      = relationship("Proxy", back_populates="functions")
