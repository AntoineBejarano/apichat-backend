# app/routers/user_router.py

import os
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
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

# 🧩 Inyector del ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

# 🔒 Setear cookie de sesión (usado en el registro)
def _set_session_cookie(response: Response, token: str):
    environment = os.getenv("ENVIRONMENT", "development")
    is_local = environment == "development"

    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=not is_local,
        samesite="none",
        domain="apichat.es" if not is_local else None
    )

# 📥 Registro de usuario
@router.post(
    "/",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="📝 Registro manual de usuario",
    description="Permite registrar un nuevo usuario manualmente proporcionando nombre, email y contraseña."
)
def register_user(
    user_data: UserCreate,
    request: Request,
    response: Response,
    factory: ServiceFactory = Depends(get_factory)
):
    existing = factory.get_user_service().get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(status_code=400, detail="❌ El email ya está registrado")

    user = factory.get_user_service().create_user(user_data)
    session = factory.get_session_service().create_session(user.id, request)
    _set_session_cookie(response, session.session_token)
    return user

# 👤 Obtener perfil actual
@router.get(
    "/me",
    response_model=UserDetail,
    summary="🙋 Perfil actual",
    description="Obtiene la información del usuario autenticado actual."
)
def get_current_profile(factory: ServiceFactory = Depends(get_factory)):
    return factory.user

# 🔍 Obtener usuario por ID
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
        raise HTTPException(status_code=404, detail="❌ Usuario no encontrado")
    return user

# 🔎 Obtener usuario por email
@router.get(
    "/by-email/{email}",
    response_model=UserDetail,
    summary="🔎 Obtener usuario por email",
    description="Devuelve los detalles de un usuario específico a partir de su email."
)
def get_user_by_email_route(
    email: str,
    factory: ServiceFactory = Depends(get_factory)
):
    user = factory.get_user_service().get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="❌ Usuario no encontrado")
    return user

# 📋 Listar todos los usuarios (útil para admin o pruebas)
@router.get(
    "/",
    response_model=list[UserOut],
    summary="📋 Listar todos los usuarios",
    description="Devuelve una lista de todos los usuarios del sistema (solo uso interno/admin)."
)
def list_all_users(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_user_service().get_all_users()
