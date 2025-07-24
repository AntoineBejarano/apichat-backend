import logging
from fastapi import HTTPException
from typing import List, Dict

from app.models.trigger_model import Trigger
from app.models.event_trigger_model import EventTrigger
from app.schemas.trigger_schema import TriggerCreate
from app.services.base_service import BaseService

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class TriggerService(BaseService):
    def __init__(self, factory: "ServiceFactory"):
        super().__init__(factory)
        logger.info(f"[TriggerService] ✅ Initialized for user_id={self.user_id}")

    # ----------------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------------
    def create(self, data: TriggerCreate) -> Trigger:
        logger.info(f"[TriggerService] ➕ Creating new Trigger for user_id={self.user_id}")

        event_trigger = self.db.query(EventTrigger).filter(
            EventTrigger.id == data.event_trigger_id,
            EventTrigger.user_id == self.user_id
        ).first()

        if not event_trigger:
            raise HTTPException(status_code=400, detail="Invalid or unauthorized event_trigger_id")

        trigger = Trigger(**data.model_dump(), user_id=self.user_id)
        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)

        logger.info(f"[TriggerService] ✅ Trigger created with ID={trigger.id}")
        return trigger

    # ----------------------------------------------------------------
    # READ
    # ----------------------------------------------------------------
    def get_all(self) -> List[Trigger]:
        logger.info(f"[TriggerService] 📦 Getting all Triggers for user_id={self.user_id}")
        return self.db.query(Trigger).filter(Trigger.user_id == self.user_id).all()

    def get_by_id(self, trigger_id: str) -> Trigger:
        logger.info(f"[TriggerService] 🔍 Fetching Trigger ID={trigger_id}")
        trigger = self.db.query(Trigger).filter(
            Trigger.id == trigger_id,
            Trigger.user_id == self.user_id
        ).first()
        if not trigger:
            raise HTTPException(status_code=404, detail="Trigger not found")
        return trigger

    # ----------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------
    def delete(self, trigger_id: str) -> dict:
        logger.info(f"[TriggerService] 🗑️ Deleting Trigger ID={trigger_id}")
        trigger = self.get_by_id(trigger_id)
        self.db.delete(trigger)
        self.db.commit()
        return {"detail": "Trigger deleted"}
