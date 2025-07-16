from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.mcp_integration_schema import (
    MCPIntegrationCreate,
    MCPIntegrationInDB
)

router = APIRouter(
    prefix="/mcp_integrations",
    tags=["🧩 MCP Integrations"],
    responses={404: {"description": "Not found"}}
)


# 🧩 ServiceFactory injection
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/",
    response_model=MCPIntegrationInDB,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una nueva integración MCP",
    response_description="La integración creada"
)
def create_mcp_integration(
    data: MCPIntegrationCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Crea una nueva integración de tipo MCP (Multi-Channel Processor).

    Puede ser de tipo:
    - `http`: Usa un servidor HTTP remoto
    - `stdio`: Usa un binario local
    - `websocket`: Conecta por WebSocket

    Los endpoints se configuran de forma dinámica desde `metadata`.

    """
    service = factory.get_mcp_integration_service()
    return service.create_mcp_integration(data)


@router.get(
    "/",
    response_model=List[MCPIntegrationInDB],
    summary="Listar todas las integraciones MCP",
    response_description="Listado completo de integraciones"
)
def list_mcp_integrations(factory: ServiceFactory = Depends(get_factory)):
    """
    Devuelve todas las integraciones MCP registradas por el usuario.
    """
    service = factory.get_mcp_integration_service()
    return service.get_all_mcp_integrations()


@router.get(
    "/{integration_id}",
    response_model=MCPIntegrationInDB,
    summary="Obtener integración por ID",
    response_description="Detalles de la integración"
)
def get_mcp_integration_by_id(
    integration_id: int,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Recupera una integración MCP específica por su ID.
    """
    service = factory.get_mcp_integration_service()
    integration = service.get_mcp_integration_by_id(integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.delete(
    "/{integration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar integración por ID",
)
def delete_mcp_integration(
    integration_id: int,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Elimina una integración MCP por su ID.
    """
    service = factory.get_mcp_integration_service()
    success = service.delete_mcp_integration(integration_id)
    if not success:
        raise HTTPException(status_code=404, detail="Integration not found")


@router.put(
    "/{integration_id}",
    response_model=MCPIntegrationInDB,
    summary="Actualizar una integración MCP",
    response_description="Integración actualizada"
)
def update_mcp_integration(
    integration_id: int,
    data: MCPIntegrationCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Actualiza una integración MCP existente.

    Puedes modificar campos como:
    - Nombre (`name`)
    - Tipo (`mcp_type`)
    - Metadata (`url`, `command`, `args`, `endpoints`, etc.)
    """
    service = factory.get_mcp_integration_service()
    updated = service.update_mcp_integration(integration_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Integration not found")
    return updated
