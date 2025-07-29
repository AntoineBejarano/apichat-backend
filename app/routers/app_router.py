# app/routers/app_router.py

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.app_schema import AppCreate, AppOut, AppUpdate
from uuid import UUID

router = APIRouter(
    prefix="/apps",
    tags=["📦 Apps"],
    responses={404: {"description": "App no encontrada"}},
)

# Inyecta ServiceFactory con DB + Request
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/",
    summary="Crear nueva App",
    response_model=AppOut,
    response_description="App creada correctamente",
    status_code=status.HTTP_201_CREATED,
)
def create_app(
    app_data: AppCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    app_service = factory.get_apps_service()
    return app_service.create(app_data)


@router.get(
    "/",
    summary="Listar mis Apps",
    response_model=List[AppOut],
    response_description="Lista de Apps del usuario",
)
def list_apps(factory: ServiceFactory = Depends(get_factory)):
    app_service = factory.get_apps_service()
    return app_service.get_all()


@router.get(
    "/{app_id}",
    summary="Obtener una App por ID",
    response_model=AppOut,
    response_description="Detalles de la App",
)
def get_app(app_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    app_service = factory.get_apps_service()
    return app_service.get_by_id(app_id)


@router.put(
    "/{app_id}",
    summary="Actualizar una App",
    response_model=AppOut,
    response_description="App actualizada correctamente",
)
def update_app(
    app_id: UUID,
    app_update: AppUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    app_service = factory.get_apps_service()
    return app_service.update(app_id, app_update)


@router.delete(
    "/{app_id}",
    summary="Eliminar una App",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="App eliminada exitosamente",
)
def delete_app(app_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    app_service = factory.get_apps_service()
    app_service.delete(app_id)
