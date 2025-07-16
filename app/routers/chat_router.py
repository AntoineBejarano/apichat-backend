# app/routers/chat_router.py

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat IA"],
    responses={404: {"description": "No encontrado"}},
)

# 🧩 Inyección de ServiceFactory
def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)


@router.post(
    "/{database_id}/{app_id}/{agent_id}",
    summary="Enviar mensaje al asistente de IA",
    description="""
Envía un mensaje a tu agente de IA, quien puede usar funciones, estrategias y bases de datos para responder inteligentemente.
""",
    response_description="Respuesta generada por el asistente"
)
async def chat_with_agent(
    database_id: int,
    app_id: int,
    agent_id: int,
    message: ChatMessage,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Endpoint para enviar un mensaje a través de HTTP (alternativa a WebSocket).
    Orquestado por OrchestratorService.
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
