# app/routers/proxy_router.py
"""
Router: Proxies 🔌
Gestión de proxies (base URL, cabeceras, auth) reutilizables por varias Functions.

Cada endpoint incluye títulos/descripciones cuidadas para una
experiencia Swagger / ReDoc clara y agradable.
"""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
    Request,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.proxy_schema import (
    ProxyCreate,
    ProxyUpdate,
    ProxyOut,
)

# ------------------------------------------------------------------ #
# Configuración del router
# ------------------------------------------------------------------ #
router = APIRouter(
    prefix="/proxies",
    tags=["🔌 Proxies"],
    responses={
        404: {"description": "Proxy no encontrado"},
        401: {"description": "No autorizado"},
        500: {"description": "Error interno del servidor"},
    },
)


def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    """Inyector central con DB y Request."""
    return ServiceFactory(db, request)


# ------------------------------------------------------------------ #
# Endpoints CRUD                                                     #
# ------------------------------------------------------------------ #
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ProxyOut,
    summary="➕ Crear proxy",
    response_description="Proxy creado correctamente",
)
def create_proxy(
    data: ProxyCreate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Crea un **proxy** con URL base, cabeceras y credenciales opcionales.

    Un proxy permite reutilizar su configuración en varias funciones HTTP,
    evitando repetir *base_url* y *headers*.
    """
    return factory.get_proxy_service().create(data)


@router.get(
    "/",
    response_model=List[ProxyOut],
    summary="📋 Listar proxies",
    response_description="Listado de proxies del usuario",
)
def list_proxies(factory: ServiceFactory = Depends(get_factory)):
    """
    Devuelve **todos** los proxies creados por el usuario autenticado.
    """
    return factory.get_proxy_service().list_all()


@router.get(
    "/{proxy_id}",
    response_model=ProxyOut,
    summary="🔍 Obtener proxy",
    response_description="Detalles del proxy solicitado",
)
def get_proxy(
    proxy_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Recupera un proxy específico por **ID**.

    - **proxy_id**: identificador del proxy (entero).
    """
    proxy = factory.get_proxy_service().get_by_id(proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return proxy


@router.put(
    "/{proxy_id}",
    response_model=ProxyOut,
    summary="✏️ Actualizar proxy",
    response_description="Proxy actualizado correctamente",
)
def update_proxy(
    proxy_id: int,
    updates: ProxyUpdate,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Actualiza campos de un proxy existente.

    Solo se modifican los atributos incluidos en el cuerpo **JSON**.
    """
    try:
        return factory.get_proxy_service().update(proxy_id, updates)
    except ValueError:
        raise HTTPException(status_code=404, detail="Proxy not found")


@router.delete(
    "/{proxy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="🗑️ Eliminar proxy",
    response_description="Proxy eliminado correctamente",
)
def delete_proxy(
    proxy_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Elimina definitivamente un proxy por **ID**.
    """
    try:
        factory.get_proxy_service().delete(proxy_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Proxy not found")
