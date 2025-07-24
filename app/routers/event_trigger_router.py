from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.event_trigger_schema import (
    EventTriggerCreate,
    EventTriggerOut
)

router = APIRouter(
    prefix="/event-triggers",
    tags=["🔔 Event Triggers"],
    responses={404: {"description": "EventTrigger not found"}},
)


# Dependency: inyectar ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# ----------------------------------------------------------------
# CREATE
# ----------------------------------------------------------------
@router.post(
    "/",
    summary="Crear un EventTrigger",
    response_model=EventTriggerOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event_trigger(
    data: EventTriggerCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    service = factory.get_event_trigger_service()
    return service.create(data)


# ----------------------------------------------------------------
# LIST
# ----------------------------------------------------------------
@router.get(
    "/",
    summary="Listar todos los EventTriggers del usuario",
    response_model=List[EventTriggerOut],
)
def list_event_triggers(factory: ServiceFactory = Depends(get_factory)):
    service = factory.get_event_trigger_service()
    return service.get_all()


# ----------------------------------------------------------------
# GET BY ID
# ----------------------------------------------------------------
@router.get(
    "/{event_trigger_id}",
    summary="Obtener EventTrigger por ID",
    response_model=EventTriggerOut,
)
def get_event_trigger(
    event_trigger_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    service = factory.get_event_trigger_service()
    return service.get_by_id(event_trigger_id)


# ----------------------------------------------------------------
# DELETE
# ----------------------------------------------------------------
@router.delete(
    "/{event_trigger_id}",
    summary="Eliminar EventTrigger",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_event_trigger(
    event_trigger_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    service = factory.get_event_trigger_service()
    service.delete(event_trigger_id)
