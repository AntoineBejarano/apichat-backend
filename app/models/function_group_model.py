import uuid
from sqlalchemy import Table, Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base_model import Base

# Tabla intermedia con UUIDs
function_group_association = Table(
    'function_group_association',
    Base.metadata,
    Column('group_id', UUID(as_uuid=True), ForeignKey('function_groups.id'), primary_key=True),
    Column('function_id', UUID(as_uuid=True), ForeignKey('functions.id'), primary_key=True),
)

class FunctionGroup(Base):
    __tablename__ = "function_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name = Column(String, nullable=False)

    functions = relationship(
        "Function",
        secondary=function_group_association,
        back_populates="groups"
    )
