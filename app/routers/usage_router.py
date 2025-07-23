from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.usage_schema import UsageOut

router = APIRouter(
    prefix="/usage",
    tags=["📊 Logs & Usage"],
    responses={
        401: {"description": "Unauthorized"},
        500: {"description": "Internal Server Error"},
    }
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.get(
    "/",
    response_model=UsageOut,
    status_code=status.HTTP_200_OK,
    summary="Obtener métricas de uso",
    description=(
        "Devuelve las métricas de uso de la API para el usuario autenticado:\n\n"
        "- `total_tokens`: suma de tokens consumidos en mensajes y llamadas a función.\n"
        "- `function_calls`: lista de funciones invocadas con su recuento y tokens usados."
    ),
    response_description="Métricas de tokens y llamadas a función",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "total_tokens": 12345,
                        "function_calls": [
                            {
                                "function_name": "translate_text",
                                "count": 10,
                                "tokens_used": 500
                            },
                            {
                                "function_name": "summarize",
                                "count": 5,
                                "tokens_used": 250
                            }
                        ]
                    }
                }
            }
        }
    }
)
def get_usage(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_usage_service().get_usage()
