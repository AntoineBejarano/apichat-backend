# app/routers/user_router.py

import os
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.models.user_model import User
from app.schemas.user_schema import (
    UserCreate, 
    UserOut, 
    UserDetail, 
    UserPreferences, 
    UserPreferencesUpdate, 
    UserPreferencesResponse
)

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

# 🎯 FASE 12: Endpoints para manejo de preferencias de usuario

@router.get(
    "/{user_id}/preferences", 
    response_model=UserPreferencesResponse,
    summary="⚙️ Obtener preferencias del usuario",
    description="Obtiene las preferencias actuales del usuario para personalizar la experiencia."
)
def get_user_preferences(
    user_id: int,
    factory: ServiceFactory = Depends(get_factory)
) -> UserPreferencesResponse:
    """Obtiene las preferencias actuales del usuario."""
    user_service = factory.get_user_service()
    preferences = user_service.get_user_preferences(user_id)
    
    if not preferences:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user = user_service.get_user_by_id(user_id)
    return UserPreferencesResponse(
        user_id=UUID(str(user_id)),
        preferences=preferences,
        updated_at=user.updated_at
    )


@router.put(
    "/{user_id}/preferences", 
    response_model=UserPreferencesResponse,
    summary="⚙️ Actualizar preferencias del usuario",
    description="Actualiza las preferencias del usuario para personalizar la experiencia."
)
def update_user_preferences(
    user_id: int,
    preferences_update: UserPreferencesUpdate,
    factory: ServiceFactory = Depends(get_factory)
) -> UserPreferencesResponse:
    """Actualiza las preferencias del usuario."""
    user_service = factory.get_user_service()
    
    try:
        updated_preferences = user_service.update_user_preferences(
            user_id, 
            preferences_update
        )
        
        if not updated_preferences:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        user = user_service.get_user_by_id(user_id)
        return UserPreferencesResponse(
            user_id=UUID(str(user_id)),
            preferences=updated_preferences,
            updated_at=user.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error actualizando preferencias: {str(e)}"
        )


@router.get(
    "/{user_id}/preferences/summary",
    summary="📊 Resumen de preferencias del usuario",
    description="Obtiene un resumen detallado de las preferencias del usuario con perfil de riesgo."
)
def get_user_preferences_summary(
    user_id: int,
    factory: ServiceFactory = Depends(get_factory)
) -> Dict[str, Any]:
    """Obtiene un resumen detallado de las preferencias del usuario."""
    user_service = factory.get_user_service()
    summary = user_service.get_user_preferences_summary(user_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return summary


@router.post(
    "/{user_id}/preferences/check-confirmation",
    summary="✅ Verificar si se requiere confirmación",
    description="Verifica si se requiere confirmación para una acción basada en el nivel de riesgo."
)
def check_if_confirmation_required(
    user_id: int,
    risk_level: str,
    factory: ServiceFactory = Depends(get_factory)
) -> Dict[str, Any]:
    """Verifica si se requiere confirmación para una acción basada en el nivel de riesgo."""
    if risk_level not in ["low", "medium", "high"]:
        raise HTTPException(
            status_code=400, 
            detail="Nivel de riesgo debe ser: low, medium, o high"
        )
    
    user_service = factory.get_user_service()
    requires_confirmation = user_service.should_confirm_action(user_id, risk_level)
    
    return {
        "user_id": user_id,
        "action_risk_level": risk_level,
        "requires_confirmation": requires_confirmation,
        "reason": "Basado en las preferencias de confirmación del usuario"
    }


@router.get(
    "/preferences/by-category",
    summary="👥 Usuarios por categoría de preferencia",
    description="Obtiene usuarios que tienen una preferencia específica."
)
def get_users_by_preference_category(
    preference_field: str,
    preference_value: str,
    factory: ServiceFactory = Depends(get_factory)
) -> Dict[str, Any]:
    """Obtiene usuarios que tienen una preferencia específica."""
    user_service = factory.get_user_service()
    
    try:
        users = user_service.get_users_by_preference(preference_field, preference_value)
        
        return {
            "preference_field": preference_field,
            "preference_value": preference_value,
            "user_count": len(users),
            "users": [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name
                }
                for user in users
            ]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error obteniendo usuarios por preferencia: {str(e)}"
        )
