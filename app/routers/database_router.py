# app/routers/database_router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionOut,
)

router = APIRouter(
    prefix="/databases",
    tags=["🗄️ Databases"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Base de datos no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)

# 🧩 Inyección del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/",
    response_model=DatabaseConnectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva conexión",
    response_description="Conexión creada correctamente"
)
def create_connection(
    data: DatabaseConnectionCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔌 Crear una nueva conexión a una base de datos externa para su uso en sesiones de IA.
    """
    db_service = factory.get_database_service()
    return db_service.create_connection(data)


@router.get(
    "/",
    response_model=List[DatabaseConnectionOut],
    summary="Listar conexiones",
    response_description="Lista de conexiones activas del usuario"
)
def list_connections(factory: ServiceFactory = Depends(get_factory)):
    """
    📋 Listar todas las conexiones de bases de datos del usuario autenticado.
    """
    db_service = factory.get_database_service()
    return db_service.get_user_databases()


@router.delete(
    "/{db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar conexión",
    response_description="Conexión eliminada correctamente"
)
def delete_connection(
    db_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🧹 Eliminar una conexión de base de datos por su ID.
    """
    db_service = factory.get_database_service()
    success = db_service.delete_connection(db_id)
    if not success:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")


@router.post(
    "/validate",
    summary="Validar conexión",
    response_description="Validez de la conexión comprobada"
)
def validate_connection(
    data: DatabaseConnectionCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🧪 Valida si los datos de conexión proporcionados son correctos.
    """
    db_service = factory.get_database_service()
    success = db_service.validate_connection(data)
    if not success:
        raise HTTPException(status_code=400, detail="Conexión inválida")
    return {"message": "Conexión válida ✅"}
