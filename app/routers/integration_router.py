# app/routers/integration_router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.integration_schema import IntegrationCreate, IntegrationOut

router = APIRouter(
    prefix="/integrations",
    tags=["🔗 Integrations"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Integración no encontrada"},
        500: {"description": "Error interno del servidor"},
    },
)

# 🧩 Inyector del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/",
    response_model=IntegrationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Conectar nueva integración",
    response_description="Integración conectada correctamente"
)
def connect_integration(
    data: IntegrationCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔌 Conecta una nueva integración (Notion, n8n, Zapier...).
    """
    return factory.get_integration_service().create(factory.user.id, data)


@router.get(
    "/",
    response_model=List[IntegrationOut],
    summary="Listar integraciones",
    response_description="Lista de integraciones activas del usuario"
)
def list_integrations(factory: ServiceFactory = Depends(get_factory)):
    """
    📦 Lista todas las integraciones activas del usuario autenticado.
    """
    return factory.get_integration_service().get_by_user(factory.user.id)


@router.get(
    "/by-service/{service_name}",
    response_model=IntegrationOut,
    summary="Obtener integración por servicio",
    response_description="Integración encontrada"
)
def get_integration_by_service(
    service_name: str,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    🔍 Obtiene una integración específica del usuario por nombre de servicio.
    """
    integration = factory.get_integration_service().get_by_service(factory.user.id, service_name)
    if not integration:
        raise HTTPException(status_code=404, detail="Integración no encontrada")
    return integration
