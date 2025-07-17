from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.role_schema import RoleCreate, RoleOut, RoleUpdate

router = APIRouter(
    prefix="/roles",
    tags=["🔐 Roles"],
    responses={404: {"description": "Role not found"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    summary="Create a new role",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
)
def create_role(role_data: RoleCreate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().create(role_data)

@router.get(
    "/",
    summary="List all roles",
    response_model=List[RoleOut],
)
def list_roles(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().get_all()

@router.get(
    "/{role_id}",
    summary="Get role by ID",
    response_model=RoleOut,
)
def get_role(role_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().get_by_id(role_id)

@router.put(
    "/{role_id}",
    summary="Update role by ID",
    response_model=RoleOut,
)
def update_role(role_id: int, updates: RoleUpdate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().update(role_id, updates)

@router.delete(
    "/{role_id}",
    summary="Delete role",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_role(role_id: int, factory: ServiceFactory = Depends(get_factory)):
    factory.get_role_service().delete(role_id)

@router.post(
    "/{role_id}/permissions/{permission_id}",
    summary="Assign a permission to role",
    response_model=RoleOut,
)
def assign_permission(role_id: int, permission_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().assign_permission(role_id, permission_id)

@router.delete(
    "/{role_id}/permissions/{permission_id}",
    summary="Remove a permission from role",
    response_model=RoleOut,
)
def remove_permission(role_id: int, permission_id: int, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_role_service().remove_permission(role_id, permission_id)
