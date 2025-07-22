# app/models/permission_model.py

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base_model import Base   # ← Importa Base desde aquí

class Permission(Base):
    __tablename__ = "permissions"  # tabla en plural

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(String, unique=True, index=True, nullable=False)
    name        = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ↔ Relación bidireccional con Role.permissions
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions"
    )
