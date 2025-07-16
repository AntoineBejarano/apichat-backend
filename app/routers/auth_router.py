# app/routers/auth_router.py

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.login_schema import LoginRequest

router = APIRouter(
    prefix="/auth",
    tags=["🔐 Auth"],
    responses={
        401: {"description": "No autorizado"},
        400: {"description": "Error de validación"},
        500: {"description": "Error interno del servidor"},
    },
)

# 🔐 Configurar OAuth para Google
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url=settings.GOOGLE_METADATA_URL,
    client_kwargs={"scope": settings.GOOGLE_SCOPE},
)

# 🧩 Inyección de dependencias
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.get("/google/login", summary="Iniciar sesión con Google")
async def login_via_google(request: Request):
    return await oauth.google.authorize_redirect(
        request, redirect_uri=settings.GOOGLE_REDIRECT_URI
    )


@router.get("/google/callback", summary="Callback de Google")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    try:
        factory = ServiceFactory(db, request)
        user_service = factory.get_user_service()
        session_service = factory.get_session_service()

        token = await oauth.google.authorize_access_token(request)
        user_info = token.get("userinfo")

        if not user_info:
            raise HTTPException(status_code=400, detail="No se recibió información del usuario desde Google.")

        user = user_service.get_or_create_user(user_info)
        session = session_service.create_session(user.id, request)

        response = RedirectResponse(url=f"{settings.FRONTEND_URL}/?session_token={session.session_token}")
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=session.session_token,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=settings.SESSION_COOKIE_MAX_AGE,
        )
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en login con Google: {str(e)}")


@router.post("/login", summary="Login con email y contraseña")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    factory: ServiceFactory = Depends(get_factory),
):
    db = factory.db
    session_service = factory.get_session_service()

    user = db.query(factory.user.__class__).filter_by(email=data.email).first()
    if not user or not user.verify_password(data.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    session = session_service.create_session(user.id, request)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session.session_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.SESSION_COOKIE_MAX_AGE,
    )
    return {"message": "✅ Login exitoso"}


@router.post("/logout", summary="Cerrar sesión")
def logout(
    request: Request,
    response: Response,
    factory: ServiceFactory = Depends(get_factory),
):
    session_service = factory.get_session_service()
    token = request.cookies.get(settings.SESSION_COOKIE_NAME) or request.headers.get("Authorization")

    if token:
        session_service.delete_session(token)
        response.delete_cookie(settings.SESSION_COOKIE_NAME)

    return {"message": "👋 Sesión cerrada"}


@router.get("/me", summary="Obtener usuario autenticado")
def me(factory: ServiceFactory = Depends(get_factory)):
    user = factory.user
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }
