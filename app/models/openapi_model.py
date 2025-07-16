from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class OpenAPIIntegration(Base):
    __tablename__ = "openapi_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    version = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    raw_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="openapi_integrations")
