# app/models/function_group.py

from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.core.database import Base

# Tabla intermedia entre grupo y función
function_group_association = Table(
    'function_group_association',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('function_groups.id')),
    Column('function_id', Integer, ForeignKey('functions.id')),
)

class FunctionGroup(Base):
    __tablename__ = "function_groups"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)

    functions = relationship("Function", secondary=function_group_association, back_populates="groups")
