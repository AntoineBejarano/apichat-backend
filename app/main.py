# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth_router, chat_router, functions_router, agent_router, database_router,
    chat_history_router, openapi_router, strategy_router, user_router, proxy_router, mcp_integration_router,
    meta_router
)
from app.routers.chat_ws_router import router as ws_router

import logging
from art import tprint

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
# FastAPI instance
# ────────────────────────────────
app = FastAPI(
    title="APIchat",
    description="Connect your APIs and let AI handle the logic.",
    version="1.0.0",
)

# ────────────────────────────────
# CORS middleware
# ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cambia esto en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────────
# Routers registration
# ────────────────────────────────
app.include_router(meta_router.router); logger.info("🔐 Meta router loaded.")
app.include_router(auth_router.router); logger.info("🔐 Auth router loaded.")
app.include_router(agent_router.router); logger.info("🛣️ Agent router loaded.")
app.include_router(chat_history_router.router); logger.info("📜 Chat history router loaded.")
app.include_router(chat_router.router); logger.info("💬 Chat router loaded.")
app.include_router(database_router.router); logger.info("🗄️  Database router loaded.")
app.include_router(functions_router.router); logger.info("🧠 Functions router loaded.")
app.include_router(openapi_router.router); logger.info("📂 OpenAPI router loaded.")
app.include_router(strategy_router.router); logger.info("📊 Strategies router loaded.")
app.include_router(user_router.router); logger.info("👤 User router loaded.")
app.include_router(proxy_router.router); logger.info("🔌 Proxy router loaded.")
app.include_router(mcp_integration_router.router); logger.info("🔌 MCP Integration router loaded.")


app.include_router(ws_router); logger.info("🔄 WebSocket router loaded.")

logger.info("🚀 APIchat is up and running.")
