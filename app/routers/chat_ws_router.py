from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.schemas.chat_schema import ChatMessage
from app.core.database import get_db
from app.core.servicefactory import ServiceFactory

router = APIRouter(
    tags=["🧠 WebSocket Chat"],
    responses={
        400: {"description": "Petición inválida"},
        500: {"description": "Error interno del servidor"}
    }
)

# ✅ Inyector del ServiceFactory para WebSocket
async def get_factory(websocket: WebSocket, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, websocket)

@router.websocket("/ws/{database_id}/{app_id}/{agent_id}")
async def websocket_chat(
    websocket: WebSocket,
    database_id: int,
    app_id: int,
    agent_id: int,
    factory: ServiceFactory = Depends(get_factory)
):
    """
    🔌 WebSocket persistente que permite conversación en tiempo real con IA.

    Transfiere mensajes desde el cliente al agente inteligente,
    respondiendo de forma automática. Cada mensaje puede incluir
    pasos (steps) detallados para seguimiento en frontend.
    """
    await websocket.accept()
    print(f"✅ Conexión WebSocket aceptada para user_id={factory.user.id}")

    try:
        orchestrator = factory.get_orchestrator_service()

        while True:
            data: Dict[str, Any] = await websocket.receive_json()
            msg = ChatMessage(**data)

            # 🔄 Procesar mensaje con el orquestador
            response = await orchestrator.handle_user_message(
                user_id=factory.user.id,
                database_id=database_id,
                app_id=app_id,
                agent_id=agent_id,
                message=msg
            )

            steps = response.get("steps")
            final_message = response.get("final", response)

            if steps:
                await websocket.send_json({
                    "type": "steps",
                    "steps": steps
                })

            await websocket.send_json({
                "type": "response",
                "message": final_message
            })

    except WebSocketDisconnect:
        print(f"❌ Usuario {factory.user.id} desconectado del WebSocket.")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Error interno: {str(e)}"
        })
