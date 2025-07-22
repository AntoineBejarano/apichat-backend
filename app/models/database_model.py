# app/models/database_model.py

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import Base

class DatabaseConnection(Base):
    __tablename__ = "database_connections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String, nullable=False)
    db_type = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 🔗 Relación en STRING para evitar import circular
    user = relationship("User", back_populates="databases")
