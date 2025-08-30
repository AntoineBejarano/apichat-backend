from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.subscription_model import Subscription
from app.models.plan_model import UserPlan

class BaseService:
    def __init__(self, factory, user=None):
        # 🔧 ROMPER CICLO RECURSIVO: No llamar a get_database_service() aquí
        self.db: Session = None  # Se establecerá después de la inicialización
        self.factory = factory
        self.user = user or getattr(factory, "user", None)
        
        # 🔧 Establecer la base de datos después de la inicialización completa
        self._setup_database()
    
    def _setup_database(self):
        """Configura la base de datos después de la inicialización completa"""
        try:
            # 🔧 ROMPER CICLO RECURSIVO: Solo obtener DB si no es DatabaseService
            if not hasattr(self, '__class__') or 'DatabaseService' not in self.__class__.__name__:
                self.db = self.factory.get_database_session()
            else:
                # Para DatabaseService, no hacer nada aquí
                pass
        except Exception as e:
            # Fallback: intentar acceder directamente si existe
            self.db = getattr(self.factory, "db", None)

    def get_active_plan(self) -> UserPlan:
        """
        Devuelve el plan activo del usuario o lanza un error si no tiene ninguno.
        """
        subscription = self.db.query(Subscription).filter(
            Subscription.user_id == self.user.id,
            Subscription.is_active == True
        ).first()

        if not subscription or not subscription.plan:
            raise HTTPException(status_code=400, detail="No active subscription or plan found")

        return subscription.plan

    def check_limit(self, model_class, limit_field: str, label: str = "items"):
        """
        Verifica si el usuario ha alcanzado el límite de recursos según su plan.

        :param model_class: Modelo a contar (ej: App, Function...).
        :param limit_field: Campo del modelo Plan que define el límite (ej: 'max_agents').
        :param label: Texto del recurso para el mensaje de error.
        """
        plan = self.get_active_plan()
        current_count = self.db.query(model_class).filter_by(user_id=self.user.id).count()
        max_allowed = getattr(plan, limit_field, None)

        if max_allowed is not None and current_count >= max_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Límite alcanzado: tu plan solo permite {max_allowed} {label}."
            )
