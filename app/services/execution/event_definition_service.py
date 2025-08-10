import logging
from fastapi import HTTPException
from typing import List, Optional

from app.models.event_definition_model import EventDefinition
from app.schemas.event_definition_schema import (
    EventDefinitionCreate,
    EventDefinitionUpdate,
)
from app.services.base_service import BaseService

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class EventDefinitionService(BaseService):
    def __init__(self, factory: "ServiceFactory"):
        super().__init__(factory)
        logger.info(f"[EventDefinitionService] ✅ Initialized for user_id={self.user.id}")

    # ----------------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------------
    def create(self, data: EventDefinitionCreate) -> EventDefinition:
        logger.info(f"[EventDefinitionService] ➕ Creating new EventDefinition: {data.name}")
        
        existing = self.db.query(EventDefinition).filter(EventDefinition.name == data.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="EventDefinition with this name already exists")

        event_def = EventDefinition(**data.model_dump())
        self.db.add(event_def)
        self.db.commit()
        self.db.refresh(event_def)
        logger.info(f"[EventDefinitionService] ✅ Created EventDefinition ID={event_def.id}")
        return event_def

    # ----------------------------------------------------------------
    # READ
    # ----------------------------------------------------------------
    def get_all(self, only_active: bool = True) -> List[EventDefinition]:
        logger.info(f"[EventDefinitionService] 📦 Getting all EventDefinitions for user_id={self.user.id}")
        query = self.db.query(EventDefinition)
        if only_active:
            query = query.filter(EventDefinition.is_active == True)
        return query.all()

    def get_by_id(self, event_def_id: str) -> EventDefinition:
        logger.info(f"[EventDefinitionService] 🔍 Fetching EventDefinition ID={event_def_id} for user_id={self.user.id}")
        event_def = self.db.query(EventDefinition).filter(EventDefinition.id == event_def_id).first()
        if not event_def:
            raise HTTPException(status_code=404, detail="EventDefinition not found")
        return event_def

    # ----------------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------------
    def update(self, event_def_id: str, data: EventDefinitionUpdate) -> EventDefinition:
        logger.info(f"[EventDefinitionService] ✏️ Updating EventDefinition ID={event_def_id} for user_id={self.user.id}")
        event_def = self.get_by_id(event_def_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(event_def, field, value)

        self.db.commit()
        self.db.refresh(event_def)
        logger.info(f"[EventDefinitionService] ✅ Updated EventDefinition ID={event_def.id}")
        return event_def

    # ----------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------
    def delete(self, event_def_id: str) -> dict:
        logger.info(f"[EventDefinitionService] 🗑️ Deleting EventDefinition ID={event_def_id} for user_id={self.user.id}")
        event_def = self.get_by_id(event_def_id)
        self.db.delete(event_def)
        self.db.commit()
        return {"detail": "EventDefinition deleted"}

    def get_or_create_by_code(self, code: str, name: str, description: str, payload_schema: dict):
        logger.info(f"[EventDefinitionService] 🔁 get_or_create_by_code for user_id={self.user.id}")
        existing = self.db.query(EventDefinition).filter_by(code=code).first()
        if existing:
            return existing
        event = EventDefinition(
            code=code,
            name=name,
            description=description,
            payload_schema=payload_schema
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        logger.info(f"[EventDefinitionService] ✅ Created new EventDefinition from code: {code}")
        return event
