import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import BaseTable

class DatabaseConnection(BaseTable):
    __tablename__ = "database_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    name = Column(String, nullable=False)
    db_type = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 🔧 NUEVO: Estado del schema para tracking
    schema_status = Column(String, nullable=False, default="pending", 
                          comment="Estado del schema: pending, generating, ready, error")

    user = relationship("User", back_populates="databases")
    agent_links = relationship("AgentDatabaseLink", back_populates="database", cascade="all, delete-orphan")
