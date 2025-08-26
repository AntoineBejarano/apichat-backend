from fastapi import APIRouter, UploadFile, Depends, HTTPException, Form
from app.services.background.resource_upload_trigger import ResourceUploadTrigger
from app.core.service_factory import ServiceFactory
from app.core.dependencies import get_current_user_id, get_service_factory
import asyncio
import logging
import uuid
from typing import List

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload/database")
async def upload_database(
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Upload de base de datos con trigger automático de preparación"""
    try:
        logger.info(f"Upload de base de datos iniciado por usuario {user_id}")
        
        # Validar archivo
        if not file.filename or not file.filename.endswith('.sql'):
            raise HTTPException(
                status_code=400, 
                detail="Archivo debe ser un .sql válido"
            )
        
        # Generar UUID único para la base de datos
        db_uuid = str(uuid.uuid4())
        
        # TODO: Aquí iría la lógica real de guardado del archivo
        # Por ahora simulamos el guardado
        logger.info(f"Archivo {file.filename} guardado con UUID {db_uuid}")
        
        # Trigger automático de preparación
        upload_trigger = factory.background.get_upload_trigger_service()
        asyncio.create_task(
            upload_trigger.on_database_uploaded(db_uuid, user_id)
        )
        
        logger.info(f"Trigger automático iniciado para DB {db_uuid}")
        
        return {
            "message": "Base de datos subida y preparación iniciada automáticamente",
            "db_uuid": db_uuid,
            "filename": file.filename,
            "status": "uploading_and_preparing",
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload de base de datos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/application")
async def upload_application(
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Upload de aplicación con trigger automático de preparación"""
    try:
        logger.info(f"Upload de aplicación iniciado por usuario {user_id}")
        
        # Validar archivo
        if not file.filename or not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400, 
                detail="Archivo debe ser un .json válido"
            )
        
        # Generar UUID único para la aplicación
        app_id = str(uuid.uuid4())
        
        # TODO: Aquí iría la lógica real de guardado del archivo
        # Por ahora simulamos el guardado
        logger.info(f"Archivo {file.filename} guardado con UUID {app_id}")
        
        # Trigger automático de preparación
        upload_trigger = factory.background.get_upload_trigger_service()
        asyncio.create_task(
            upload_trigger.on_application_uploaded(app_id, user_id)
        )
        
        logger.info(f"Trigger automático iniciado para app {app_id}")
        
        return {
            "message": "Aplicación subida y preparación iniciada automáticamente",
            "app_id": app_id,
            "filename": file.filename,
            "status": "uploading_and_preparing",
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload de aplicación: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/strategies")
async def upload_strategies(
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Upload de estrategias con trigger automático de preparación"""
    try:
        logger.info(f"Upload de estrategias iniciado por usuario {user_id}")
        
        # Validar archivo
        if not file.filename or not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=400, 
                detail="Archivo debe ser un .json válido"
            )
        
        # Generar UUID único para las estrategias
        strategy_id = str(uuid.uuid4())
        
        # TODO: Aquí iría la lógica real de guardado del archivo
        # Por ahora simulamos el guardado
        logger.info(f"Archivo {file.filename} guardado con UUID {strategy_id}")
        
        # Trigger automático de preparación
        upload_trigger = factory.background.get_upload_trigger_service()
        asyncio.create_task(
            upload_trigger.on_strategies_uploaded(strategy_id, user_id)
        )
        
        logger.info(f"Trigger automático iniciado para estrategias {strategy_id}")
        
        return {
            "message": "Estrategias subidas y preparación iniciada automáticamente",
            "strategy_id": strategy_id,
            "filename": file.filename,
            "status": "uploading_and_preparing",
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en upload de estrategias: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/upload/status/{resource_type}/{resource_id}")
async def get_upload_status(
    resource_type: str,
    resource_id: str,
    user_id: str = Depends(get_current_user_id),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Obtiene el estado de preparación de un recurso subido"""
    try:
        logger.info(f"Consultando estado de {resource_type} {resource_id} para usuario {user_id}")
        
        # Obtener estado desde el registro de readiness
        readiness_registry = factory.readiness_registry
        status = await readiness_registry.get_resource_status(resource_type, resource_id)
        
        return {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de {resource_type} {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/force-prepare/{resource_type}/{resource_id}")
async def force_prepare_resource(
    resource_type: str,
    resource_id: str,
    user_id: str = Depends(get_current_user_id),
    factory: ServiceFactory = Depends(get_service_factory)
):
    """Fuerza la preparación manual de un recurso"""
    try:
        logger.info(f"Forzando preparación de {resource_type} {resource_id} para usuario {user_id}")
        
        # Obtener el servicio de preparación
        preparation_service = factory.background.get_resource_preparation_service()
        
        # Lanzar preparación forzada
        if resource_type == "database":
            asyncio.create_task(
                preparation_service.prepare_database(resource_id, user_id)
            )
        elif resource_type == "application":
            asyncio.create_task(
                preparation_service.prepare_application(resource_id, user_id)
            )
        elif resource_type == "strategies":
            asyncio.create_task(
                preparation_service.prepare_strategies(resource_id, user_id)
            )
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de recurso no válido: {resource_type}"
            )
        
        return {
            "message": f"Preparación forzada iniciada para {resource_type} {resource_id}",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": "force_preparation_started",
            "user_id": user_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error forzando preparación de {resource_type} {resource_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
