# app/services/base_service.py

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan

class BaseService:
    def __init__(self, factory, user=None):
        self.db: Session = factory.db
        self.factory = factory
        self.user = user or getattr(factory, "user", None)  # ← evita explotar si no hay request
        
    def check_limit(self, model_class, limit_field: str, label: str = "items"):
        """
        Verifica si el usuario ha alcanzado el límite de recursos según su plan.

        :param model_class: Modelo a contar (ej: App, Function...)
        :param limit_field: Campo del modelo Plan que define el límite (ej: 'max_agents').
        :param label: Texto del recurso para el mensaje de error.
        """
        current_count = self.db.query(model_class).filter_by(user_id=self.user.id).count()

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
                detail=f"Límite alcanzado: tu plan solo permite {max_allowed} {label}"
            )
