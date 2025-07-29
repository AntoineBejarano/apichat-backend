from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base_model import Base


class AgentDatabaseLink(Base):
    __tablename__ = "agent_database_links"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    database_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id", ondelete="CASCADE"), primary_key=True)

    agent = relationship("Agent", back_populates="database_links")
    database = relationship("DatabaseConnection", back_populates="agent_links")
