from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID

from app.schemas.api_triggering_config_schema import (
    APITriggeringConfigCreate,
    APITriggeringConfigUpdate,
    APITriggeringConfigOut
)
from app.dependencies import get_service_factory
from app.core.service_factory import ServiceFactory

router = APIRouter(
    prefix="/api-triggering-configs",
    tags=["🔧 API Triggering Config"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Configuración no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)


@router.post(
    "/",
    response_model=APITriggeringConfigOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear configuración de triggering",
    description="Crear configuración personalizada de triggering para una app específica"
)
async def create_triggering_config(
    config_data: APITriggeringConfigCreate,
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Crear configuración de triggering para un usuario y app"""
    try:
        config_service = factory.get_api_triggering_config_service()
        return config_service.create_config(config_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando configuración: {str(e)}")


@router.get(
    "/",
    response_model=List[APITriggeringConfigOut],
    summary="Listar configuraciones del usuario",
    description="Obtener todas las configuraciones de triggering del usuario actual"
)
async def list_user_configs(
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Listar todas las configuraciones del usuario"""
    try:
        config_service = factory.get_api_triggering_config_service()
        return config_service.get_user_configs(factory.user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo configuraciones: {str(e)}")


@router.get(
    "/app/{app_id}",
    response_model=APITriggeringConfigOut,
    summary="Obtener configuración por app",
    description="Obtener configuración de triggering para una app específica"
)
async def get_config_by_app(
    app_id: UUID,
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtener configuración para una app específica"""
    try:
        config_service = factory.get_api_triggering_config_service()
        config = config_service.get_config_by_user_and_app(factory.user.id, app_id)
        
        if not config:
            # Retornar configuración por defecto
            config = config_service.get_default_config(app_id)
        
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo configuración: {str(e)}")


@router.put(
    "/{config_id}",
    response_model=APITriggeringConfigOut,
    summary="Actualizar configuración",
    description="Actualizar configuración de triggering existente"
)
async def update_triggering_config(
    config_id: UUID,
    config_data: APITriggeringConfigUpdate,
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Actualizar configuración existente"""
    try:
        config_service = factory.get_api_triggering_config_service()
        return config_service.update_config(config_id, config_data)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando configuración: {str(e)}")


@router.delete(
    "/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar configuración",
    description="Eliminar configuración de triggering"
)
async def delete_triggering_config(
    config_id: UUID,
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Eliminar configuración"""
    try:
        config_service = factory.get_api_triggering_config_service()
        config_service.delete_config(config_id)
        return {"message": "Configuración eliminada exitosamente"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando configuración: {str(e)}")
