# app/utils/error_handler.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app: FastAPI):

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"[HTTPException] {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"[ValidationError] {exc.errors()}")
        return JSONResponse(
            status_code=422,
            content={"error": "Validación fallida", "details": exc.errors()}
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"[DBError] {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error de base de datos"}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"[UnhandledError] {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Error interno del servidor"}
        )
