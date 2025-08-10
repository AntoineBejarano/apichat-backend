import logging
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.integration_model import Integration
from app.schemas.integration_schema import IntegrationCreate
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class IntegrationService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user = factory.user

    def create(self, data: IntegrationCreate) -> Integration:
        logger.info(f"[IntegrationService] ➕ Creando integración '{data.service_name}' para usuario {self.user.id}")
        integration = Integration(user_id=self.user.id, **data.model_dump())
        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)
        return integration

    def get_by_user(self) -> List[Integration]:
        logger.debug(f"[IntegrationService] 🔍 Obteniendo integraciones para usuario {self.user.id}")
        return self.db.query(Integration).filter(Integration.user_id == self.user.id).all()

    def get_by_service(self, service_name: str) -> Optional[Integration]:
        logger.debug(f"[IntegrationService] 🔍 Buscando integración '{service_name}' para usuario {self.user.id}")
        return self.db.query(Integration).filter_by(
            user_id=self.user.id,
            service_name=service_name
        ).first()
