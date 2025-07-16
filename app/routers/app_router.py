# app/routers/app_router.py

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.app_schema import AppCreate, AppOut, AppUpdate

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
    status_code=status.HTTP_201_CREATED
)
def create_app(
    app_data: AppCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    function_service = factory.get_function_service()
    return function_service.create_app(factory.db, app_data, factory.user.id)


@router.get(
    "/",
    summary="Listar mis Apps",
    response_model=List[AppOut],
    response_description="Lista de Apps del usuario"
)
def list_apps(factory: ServiceFactory = Depends(get_factory)):
    function_service = factory.get_function_service()
    return function_service.get_user_apps(factory.db, factory.user.id)


@router.get(
    "/{app_id}",
    summary="Obtener una App por ID",
    response_model=AppOut,
    response_description="Detalles de la App"
)
def get_app(app_id: int, factory: ServiceFactory = Depends(get_factory)):
    function_service = factory.get_function_service()
    return function_service.get_app_by_id(factory.db, app_id, factory.user.id)


@router.put(
    "/{app_id}",
    summary="Actualizar una App",
    response_model=AppOut,
    response_description="App actualizada correctamente"
)
def update_app(
    app_id: int,
    app_update: AppUpdate,
    factory: ServiceFactory = Depends(get_factory)
):
    function_service = factory.get_function_service()
    return function_service.update_app(factory.db, app_id, factory.user.id, app_update)


@router.delete(
    "/{app_id}",
    summary="Eliminar una App",
    status_code=status.HTTP_204_NO_CONTENT,
    response_description="App eliminada exitosamente"
)
def delete_app(app_id: int, factory: ServiceFactory = Depends(get_factory)):
    function_service = factory.get_function_service()
    function_service.delete_app(factory.db, app_id, factory.user.id)
