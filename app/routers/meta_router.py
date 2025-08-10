# app/routers/meta_router.py
"""
Router: Meta ⚙️
Pequeño punto de entrada para comprobar salud del servicio
y conocer la versión desplegada.
"""

import importlib.metadata
import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["⚙️ Meta"],
    responses={500: {"description": "Error interno del servidor"}},
)


# ------------------------------------------------------------------ #
# Helper: ServiceFactory inyectado (con DB + Request)                #
# ------------------------------------------------------------------ #
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


# ------------------------------------------------------------------ #
# GET /health                                                        #
# ------------------------------------------------------------------ #
@router.get(
    "/health",
    summary="🏥 Health‑check",
    response_description="Estado actual de la API y sus dependencias",
)
def health_check(factory: ServiceFactory = Depends(get_factory)) -> Dict[str, str]:
    """
    Comprueba conectividad con la **base de datos** y dependencias críticas.

    Devuelve un diccionario con el estado de cada subsistema.
    """
    status_report = {"timestamp": datetime.now(timezone.utc).isoformat()}
    db = factory.db

    # --- Base de datos -------------------------------------------------
    try:
        db.execute(text("SELECT 1"))  # consulta trivial
        status_report["database"] = "ok"
    except Exception as e:
        logger.exception("❌ DB health‑check failed")
        status_report["database"] = f"error: {e}"

    # --- OpenAI (opcional) -------------------------------------------
    try:
        factory.get_openai_service()  # solo aseguramos instanciación / clave
        status_report["openai"] = "ok"
    except Exception as e:
        status_report["openai"] = f"error: {e}"

    # Resultado global
    overall_ok = all(v == "ok" for v in status_report.values() if v != "timestamp")
    if not overall_ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=status_report)

    return status_report


# ------------------------------------------------------------------ #
# GET /version                                                       #
# ------------------------------------------------------------------ #
@router.get(
    "/version",
    summary="📦 Versión API",
    response_description="Número de versión de la API desplegada",
)
def api_version() -> Dict[str, str]:
    """
    Devuelve la **versión** del sistema.

    - Se intenta leer desde `pyproject.toml`/`setup.py` vía
      `importlib.metadata.version('apichat-backend')`.
    - Si no se encuentra, se recurre al valor de ajustes (`settings.APP_VERSION`).
    """
    try:
        version = importlib.metadata.version("apichat-backend")
    except importlib.metadata.PackageNotFoundError:
        version = getattr(settings, "APP_VERSION", "dev")

    return {"version": version}
