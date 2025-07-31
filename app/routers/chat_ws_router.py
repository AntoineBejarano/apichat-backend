from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_schema import ChatCreate  # para crear nuevo chat
from app.utils.logger import logger

router = APIRouter(
    tags=["🧠 WebSocket Chat"],
    responses={
        400: {"description": "❌ Petición inválida"},
        500: {"description": "❌ Error interno del servidor"},
    },
)

# 🧩 Factory para WebSocket (con WebSocket como "Request")
async def get_factory(websocket: WebSocket, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, websocket)


@router.websocket("/ws/{database_id}/{app_id}/{agent_id}")
async def websocket_chat(
    websocket: WebSocket,
    database_id: UUID,
    app_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
):
    """
    WebSocket en tiempo real con el orquestador de IA.

    - `database_id`: ID de la base conectada
    - `app_id`: ID de la App con funciones
    - `agent_id`: ID del agente IA
    """
    await websocket.accept()

    factory = ServiceFactory(db, websocket)
    try:
        user_id = factory.user.id
        logger.info(f"✅ WebSocket conectado - user_id={user_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Autenticación fallida: {str(e)}",
        })
        await websocket.close(code=1008)  # Policy Violation
        return

    orchestrator = factory.get_orchestrator_service()
    chat_service = factory.get_chat_service()

    # Reutilizar o crear chat_id automáticamente
    chats = chat_service.get_all(limit=1)
    if chats:
        chat_id = chats[0].id
    else:
        new_chat = chat_service.create_chat(ChatCreate(name="Chat automático"))
        chat_id = new_chat.id

    try:
        while True:
            data: Dict[str, Any] = await websocket.receive_json()
            msg = ChatMessage(**data)

            response = await orchestrator.handle_user_message(
                chat_id=chat_id,
                database_id=database_id,
                app_id=app_id,
                agent_id=agent_id,
                message=msg
            )

            if steps := response.get("steps"):
                await websocket.send_json({
                    "type": "steps",
                    "steps": steps,
                })

            await websocket.send_json({
                "type": "response",
                "message": response.get("assistant_response", response),
            })

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket desconectado - user_id={user_id}")
    except Exception as e:
        logger.error(f"❌ Error interno en WebSocket - user_id={user_id} - {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Error interno: {str(e)}",
        })
        await websocket.close(code=1011)  # Internal error
