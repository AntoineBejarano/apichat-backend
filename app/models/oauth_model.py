from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    integration_id = Column(Integer, ForeignKey("integrations.id"))

    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    oauth_metadata = Column(JSON, nullable=True)  # Info adicional: workspace_id, user_email, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="oauth_accounts")
    integration = relationship("Integration", back_populates="oauth_accounts")
