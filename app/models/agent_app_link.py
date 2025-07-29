from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base_model import Base


class AgentAppLink(Base):
    __tablename__ = "agent_app_links"

    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id", ondelete="CASCADE"), primary_key=True)

    agent = relationship("Agent", back_populates="app_links")
    app = relationship("App", back_populates="agent_links")
