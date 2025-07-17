# schemas/billing_schema.py
from pydantic import BaseModel, HttpUrl

class BillingSessionCreate(BaseModel):
    plan_id: int
    success_url: HttpUrl
    cancel_url: HttpUrl

class SubscriptionOut(BaseModel):
    plan_name: str
    is_active: bool
    current_period_end: str
