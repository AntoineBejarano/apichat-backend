from fastapi import APIRouter, UploadFile, File, Depends, Request, HTTPException, status
import json

from app.core.servicefactory import ServiceFactory
from app.core.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/openapi",
    tags=["📄 OpenAPI"],
    responses={
        400: {"description": "Archivo inválido o contenido JSON incorrecto"},
        422: {"description": "Error de validación en el contenido del OpenAPI"},
        500: {"description": "Error interno del servidor"},
    }
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/upload",
    summary="📤 Subir archivo OpenAPI",
    description="""
Sube un archivo `.json` con especificaciones OpenAPI.  
El sistema lo parseará y generará funciones disponibles automáticamente.

**Requisitos:**
- El archivo debe estar en formato JSON válido.
- El contenido debe seguir el estándar OpenAPI (v3).

**Respuesta:** Lista de funciones creadas.
"""
)
async def upload_openapi(
    file: UploadFile = File(..., description="Archivo JSON con el esquema OpenAPI"),
    factory: ServiceFactory = Depends(get_factory)
):
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo debe ser un JSON (.json)"
        )

    try:
        contents = await file.read()
        openapi_dict = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contenido JSON inválido"
        )

    try:
        processor = factory.get_openapi_processor()
        result = processor.process(openapi_dict)
        return {
            "message": f"{len(result)} funciones creadas correctamente.",
            "functions": [f.name for f in result]
        }

    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando el archivo: {str(e)}"
        )
