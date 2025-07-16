import logging
from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.function_model import Function
from app.schemas.function_schema import FunctionCreate, FunctionUpdate
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory
    
logger = logging.getLogger(__name__)


class FunctionService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

    def create(self, data: FunctionCreate) -> Function:
        logger.info(f"[FunctionService] 🛠️ Creando función '{data.name}' para usuario {self.user_id}")
        function = Function(user_id=self.user_id, **data.model_dump(), active=True)
        self.db.add(function)
        self.db.commit()
        self.db.refresh(function)
        return function

    def get_by_user(self) -> List[Function]:
        logger.debug(f"[FunctionService] 🔍 Buscando funciones para usuario {self.user_id}")
        return self.db.query(Function).filter(Function.user_id == self.user_id).all()

    def get_by_group(self, group_id: int) -> List[Function]:
        logger.debug(f"[FunctionService] 🔍 Buscando funciones para grupo {group_id}")
        return self.db.query(Function).filter(Function.group_id == group_id).all()

    def get_by_id(self, function_id: int) -> Function:
        logger.debug(f"[FunctionService] 🔍 Buscando función ID {function_id} para usuario {self.user_id}")
        function = self.db.query(Function).filter(
            Function.user_id == self.user_id,
            Function.id == function_id
        ).first()
        if not function:
            logger.warning(f"[FunctionService] ❌ Función ID {function_id} no encontrada para usuario {self.user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Function with ID {function_id} not found for user {self.user_id}."
            )
        return function

    def update(self, function_id: int, updates: FunctionUpdate) -> Function:
        logger.info(f"[FunctionService] ✏️ Actualizando función ID {function_id} para usuario {self.user_id}")
        function = self.get_by_id(function_id)
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(function, field, value)
        self.db.commit()
        self.db.refresh(function)
        return function

    def delete(self, function_id: int) -> bool:
        logger.info(f"[FunctionService] 🗑️ Eliminando función ID {function_id} para usuario {self.user_id}")
        function = self.get_by_id(function_id)
        self.db.delete(function)
        self.db.commit()
        return True

    def get_by_app(self, app_id: int) -> List[Function]:
        logger.debug(f"[FunctionService] 🔍 Buscando funciones para app {app_id} del usuario {self.user_id}")
        return self.db.query(Function).filter(
            Function.user_id == self.user_id,
            Function.app_id == app_id
        ).all()
