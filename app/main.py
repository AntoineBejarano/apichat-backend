# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth_router, chat_router, functions_router, strategies_router,
    agent_router, database_router, chat_history_router, openapi_router,
    user_router
)
from app.routers.chat_ws_router import router as ws_router
from app.core.servicefactory import initialize_dependencies

import logging
from art import tprint

# ────────────────────────────────
# ASCII logo
# ────────────────────────────────
tprint("APIchat", font="slant")  # Puedes cambiar a 'block', 'banner3-D', etc.

# ────────────────────────────────
# Logging configuration
# ────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("APIchat")

# ────────────────────────────────
# FastAPI instance
# ────────────────────────────────
app = FastAPI(
    title="APIchat",
    description="Connect your APIs and let AI handle the logic.",
    version="1.0.0",
)

# ────────────────────────────────
# CORS middleware (refine in prod)
# ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────
# Initialization
# ────────────────────────────────
initialize_dependencies()
logger.info("✅ Dependencies initialized successfully.")

# ────────────────────────────────
# Routers registration
# ────────────────────────────────
app.include_router(agent_router.router); logger.info("🔌 Agent router loaded.")
app.include_router(auth_router.router); logger.info("🔐 Auth router loaded.")
app.include_router(chat_history_router.router); logger.info("📜 Chat history router loaded.")
app.include_router(chat_router.router); logger.info("💬 Chat router loaded.")
app.include_router(database_router.router); logger.info("🗄️  Database router loaded.")
app.include_router(functions_router.router); logger.info("🧠 Functions router loaded.")
app.include_router(openapi_router.router); logger.info("📂 OpenAPI router loaded.")
app.include_router(strategies_router.router); logger.info("📊 Strategies router loaded.")
app.include_router(user_router.router); logger.info("👤 User router loaded.")
app.include_router(ws_router); logger.info("🔄 WebSocket router loaded.")

logger.info("🚀 APIchat is up and running.")
