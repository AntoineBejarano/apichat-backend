from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import re

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


def resolve_step_templates(steps: List[Dict[str, Any]], variables: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Resuelve los templates en los steps usando las variables disponibles.
    Reemplaza {variable} y {{variable}} con los valores reales de forma segura.
    """
    if not steps or not variables:
        return steps
    
    resolved_steps = []
    
    for step in steps:
        resolved_step = step.copy()
        
        # Resolver template en message si existe
        if "template" in step and step["template"]:
            template = step["template"]
            resolved_message = resolve_template_string(template, variables)
            resolved_step["message"] = resolved_message
            logger.info(f"[ChatWS] ✅ Template resuelto: '{template}' -> '{resolved_message}'")
        
        # También resolver message directo si no hay template
        elif "message" in step and step["message"]:
            message = step["message"]
            resolved_message = resolve_template_string(message, variables)
            resolved_step["message"] = resolved_message
            logger.info(f"[ChatWS] ✅ Message resuelto: '{message}' -> '{resolved_message}'")
        
        resolved_steps.append(resolved_step)
    
    return resolved_steps


def resolve_template_string(template: str, variables: Dict[str, Any]) -> str:
    """
    Resuelve templates en un string usando las variables disponibles.
    Reemplaza {variable} y {{variable}} con los valores reales de forma segura.
    IMPORTANTE: Reemplaza primero {{variable}} para evitar conflictos.
    """
    if not template or not variables:
        return template
    
    resolved = template
    
    # Primero reemplazar {{variable}} para evitar conflictos
    for var_name, var_value in variables.items():
        placeholder_double = "{{" + var_name + "}}"
        resolved = resolved.replace(placeholder_double, str(var_value))
    
    # Luego reemplazar {variable}
    for var_name, var_value in variables.items():
        placeholder_single = "{" + var_name + "}"
        resolved = resolved.replace(placeholder_single, str(var_value))
    
    return resolved


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
    
    # 🔧 NUEVO: Establecer chat_id en el factory para tracking de LLM runs
    factory.set_current_chat_id(chat_id)
    logger.info(f"[ChatWS] 🔗 Chat ID establecido en factory: {chat_id}")

    try:
        while True:
            data: Dict[str, Any] = await websocket.receive_json()

            # 🚀 FASE 3: Manejar respuestas de decisión
            if data.get("type") == "decision.response":
                try:
                    decision_id = data.get("decision_id")
                    action = data.get("action")
                    user_message = data.get("user_message")
                    selected_options = data.get("selected_options")
                    
                    if decision_id and action:
                        # Procesar la respuesta de decisión
                        success = orchestrator.decision_manager.submit_decision_response(
                            decision_id=decision_id,
                            action=action,
                            user_message=user_message,
                            selected_options=selected_options
                        )
                        
                        if success:
                            await websocket.send_json({
                                "type": "decision.confirmed",
                                "message": f"✅ Decisión confirmada: {action}",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.info(f"[ChatWS] ✅ Respuesta de decisión procesada: {action}")
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "❌ Decisión no encontrada o ya expirada",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.warning(f"[ChatWS] ⚠️ Decisión {decision_id} no encontrada")
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "❌ Formato de decisión inválido",
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.warning(f"[ChatWS] ⚠️ Formato de decisión inválido: {data}")
                    
                    continue  # Continuar con el siguiente mensaje
                    
                except Exception as e:
                    logger.error(f"[ChatWS] ❌ Error procesando decisión: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"❌ Error procesando decisión: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
            
            # 🎯 FASE 8: Manejar respuestas a propuestas de recursos
            if data.get("type") == "resource.proposal.response":
                try:
                    proposal_id = data.get("proposal_id")
                    action = data.get("action")
                    selected_option = data.get("selected_option")
                    user_message = data.get("user_message")
                    
                    if proposal_id and action:
                        logger.info(f"[ChatWS] 🎯 Respuesta a propuesta de recursos: {action}")
                        
                        # Si el usuario eligió una opción Guided, cambiar a modo Guided
                        if action.startswith("guided_option_"):
                            try:
                                # Extraer IDs de la opción seleccionada
                                if selected_option and "database_id" in selected_option and "application_id" in selected_option:
                                    db_id = selected_option["database_id"]
                                    app_id = selected_option["application_id"]
                                    
                                    # Crear nuevo mensaje para modo Guided
                                    guided_message = ChatMessage(
                                        role="user",
                                        content=f"Cambiar a modo Guided con DB {db_id} y App {app_id}. {user_message or ''}"
                                    )
                                    
                                    # Ejecutar en modo Guided
                                    guided_response = await orchestrator.handle_user_message(
                                        chat_id=chat_id,
                                        agent_id=agent_id,
                                        message=guided_message,
                                        db_ids=[UUID(db_id)],
                                        app_ids=[UUID(app_id)],
                                        explorer=False,  # Cambiar a Guided
                                    )
                                    
                                    # Enviar respuesta del modo Guided
                                    await websocket.send_json({
                                        "type": "guided_response",
                                        "message": "🔄 Cambiando a modo Guided...",
                                        "data": guided_response,
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    
                                    logger.info(f"[ChatWS] ✅ Cambio a modo Guided completado: DB {db_id}, App {app_id}")
                                    
                                else:
                                    await websocket.send_json({
                                        "type": "error",
                                        "message": "❌ Opción de recursos inválida",
                                        "timestamp": datetime.now().isoformat()
                                    })
                                    
                            except Exception as e:
                                logger.error(f"[ChatWS] ❌ Error cambiando a modo Guided: {str(e)}")
                                await websocket.send_json({
                                    "type": "error",
                                    "message": f"❌ Error cambiando a modo Guided: {str(e)}",
                                    "timestamp": datetime.now().isoformat()
                                })
                        
                        elif action == "see_more":
                            # El usuario quiere ver más opciones
                            await websocket.send_json({
                                "type": "notice",
                                "message": "🔍 Buscando más opciones de recursos...",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.info(f"[ChatWS] 🔍 Usuario solicitó más opciones de recursos")
                        
                        elif action == "explore_only":
                            # El usuario quiere continuar en modo Explorer
                            await websocket.send_json({
                                "type": "notice",
                                "message": "✅ Continuando en modo Explorer",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.info(f"[ChatWS] ✅ Usuario eligió continuar en modo Explorer")
                        
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "❌ Acción de propuesta inválida",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.warning(f"[ChatWS] ⚠️ Acción de propuesta inválida: {action}")
                    
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "❌ Formato de propuesta inválido",
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.warning(f"[ChatWS] ⚠️ Formato de propuesta inválido: {data}")
                    
                    continue  # Continuar con el siguiente mensaje
                    
                except Exception as e:
                    logger.error(f"[ChatWS] ❌ Error procesando propuesta de recursos: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"❌ Error procesando propuesta: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

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

                # 🔧 FIX: Resolver templates en los steps antes de enviarlos
                steps = response.get("steps", [])
                if steps:
                    # Obtener variables del execution_results para resolver templates
                    execution_results = response.get("execution_results", {})
                    variables = execution_results.get("variables", {})
                    
                    # Resolver templates en los steps
                    resolved_steps = resolve_step_templates(steps, variables)
                    
                    # Enviar steps con templates resueltos
                    await websocket.send_json({
                        "type": "steps",
                        "steps": resolved_steps,
                    })
                    
                    logger.info(f"[ChatWS] ✅ Steps enviados con templates resueltos usando {len(variables)} variables")

                # 🔧 FIX: Obtener la respuesta del asistente y resolver cualquier template restante
                assistant_response = response.get("assistant_response", "🤖 No response generated")
                
                # Si la respuesta contiene templates, resolverlos también
                if assistant_response and ("{" in assistant_response or "{{" in assistant_response):
                    execution_results = response.get("execution_results", {})
                    variables = execution_results.get("variables", {})
                    
                    # Resolver templates en la respuesta del asistente usando el método auxiliar
                    resolved_response = resolve_template_string(assistant_response, variables)
                    
                    if resolved_response != assistant_response:
                        logger.info(f"[ChatWS] ✅ Template en assistant_response resuelto: '{assistant_response}' -> '{resolved_response}'")
                        assistant_response = resolved_response
                
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
