import logging
from fastapi import HTTPException
from typing import List, Dict

from app.models.event_trigger_model import EventTrigger
from app.models.event_definition_model import EventDefinition
from app.schemas.event_trigger_schema import EventTriggerCreate
from app.services.base_service import BaseService

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class EventTriggerService(BaseService):
    def __init__(self, factory: "ServiceFactory"):
        super().__init__(factory)
        logger.info(f"[EventTriggerService] ✅ Initialized for user_id={self.user.id}")

    # ----------------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------------
    def create(self, data: EventTriggerCreate) -> EventTrigger:
        logger.info(f"[EventTriggerService] ➕ Creating new EventTrigger for user_id={self.user.id}")

        definition = self.db.query(EventDefinition).filter(
            EventDefinition.id == data.event_definition_id,
            EventDefinition.is_active == True
        ).first()

        if not definition:
            raise HTTPException(status_code=400, detail="Invalid or inactive event_definition_id")

        missing = [
            field for field in definition.required_fields
            if field not in data.config
        ]
        if missing:
            logger.warning(f"[EventTriggerService] ❌ Missing fields in config: {missing}")
            raise HTTPException(status_code=400, detail=f"Missing fields in config: {missing}")

        trigger = EventTrigger(
            **data.model_dump(),
            user_id=self.user.id
        )

        self.db.add(trigger)
        self.db.commit()
        self.db.refresh(trigger)

        logger.info(f"[EventTriggerService] ✅ Created EventTrigger ID={trigger.id}")
        return trigger

    # ----------------------------------------------------------------
    # READ
    # ----------------------------------------------------------------
    def get_all(self) -> List[EventTrigger]:
        logger.info(f"[EventTriggerService] 📦 Getting all EventTriggers for user_id={self.user.id}")
        return self.db.query(EventTrigger).filter(EventTrigger.user_id == self.user.id).all()

    def get_by_id(self, event_trigger_id: str) -> EventTrigger:
        logger.info(f"[EventTriggerService] 🔍 Fetching EventTrigger ID={event_trigger_id}")
        event_trigger = self.db.query(EventTrigger).filter(
            EventTrigger.id == event_trigger_id,
            EventTrigger.user_id == self.user.id
        ).first()
        if not event_trigger:
            raise HTTPException(status_code=404, detail="EventTrigger not found")
        return event_trigger

    # ----------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------
    def delete(self, event_trigger_id: str) -> dict:
        logger.info(f"[EventTriggerService] 🗑️ Deleting EventTrigger ID={event_trigger_id}")
        event_trigger = self.get_by_id(event_trigger_id)
        self.db.delete(event_trigger)
        self.db.commit()
        return {"detail": "EventTrigger deleted"}
