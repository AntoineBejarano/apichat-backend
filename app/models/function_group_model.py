from sqlalchemy import Table, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base_model import Base

# Tabla intermedia
function_group_association = Table(
    'function_group_association',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('function_groups.id'), primary_key=True),
    Column('function_id', Integer, ForeignKey('functions.id'), primary_key=True),
)

class FunctionGroup(Base):
    __tablename__ = "function_groups"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)

    # ❌ Quitamos delete-orphan aquí
    functions = relationship(
        "Function",
        secondary=function_group_association,
        back_populates="groups"
    )
