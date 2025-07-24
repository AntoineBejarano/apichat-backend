from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.event_definition_schema import (
    EventDefinitionCreate,
    EventDefinitionUpdate,
    EventDefinitionOut
)

router = APIRouter(
    prefix="/event-definitions",
    tags=["⚙️ Event Definitions"],
    responses={404: {"description": "EventDefinition not found"}},
)


# Dependency: inyectar ServiceFactory con acceso a request y DB
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# ----------------------------------------------------------------
# CREATE
# ----------------------------------------------------------------
@router.post(
    "/",
    summary="Crear nuevo tipo de evento",
    response_model=EventDefinitionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event_definition(
    data: EventDefinitionCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_event_definition_service().create(data)


# ----------------------------------------------------------------
# LIST
# ----------------------------------------------------------------
@router.get(
    "/",
    summary="Listar definiciones de eventos",
    response_model=List[EventDefinitionOut],
)
def list_event_definitions(
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_event_definition_service().get_all()


# ----------------------------------------------------------------
# GET ONE
# ----------------------------------------------------------------
@router.get(
    "/{event_def_id}",
    summary="Obtener definición de evento por ID",
    response_model=EventDefinitionOut,
)
def get_event_definition(
    event_def_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_event_definition_service().get_by_id(event_def_id)


# ----------------------------------------------------------------
# UPDATE
# ----------------------------------------------------------------
@router.put(
    "/{event_def_id}",
    summary="Actualizar definición de evento",
    response_model=EventDefinitionOut,
)
def update_event_definition(
    event_def_id: str,
    updates: EventDefinitionUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_event_definition_service().update(event_def_id, updates)


# ----------------------------------------------------------------
# DELETE
# ----------------------------------------------------------------
@router.delete(
    "/{event_def_id}",
    summary="Eliminar definición de evento",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_event_definition(
    event_def_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    factory.get_event_definition_service().delete(event_def_id)
