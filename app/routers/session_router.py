from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.session_schema import SessionOut

router = APIRouter(
    prefix="/sessions",
    tags=["🧾 Sessions"],
    responses={
        401: {"description": "No autorizado"},
        403: {"description": "Prohibido"},
        404: {"description": "Sesión no encontrada"},
    },
)

# 🧩 Factory injection
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.get(
    "/me",
    summary="Listar todas mis sesiones activas",
    response_model=List[SessionOut],
)
def list_my_sessions(factory: ServiceFactory = Depends(get_factory)):
    user = factory.user
    session_service = factory.get_session_service()
    current_token = factory.request.cookies.get("session_token") or factory.request.headers.get("Authorization")

    sessions = session_service.get_user_sessions(user.id)
    for session in sessions:
        session.is_current = session.session_token == current_token

    return sessions


@router.delete(
    "/me/{token}",
    summary="Revocar una sesión específica del usuario",
    status_code=200,
)
def revoke_specific_session(token: str, factory: ServiceFactory = Depends(get_factory)):
    user = factory.user
    session_service = factory.get_session_service()
    session_service.revoke_session_by_token(token, user.id)
    return {"message": "🗑️ Sesión revocada correctamente"}


@router.delete(
    "/me",
    summary="Cerrar todas mis sesiones excepto la actual",
    status_code=200,
)
def revoke_all_sessions_except_current(factory: ServiceFactory = Depends(get_factory)):
    user = factory.user
    session_service = factory.get_session_service()
    current_token = factory.request.cookies.get("session_token") or factory.request.headers.get("Authorization")

    if not current_token:
        raise HTTPException(status_code=401, detail="No session token provided")

    count = session_service.revoke_all_except(user.id, current_token)
    return {"message": f"🔒 {count} sesiones revocadas. Solo permanece la actual."}


@router.get(
    "/validate",
    summary="Validar si la sesión actual es válida",
    response_model=SessionOut,
)
def validate_session(factory: ServiceFactory = Depends(get_factory)):
    request = factory.request
    token = request.cookies.get("session_token") or request.headers.get("Authorization")

    if not token:
        raise HTTPException(status_code=401, detail="No session token provided")

    session_service = factory.get_session_service()
    session = session_service.validate_session(token)
    session.is_current = True
    return session
