from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.trigger_schema import (
    TriggerCreate,
    TriggerOut
)

router = APIRouter(
    prefix="/triggers",
    tags=["🚀 Triggers"],
    responses={404: {"description": "Trigger no encontrado"}},
)


# Dependency: inyectar ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# ----------------------------------------------------------------
# CREATE
# ----------------------------------------------------------------
@router.post(
    "/",
    summary="Crear Trigger sobre un EventTrigger",
    response_model=TriggerOut,
    status_code=status.HTTP_201_CREATED,
)
def create_trigger(
    data: TriggerCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_trigger_service().create(data)


# ----------------------------------------------------------------
# LIST
# ----------------------------------------------------------------
@router.get(
    "/",
    summary="Listar Triggers del usuario",
    response_model=List[TriggerOut],
)
def list_triggers(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_trigger_service().get_all()


# ----------------------------------------------------------------
# GET BY ID
# ----------------------------------------------------------------
@router.get(
    "/{trigger_id}",
    summary="Obtener Trigger por ID",
    response_model=TriggerOut,
)
def get_trigger(
    trigger_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_trigger_service().get_by_id(trigger_id)


# ----------------------------------------------------------------
# DELETE
# ----------------------------------------------------------------
@router.delete(
    "/{trigger_id}",
    summary="Eliminar Trigger",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_trigger(
    trigger_id: str,
    factory: ServiceFactory = Depends(get_factory),
):
    factory.get_trigger_service().delete(trigger_id)
