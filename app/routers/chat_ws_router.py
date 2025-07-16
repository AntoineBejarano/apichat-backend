# app/routers/chat_ws_router.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage

router = APIRouter(
    tags=["🧠 WebSocket Chat"],
    responses={
        400: {"description": "Petición inválida"},
        500: {"description": "Error interno del servidor"},
    },
)

# 🧩 Factory para WebSocket (con WebSocket como "Request")
async def get_factory(websocket: WebSocket, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, websocket)


@router.websocket("/ws/{database_id}/{app_id}/{agent_id}")
async def websocket_chat(
    websocket: WebSocket,
    database_id: int,
    app_id: int,
    agent_id: int,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    WebSocket en tiempo real con el orquestador de IA.

    - `database_id`: ID de la base conectada
    - `app_id`: ID de la App con funciones
    - `agent_id`: ID del agente IA
    """
    await websocket.accept()
    user_id = factory.user.id
    # Aquí puedes usar logger.info si prefieres
    print(f"✅ Conexión WebSocket iniciada para user_id={user_id}")

    orchestrator = factory.get_orchestrator_service()

    try:
        while True:
            data: Dict[str, Any] = await websocket.receive_json()
            msg = ChatMessage(**data)

            response = await orchestrator.handle_user_message(
                user_id=user_id,
                database_id=database_id,
                app_id=app_id,
                agent_id=agent_id,
                message=msg,
            )

            if steps := response.get("steps"):
                await websocket.send_json({
                    "type": "steps",
                    "steps": steps,
                })

            await websocket.send_json({
                "type": "response",
                "message": response.get("final", response),
            })

    except WebSocketDisconnect:
        print(f"❌ WebSocket desconectado para user_id={user_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Error interno: {str(e)}",
        })
