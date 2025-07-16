from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.servicefactory import ServiceFactory
from app.schemas.function_schema import FunctionCreate, FunctionUpdate, FunctionOut

router = APIRouter(
    prefix="/functions",
    tags=["⚙️ Functions"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Función no encontrada"},
        500: {"description": "Error interno del servidor"}
    }
)

# Dependency para el ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post("/", response_model=FunctionOut, status_code=status.HTTP_201_CREATED)
def create_function(
    function_data: FunctionCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🆕 Crea una nueva función para tu aplicación.
    Esta función puede ser usada en llamadas automáticas por la IA mediante Function Calling.
    """
    return factory.get_function_service().create(factory.user.id, function_data)

@router.get("/", response_model=List[FunctionOut])
def list_user_functions(factory: ServiceFactory = Depends(get_factory)):
    """
    📄 Lista todas las funciones definidas por el usuario.
    """
    return factory.get_function_service().get_by_user(factory.user.id)

@router.get("/{function_id}", response_model=FunctionOut)
def get_function(
    function_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔍 Recupera una función específica por su ID.
    """
    return factory.get_function_service().get_by_id(factory.user.id, function_id)

@router.put("/{function_id}", response_model=FunctionOut)
def update_function(
    function_id: int,
    updates: FunctionUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    ✏️ Actualiza una función existente con nuevos parámetros.
    """
    return factory.get_function_service().update(factory.user.id, function_id, updates)

@router.delete("/{function_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_function(
    function_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🗑️ Elimina una función por su ID.
    """
    if not factory.get_function_service().delete(factory.user.id, function_id):
        raise HTTPException(status_code=404, detail="Función no encontrada")
