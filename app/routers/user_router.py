from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.servicefactory import ServiceFactory
from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserOut, UserDetail

router = APIRouter(
    prefix="/users",
    tags=["👤 Users"],
    responses={
        404: {"description": "Usuario no encontrado"},
        400: {"description": "Solicitud inválida"},
    }
)

# Dependency centralizada
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="📝 Registro manual de usuario",
    description="Permite registrar un nuevo usuario manualmente proporcionando nombre, email y contraseña."
)
def register_user(
    user_data: UserCreate,
    factory: ServiceFactory = Depends(get_factory)
):
    existing = factory.db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    return factory.get_user_service().create_user(user_data)


@router.get(
    "/{user_id}",
    response_model=UserDetail,
    summary="🔍 Obtener usuario por ID",
    description="Devuelve los detalles completos de un usuario específico a partir de su ID."
)
def get_user_by_id_route(
    user_id: int,
    factory: ServiceFactory = Depends(get_factory)
):
    user = factory.get_user_service().get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get(
    "/me",
    response_model=UserDetail,
    summary="🙋 Perfil actual",
    description="Obtiene la información del usuario autenticado actual."
)
def get_current_profile(factory: ServiceFactory = Depends(get_factory)):
    return factory.user
