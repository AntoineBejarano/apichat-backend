# app/routers/functions_router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.function_schema import FunctionCreate, FunctionUpdate, FunctionOut

router = APIRouter(
    prefix="/apps/{app_id}/functions",
    tags=["⚙️ Functions"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Función o App no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/",
    response_model=FunctionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear función",
    response_description="Función creada correctamente"
)
def create_function(
    app_id: UUID,
    function_data: FunctionCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    # Inyectamos el app_id dentro de function_data antes de llamar al servicio
    function_data.app_id = app_id
    return factory.get_function_service().create(function_data)


@router.get(
    "/",
    response_model=List[FunctionOut],
    summary="Listar funciones de la app",
    response_description="Funciones definidas en la app"
)
def list_functions(
    app_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_function_service().get_by_app(app_id)


@router.get(
    "/{function_id}",
    response_model=FunctionOut,
    summary="Obtener función por ID",
    response_description="Detalles de la función"
)
def get_function(
    app_id: UUID,
    function_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_function_service().get_by_id(app_id, function_id)


@router.put(
    "/{function_id}",
    response_model=FunctionOut,
    summary="Actualizar función",
    response_description="Función actualizada correctamente"
)
def update_function(
    app_id: UUID,
    function_id: UUID,
    updates: FunctionUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    return factory.get_function_service().update(app_id, function_id, updates)


@router.delete(
    "/{function_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar función",
    response_description="Función eliminada correctamente"
)
def delete_function(
    app_id: UUID,
    function_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    success = factory.get_function_service().delete(app_id, function_id)
    if not success:
        raise HTTPException(status_code=404, detail="Función no encontrada")
