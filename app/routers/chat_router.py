from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.servicefactory import ServiceFactory
from app.schemas.chat_schema import ChatMessage

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat IA"],
    responses={404: {"description": "No encontrado"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/{database_id}/{app_id}/{agent_id}",
    summary="Enviar mensaje al asistente de IA",
    description="""
Envía un mensaje a tu agente de inteligencia artificial, quien puede usar funciones, bases de datos o simplemente responder.

- `database_id`: ID de la base de datos conectada
- `app_id`: ID de la App donde están las funciones
- `agent_id`: ID del agente que contiene el system prompt y estrategia
""",
    response_description="Respuesta generada por el asistente",
)
async def chat_with_agent(
    database_id: int,
    app_id: int,
    agent_id: int,
    message: ChatMessage,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    Procesa un mensaje desde el usuario hacia el agente inteligente.
    Este endpoint es útil como alternativa a WebSocket cuando quieres llamadas HTTP simples.
    """
    try:
        orchestrator = factory.get_orchestrator_service()
        response = await orchestrator.handle_user_message(
            user_id=factory.user.id,
            database_id=database_id,
            app_id=app_id,
            agent_id=agent_id,
            message=message
        )
        return JSONResponse(content=response)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )
