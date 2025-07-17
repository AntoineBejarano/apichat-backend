# models/subscription_model.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base_model import Base

class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_subscription_id = Column(String, nullable=False)
    stripe_customer_id = Column(String, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("Plan")
    user = relationship("User", back_populates="subscriptions")
