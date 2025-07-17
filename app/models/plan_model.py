# models/plan_model.py
from sqlalchemy import Column, Integer, String, Float, Boolean
from app.models.base_model import Base

class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    stripe_price_id = Column(String, unique=True, nullable=False)
    price = Column(Float, nullable=False)
    features = Column(String)
    is_active = Column(Boolean, default=True)
