import logging
from fastapi import HTTPException
from typing import List

from app.models.app_model import App
from app.schemas.app_schema import AppCreate, AppUpdate
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory
    
logger = logging.getLogger(__name__)

class AppService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        logger.info(f"[AppService] Inicializado para user_id={self.user_id}")

    def create(self, app_data: AppCreate) -> App:
        logger.info(f"[AppService] Creando nueva App para user_id={self.user_id}")
        new_app = App(**app_data.dict(), user_id=self.user_id)
        self.db.add(new_app)
        self.db.commit()
        self.db.refresh(new_app)
        return new_app

    def get_all(self) -> List[App]:
        logger.info(f"[AppService] Obteniendo todas las Apps para user_id={self.user_id}")
        return self.db.query(App).filter(App.user_id == self.user_id).all()

    def get_by_id(self, app_id: int) -> App:
        logger.info(f"[AppService] Buscando App ID={app_id} para user_id={self.user_id}")
        app = self.db.query(App).filter(App.id == app_id, App.user_id == self.user_id).first()
        if not app:
            logger.error(f"[AppService] App ID={app_id} no encontrada para user_id={self.user_id}")
            raise HTTPException(status_code=404, detail="App not found")
        return app

    def update(self, app_id: int, app_data: AppUpdate) -> App:
        logger.info(f"[AppService] Actualizando App ID={app_id} para user_id={self.user_id}")
        app = self.get_by_id(app_id)
        for field, value in app_data.dict(exclude_unset=True).items():
            setattr(app, field, value)
        self.db.commit()
        self.db.refresh(app)
        return app

    def delete(self, app_id: int) -> dict:
        logger.info(f"[AppService] Eliminando App ID={app_id} para user_id={self.user_id}")
        app = self.get_by_id(app_id)
        self.db.delete(app)
        self.db.commit()
        return {"detail": "App deleted successfully"}
