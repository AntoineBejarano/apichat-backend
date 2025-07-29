# app/services/function_service.py

import logging
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.function_model import Function
from app.models.app_model import App
from app.schemas.function_schema import FunctionCreate, FunctionUpdate
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class FunctionService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

    def _get_app_or_404(self, app_id: int) -> App:
        app = self.db.query(App).filter(App.id == app_id, App.user_id == self.user_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="App no encontrada o no pertenece al usuario.")
        return app

    def create(self, data: FunctionCreate) -> Function:
        self._get_app_or_404(str(data.app_id))  # Asegúrate de que sea UUID o str
        logger.info(f"[FunctionService] ➕ Creando función '{data.name}' para app_id={data.app_id}")
        function = Function(**data.model_dump())
        self.db.add(function)
        self.db.commit()
        self.db.refresh(function)
        return function


    def get_by_app(self, app_id: int) -> List[Function]:
        self._get_app_or_404(app_id)
        return self.db.query(Function).filter(Function.app_id == app_id).all()

    def get_by_id(self, app_id: int, function_id: int) -> Function:
        self._get_app_or_404(app_id)
        function = self.db.query(Function).filter(Function.id == function_id, Function.app_id == app_id).first()
        if not function:
            raise HTTPException(status_code=404, detail="Función no encontrada en esta app.")
        return function

    def update(self, app_id: int, function_id: int, updates: FunctionUpdate) -> Function:
        function = self.get_by_id(app_id, function_id)
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(function, field, value)
        self.db.commit()
        self.db.refresh(function)
        return function

    def delete(self, app_id: int, function_id: int) -> bool:
        function = self.get_by_id(app_id, function_id)
        self.db.delete(function)
        self.db.commit()
        return True
