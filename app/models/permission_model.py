from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.models.base_model import Base
from app.models.role_model import role_permissions

class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
