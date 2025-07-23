# app/services/base_service.py

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan

class BaseService:
    def __init__(self, db: Session, user):
        self.db = db
        self.user = user

    def check_limit(self, current_count: int, limit_field: str):
        """
        Verifica si el usuario ha alcanzado el límite de recursos según su plan.

        :param current_count: Número actual de elementos creados por el usuario.
        :param limit_field: Campo del modelo Plan que define el límite (ej: 'max_agents').
        :raises HTTPException: Si se supera el límite.
        """
        plan = self.db.query(Plan).join(Subscription).filter(
            Subscription.user_id == self.user.id,
            Subscription.is_active == True
        ).first()

        if not plan:
            raise HTTPException(status_code=400, detail="No active subscription or plan found")

        max_allowed = getattr(plan, limit_field, None)
        if max_allowed is not None and current_count >= max_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Límite alcanzado: tu plan solo permite {max_allowed} elementos para '{limit_field}'"
            )
