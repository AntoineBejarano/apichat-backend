# app/main.py

# 1) Fuerza la importación de todos los modelos
from app.models import init_model_relationships
init_model_relationships()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth_router, chat_router, functions_router, agent_router, database_router,
    chat_history_router, openapi_router, strategy_router, user_router, proxy_router,
    mcp_integration_router, meta_router, session_router, user_role_router, role_router,
    billing_router, integration_router, permission_router, usage_router, event_definition_router,
    event_trigger_router, trigger_router, app_router, performance_router, cache_router,
    # telemetry_router,  # 🎯 FASE 13: Router de telemetría (comentado temporalmente para tests)
    # background_task_router  # Comentado temporalmente para tests
)
# from app.routers.error_handler_router import router as error_handler_router
from app.routers.chat_ws_router import router as ws_router
from app.utils.error_handler import register_error_handlers

import logging
from art import tprint
from contextlib import asynccontextmanager
from sqlalchemy.exc import OperationalError
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings

# ────────────────────────────────
# ASCII logo
# ────────────────────────────────
tprint("APIchat", font="slant")

# ────────────────────────────────
# Logging configuration
# ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("APIchat")

# ────────────────────────────────
# Lifespan Event (Startup/Shutdown)
# ────────────────────────────────
from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.seed.seed_all import seed_permissions, seed_event_definitions

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = next(get_db())
    factory = ServiceFactory(db=db)

    try:
        #seed_permissions(factory)
        #seed_event_definitions(factory)
        logger.info("🔐 Default permissions seeded.")
    except OperationalError as e:
        # Si la tabla 'permissions' (o cualquier otra) no existe, saltamos el seed
        logger.warning("⚠️ No se pudo sembrar permisos (probablemente no hay tablas): %s", e)

    yield
    # (opcional) logic on shutdown

# ────────────────────────────────
# FastAPI instance
# ────────────────────────────────
app = FastAPI(
    title="APIchat",
    description="Connect your APIs and let AI handle the logic.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME  # esto usará "session_token"
)


# 👇 Fuerza OpenAPI 3.0.2 para compatibilidad con Schemathesis
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["openapi"] = "3.0.2"  # 👈 Aquí se fuerza la versión
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ────────────────────────────────
# CORS middleware
# ────────────────────────────────
origins = [
    "http://127.0.0.1:8000/",           # para desarrollo local
    "https://app.apichat.es",         # frontend en producción
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────
# Routers registration
# ────────────────────────────────
app.include_router(meta_router.router); logger.info("📡 Meta router loaded.")
app.include_router(auth_router.router); logger.info("🔐 Auth router loaded.")
app.include_router(app_router.router); logger.info("📦 App router loaded.")
app.include_router(agent_router.router); logger.info("🛣️ Agent router loaded.")
app.include_router(chat_history_router.router); logger.info("📜 Chat history router loaded.")
app.include_router(chat_router.router); logger.info("💬 Chat router loaded.")
app.include_router(database_router.router); logger.info("🗄️ Database router loaded.")
app.include_router(functions_router.router); logger.info("🧠 Functions router loaded.")
app.include_router(openapi_router.router); logger.info("📂 OpenAPI router loaded.")
app.include_router(strategy_router.router); logger.info("📊 Strategies router loaded.")
app.include_router(user_router.router); logger.info("👤 User router loaded.")
app.include_router(proxy_router.router); logger.info("🔌 Proxy router loaded.")
app.include_router(mcp_integration_router.router); logger.info("🔌 MCP Integration router loaded.")
app.include_router(session_router.router);
app.include_router(user_role_router.router); logger.info("👥 User_Role router loaded.")
app.include_router(role_router.router); logger.info("🧩 Role router loaded.")
app.include_router(billing_router.router); logger.info("💳 Billing router loaded.")
app.include_router(integration_router.router); logger.info("🧩 Integration router loaded.")
app.include_router(permission_router.router); logger.info("🔐 Permission router loaded.")
app.include_router(usage_router.router); logger.info("📊 Usage router loaded")
app.include_router(event_definition_router.router); logger.info("📘 EventDefinition router loaded")
app.include_router(event_trigger_router.router); logger.info("📡 EventTrigger router loaded")
app.include_router(trigger_router.router); logger.info("🎯 Trigger router loaded")
app.include_router(performance_router.router); logger.info("📊 Performance router loaded")
app.include_router(cache_router.router); logger.info("🗄️ Cache router loaded")
# app.include_router(telemetry_router.router); logger.info("🎯 FASE 13: Telemetría router loaded")  # Comentado temporalmente para tests
# app.include_router(error_handler_router); logger.info("🎯 Error Handler router loaded")
# app.include_router(background_task_router.router); logger.info("🚀 Background Task router loaded") # Comentado temporalmente para tests

app.include_router(ws_router); logger.info("🔄 WebSocket router loaded.")

logger.info("🚀 APIchat is up and running.")

register_error_handlers(app)
