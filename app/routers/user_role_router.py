from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.user_role_schema import UserRoleAssign, RoleSummary
from app.schemas.role_schema import RoleOut  # reutiliza si ya tienes esto

router = APIRouter(
    prefix="/user-roles",
    tags=["🔐 User Roles"],
    responses={404: {"description": "Not found"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/{user_id}/assign",
    summary="Asignar un rol a un usuario",
    status_code=status.HTTP_200_OK
)
def assign_role(user_id: UUID, data: UserRoleAssign, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_user_role_service().assign_role(user_id, data.role_id)

@router.post(
    "/{user_id}/remove",
    summary="Eliminar un rol de un usuario",
    status_code=status.HTTP_200_OK
)
def remove_role(user_id: UUID, data: UserRoleAssign, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_user_role_service().remove_role(user_id, data.role_id)

@router.get(
    "/{user_id}/",
    summary="Listar roles de un usuario",
    response_model=List[RoleSummary],
    status_code=status.HTTP_200_OK
)
def list_roles(user_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_user_role_service().list_roles(user_id)
