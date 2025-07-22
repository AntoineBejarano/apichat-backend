from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base  # Usa el mismo Base que el resto

class OpenAPIIntegration(Base):
    __tablename__ = "openapi_integrations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # 🔑 FK a users.id

    title    = Column(String, nullable=False)
    version  = Column(String, nullable=True)
    base_url = Column(String, nullable=True)
    raw_json = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación inversa con User.openapi_integrations
    user = relationship("User", back_populates="openapi_integrations")
