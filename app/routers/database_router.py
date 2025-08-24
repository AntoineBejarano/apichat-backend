from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionOut,
)
from app.services.background.schema_generation_service import generate_schema_background
from app.services.background.schema_refresh_service import refresh_schema_background

router = APIRouter(
    prefix="/databases",
    tags=["🗄️ Databases"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Base de datos no encontrada"},
        500: {"description": "Error UUIDerno del servidor"},
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
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔌 Crear una nueva conexión a una base de datos externa para su uso en sesiones de IA.
    
    El schema se generará automáticamente en background.
    """
    db_service = factory.get_database_service()
    
    # Crear la conexión
    connection = db_service.create_connection(data)
    
    # 🔧 NUEVO: Lanzar generación de schema en background
    background_tasks.add_task(
        generate_schema_background, 
        connection.id,
        connection.user_id,
        factory
    )
    
    # 🔧 NUEVO: Retornar respuesta con mensaje informativo
    return {
        "connection": connection,
        "message": "We are working on adding your database. This may take a few minutes.",
        "schema_status": "pending",
        "estimated_time": "2-5 minutes"
    }


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
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🧹 Eliminar una conexión de base de datos por su ID.
    """
    db_service = factory.get_database_service()
    success = db_service.delete_connection(db_id)
    if not success:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")


@router.get(
    "/test/{db_id}",
    summary="Testear conexión por ID",
    response_description="Conexión exitosa"
)
def test_connection(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🧪 Testea si una conexión ya guardada (por ID) es válida y operativa.
    """
    db_service = factory.get_database_service()
    success = db_service.test_connection_by_id(db_id)
    if not success:
        raise HTTPException(status_code=400, detail="Conexión inválida o inaccesible")
    return {"message": "Conexión exitosa ✅"}


@router.put(
    "/{db_id}/schema/refresh",
    summary="🔄 Refrescar schema de base de datos",
    response_description="Schema refresh iniciado en background"
)
def refresh_database_schema(
    db_id: UUID,
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔄 Refrescar manualmente el schema de una base de datos.
    
    El schema se regenerará completamente en background, incluyendo:
    - Análisis de la estructura actual de la DB
    - Actualización del cache (Redis + BD)
    - Invalidación de cache anterior
    - Fallback a schema anterior si falla
    
    ⚠️ **Nota**: Este proceso puede tomar varios minutos dependiendo del tamaño de la DB.
    """
    try:
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_connection_by_id(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Lanzar refresh de schema en background
        background_tasks.add_task(
            refresh_schema_background,
            db_id,
            factory.user.id,
            factory,
            False  # force=False por defecto
        )
        
        # Retornar respuesta informativa
        return {
            "success": True,
            "message": "We are refreshing your database schema. This may take a few minutes.",
            "db_id": str(db_id),
            "status": "updating",
            "estimated_time": "2-5 minutes",
            "note": "Your database will remain available during the refresh process"
        }
        
    except HTTPException:
        # Re-lanzar HTTPExceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )
