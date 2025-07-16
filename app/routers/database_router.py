from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.servicefactory import ServiceFactory
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionOut
)

router = APIRouter(
    prefix="/databases",
    tags=["🗄️ Databases"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Base de datos no encontrada"},
        500: {"description": "Error interno del servidor"}
    }
)

# Inyector para el ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post("/", response_model=DatabaseConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    data: DatabaseConnectionCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    🔌 Crear una nueva conexión a una base de datos externa.

    Esta conexión se podrá usar luego en sesiones de chat para hacer consultas con IA.
    """
    return factory.get_database_service().create_connection(factory.user.id, data)


@router.get("/", response_model=List[DatabaseConnectionOut])
def list_connections(factory: ServiceFactory = Depends(get_factory)):
    """
    📋 Listar todas las conexiones de bases de datos del usuario autenticado.
    """
    return factory.get_database_service().get_user_databases(factory.user.id)


@router.delete("/{db_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    db_id: int,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    🧹 Eliminar una conexión de base de datos por su ID.
    """
    success = factory.get_database_service().delete_database(factory.user.id, db_id)
    if not success:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")
    return
