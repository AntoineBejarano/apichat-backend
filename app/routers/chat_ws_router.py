from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage, ChatCreate
from app.utils.logger import logger

router = APIRouter(
    tags=["🧠 WebSocket Chat"],
    responses={
        400: {"description": "❌ Invalid request"},
        500: {"description": "❌ Internal server error"},
    },
)


@router.websocket("/ws/{agent_id}")
async def websocket_chat(
    websocket: WebSocket,
    agent_id: UUID,
    db: Session = Depends(get_db),
):
    await websocket.accept()

    factory = ServiceFactory(db, websocket)

    try:
        user_id = factory.user.id
        logger.info(f"✅ WebSocket connected - user_id={user_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Authentication failed: {str(e)}",
        })
        await websocket.close(code=1008)
        return

    orchestrator = factory.get_orchestrator_service()
    chat_service = factory.get_chat_service()

    # Crea o reutiliza un chat existente
    chats = chat_service.get_all(limit=1)
    if chats:
        chat_id = chats[0].id
    else:
        new_chat = chat_service.create_chat(ChatCreate(name="Auto Chat"))
        chat_id = new_chat.id

    try:
        while True:
            data: Dict[str, Any] = await websocket.receive_json()

            try:
                msg = ChatMessage(**data)
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"❌ Invalid message format: {str(e)}",
                })
                continue

            # Parámetros opcionales
            db_ids: Optional[List[UUID]] = data.get("db_ids", [])
            app_ids: Optional[List[UUID]] = data.get("app_ids", [])
            explorer: bool = data.get("explorer", False)

            try:
                response = await orchestrator.handle_user_message(
                    chat_id=chat_id,
                    agent_id=agent_id,
                    message=msg,
                    db_ids=db_ids,
                    app_ids=app_ids,
                    explorer=explorer,
                )

                # Si hay pasos intermedios
                if steps := response.get("steps"):
                    await websocket.send_json({
                        "type": "steps",
                        "steps": steps,
                    })

                # Mensaje final de la IA - formateado para mejor legibilidad
                assistant_response = response.get("assistant_response", "🤖 No response generated")
                
                # Verificar si hay errores en la respuesta
                if "error" in assistant_response.lower() or "error" in response:
                    await websocket.send_json({
                        "type": "error",
                        "message": assistant_response,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    # Formatear la respuesta para que sea más legible
                    await websocket.send_json({
                        "type": "response",
                        "message": assistant_response,
                        "formatted": True,
                        "timestamp": datetime.now().isoformat()
                    })

            except Exception as e:
                logger.error(f"❌ Error while handling message - {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"❌ Failed to process message: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket disconnected - user_id={user_id}")
    except Exception as e:
        logger.error(f"❌ Internal WebSocket error - user_id={user_id} - {str(e)}")
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Internal server error: {str(e)}",
        })
        await websocket.close(code=1011)
