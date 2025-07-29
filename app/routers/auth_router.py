import os
import logging
from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth

from app.core.config import settings
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.login_schema import LoginRequest, RegisterRequest
from app.models.user_model import User
from app.models.role_model import Role

router = APIRouter(
    prefix="/auth",
    tags=["🔐 Auth"],
    responses={
        401: {"description": "No autorizado"},
        400: {"description": "Error de validación"},
        500: {"description": "Error interno del servidor"},
    },
)

logger = logging.getLogger(__name__)

logger.info("🔧 Registrando OAuth con Google")
logger.info(f"🌍 GOOGLE_METADATA_URL: {settings.GOOGLE_METADATA_URL}")
logger.info(f"↪️ GOOGLE_REDIRECT_URI: {settings.GOOGLE_REDIRECT_URI}")

if not settings.GOOGLE_METADATA_URL.startswith("http"):
    raise ValueError(f"❌ URL inválida para Google Metadata: {settings.GOOGLE_METADATA_URL}")

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url=settings.GOOGLE_METADATA_URL,
    client_kwargs={"scope": settings.GOOGLE_SCOPE},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

def _set_session_cookie(response: Response, token: str):
    environment = os.getenv("ENVIRONMENT", "development")
    is_local = environment == "development"

    logger.info(f"🍪 Set-Cookie: {settings.SESSION_COOKIE_NAME} (secure={not is_local}, samesite={'lax' if is_local else 'none'})")

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=not is_local,
        samesite="lax" if is_local else "none",
        domain=None if is_local else "apichat.es",
        max_age=settings.SESSION_COOKIE_MAX_AGE
    )

def assign_default_user_role(db: Session, user: User):
    logger.info(f"🔑 Asignando rol 'user' por defecto a {user.email}")
    role = db.query(Role).filter_by(name="user").first()
    if role and role not in user.roles:
        user.roles.append(role)
        db.commit()
        db.refresh(user)
        logger.info(f"✅ Rol 'user' asignado a {user.email}")

@router.get("/google/login", summary="Iniciar sesión con Google")
async def login_via_google(request: Request):
    logger.info("➡️ Redirigiendo a Google para login...")
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        prompt="consent"
    )

@router.get("/google/callback", summary="Callback de Google")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    from app.schemas.user_schema import UserCreate

    try:
        logger.info(f"🔁 Callback recibido: {request.url}")
        factory = ServiceFactory(db, request)
        user_service = factory.get_user_service()
        session_service = factory.get_session_service()

        token = await oauth.google.authorize_access_token(request)
        logger.info(f"🔑 Token recibido de Google: {token}")

        resp = await oauth.google.get("https://www.googleapis.com/oauth2/v1/userinfo", token=token)
        user_info = resp.json()
        logger.info(f"👤 Información del usuario de Google: {user_info}")

        if not user_info:
            logger.warning("⚠️ No se recibió información del usuario desde Google.")
            raise HTTPException(status_code=400, detail="No se recibió información del usuario desde Google.")

        user_data = UserCreate(
            email=user_info["email"],
            name=user_info.get("name") or user_info["email"].split("@")[0],
        )

        user = user_service.get_or_create_user(user_data)
        logger.info(f"✅ Usuario creado o recuperado: {user.email}")
        assign_default_user_role(db, user)

        session = session_service.create_session(user.id, request)
        logger.info(f"📦 Sesión creada con token: {session.session_token}")

        response = RedirectResponse(url=f"{settings.FRONTEND_URL}/")
        _set_session_cookie(response, session.session_token)
        return response

    except Exception as e:
        logger.exception("❌ Error en login con Google")
        raise HTTPException(status_code=500, detail=f"Error en login con Google: {str(e)}")

@router.post("/login", summary="Login con email y contraseña")
def login(data: LoginRequest, request: Request, response: Response, factory: ServiceFactory = Depends(get_factory)):
    logger.info(f"🔐 Intentando login con email: {data.email}")
    db = factory.db
    session_service = factory.get_session_service()

    user = db.query(User).filter_by(email=data.email).first()
    if not user or not user.verify_password(data.password):
        logger.warning("🚫 Credenciales inválidas")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")

    session = session_service.create_session(user.id, request)
    logger.info(f"✅ Login exitoso: {user.email}, sesión: {session.session_token}")
    _set_session_cookie(response, session.session_token)
    return {"message": "✅ Login exitoso"}

@router.post("/logout", summary="Cerrar sesión")
def logout(request: Request, response: Response, factory: ServiceFactory = Depends(get_factory)):
    session_service = factory.get_session_service()
    token = request.cookies.get(settings.SESSION_COOKIE_NAME) or request.headers.get("Authorization")

    if token:
        logger.info(f"🚪 Cerrando sesión con token: {token}")
        session_service.delete_session(token)
        response.delete_cookie(settings.SESSION_COOKIE_NAME)
    else:
        logger.warning("⚠️ Token de sesión no encontrado")

    return {"message": "👋 Sesión cerrada"}

@router.get("/me", summary="Obtener usuario autenticado")
def me(factory: ServiceFactory = Depends(get_factory)):
    user = factory.user
    logger.info(f"👤 Usuario autenticado: {user.email}")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
    }

@router.post("/register", summary="Registrar nuevo usuario")
def register(data: RegisterRequest, request: Request, response: Response, factory: ServiceFactory = Depends(get_factory)):
    logger.info(f"📝 Registrando nuevo usuario: {data.email}")
    db = factory.db
    session_service = factory.get_session_service()

    existing = db.query(User).filter_by(email=data.email).first()
    if existing:
        logger.warning("⚠️ El email ya está registrado")
        raise HTTPException(status_code=400, detail="El email ya está registrado")

    user = User(email=data.email, name=data.name)
    user.set_password(data.password)
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"✅ Usuario registrado: {user.email}")
    assign_default_user_role(db, user)
    session = session_service.create_session(user.id, request)
    logger.info(f"📦 Sesión creada con token: {session.session_token}")
    _set_session_cookie(response, session.session_token)
    return {"message": "✅ Registro y login exitoso"}
