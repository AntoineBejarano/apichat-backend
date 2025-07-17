from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.permission_schema import (
    PermissionCreate,
    PermissionOut,
    PermissionUpdate
)

router = APIRouter(
    prefix="/permissions",
    tags=["🛡️ Permissions"],
    responses={404: {"description": "Permission not found"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    summary="Create a new permission",
    response_model=PermissionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_permission(permission_data: PermissionCreate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_permission_service().create(permission_data)

@router.get(
    "/",
    summary="List all permissions",
    response_model=List[PermissionOut],
)
def list_permissions(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_permission_service().get_all()

@router.get(
    "/{permission_id}",
    summary="Get permission by ID",
    response_model=PermissionOut,
)
def get_permission(permission_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_permission_service().get_by_id(permission_id)

@router.put(
    "/{permission_id}",
    summary="Update permission by ID",
    response_model=PermissionOut,
)
def update_permission(permission_id: int, updates: PermissionUpdate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_permission_service().update(permission_id, updates)

@router.delete(
    "/{permission_id}",
    summary="Delete permission",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_permission(permission_id: int, factory: ServiceFactory = Depends(get_factory)):
    factory.get_permission_service().delete(permission_id)
