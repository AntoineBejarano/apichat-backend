from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import re
import asyncio

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage, ChatCreate
from app.utils.logger import logger
from app.services.common.ws_emitter import get_ws_emitter
from app.services.notifications.schema_notification_service import get_schema_notification_service
from app.services.management.system_readiness_manager import SystemReadinessManager
from app.services.management.environment_preparation_orchestrator import EnvironmentPreparationOrchestrator

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

    # 🔧 CORRECCIÓN: Validar token de sesión y recuperar usuario real
    try:
        # Obtener token de sesión del WebSocket (prioridad: cookies > query_params > headers)
        session_token = None
        
        # 1. Intentar obtener de cookies (método principal)
        if hasattr(websocket, 'cookies') and websocket.cookies:
            session_token = websocket.cookies.get("session_token")
        
        # 2. Si no hay cookies, intentar de query parameters
        if not session_token:
            session_token = websocket.query_params.get("session_token")
        
        # 3. Si no hay query params, intentar de headers
        if not session_token:
            session_token = websocket.headers.get("session_token")
        
        # 4. Si no hay headers, intentar de Authorization header
        if not session_token:
            auth_header = websocket.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                session_token = auth_header.replace("Bearer ", "")
        
        if not session_token:
            await websocket.send_json({
                "type": "error",
                "message": "❌ No se proporcionó token de sesión en cookies, query params, headers o Authorization",
            })
            await websocket.close(code=1008)
            return
        
        # Validar sesión y obtener usuario real
        from app.services.data.session_service import SessionService
        session_service = SessionService(db)
        session = session_service.validate_session(session_token)
        
        if not session or not session.user:
            await websocket.send_json({
                "type": "error",
                "message": "❌ Sesión inválida o expirada",
            })
            await websocket.close(code=1008)
            return
        
        # Usar usuario real de la sesión
        real_user = session.user
        factory = ServiceFactory(websocket, real_user)
        
        logger.info(f"✅ WebSocket connected - user_id={real_user.id} (sesión válida)")
        
        # 🔧 FASE 4: Inicializar servicios de readiness y preparación del entorno
        try:
            # Inicializar SystemReadinessManager
            system_readiness_manager = SystemReadinessManager(factory)
            await system_readiness_manager.initialize_system()
            
            # Inicializar EnvironmentPreparationOrchestrator
            env_prep_orchestrator = EnvironmentPreparationOrchestrator(factory)
            
            # Enviar estado inicial del sistema
            system_status = await system_readiness_manager.get_system_status()
            await websocket.send_json({
                "type": "system.status",
                "data": system_status,
                "message": "🔍 Verificando estado del sistema...",
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"[ChatWS] 🔍 Estado del sistema verificado para usuario {real_user.id}")
            
        except Exception as readiness_error:
            logger.warning(f"[ChatWS] ⚠️ Error inicializando servicios de readiness: {readiness_error}")
            await websocket.send_json({
                "type": "system.warning",
                "message": "⚠️ Advertencia: No se pudo verificar el estado del sistema",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Error de autenticación: {str(e)}",
        })
        await websocket.close(code=1008)
        return
    
    # El usuario ya está validado arriba, continuar con la lógica del WebSocket

    orchestrator = factory.get_orchestrator_service()
    chat_service = factory.get_chat_service()
    
    # 🔧 FASE 4: Verificar readiness del entorno antes de procesar mensajes
    # Definir recursos del usuario (esto se puede mejorar para obtener de la base de datos)
    user_resources = {
        "db_uuid": None,  # TODO: Obtener de la base de datos
        "app_id": None,   # TODO: Obtener de la base de datos
        "strategy_ids": [] # TODO: Obtener de la base de datos
    }
    
    try:
        
        # Verificar readiness del entorno
        env_status = await env_prep_orchestrator.get_environment_status(
            user_id=str(real_user.id),
            **user_resources
        )
        
        # Enviar estado del entorno
        await websocket.send_json({
            "type": "environment.status",
            "data": env_status,
            "message": "🔍 Verificando recursos del entorno...",
            "timestamp": datetime.now().isoformat()
        })
        
        # Si el entorno no está listo, iniciar preparación automática
        if not env_status.get("environment_ready", False):
            await websocket.send_json({
                "type": "environment.preparing",
                "message": "🚀 Preparando entorno automáticamente...",
                "timestamp": datetime.now().isoformat()
            })
            
            # Iniciar preparación del entorno en background
            prep_result = await env_prep_orchestrator.prepare_user_environment(
                user_id=str(real_user.id),
                **user_resources
            )
            
            if prep_result.get("success"):
                await websocket.send_json({
                    "type": "environment.preparation_started",
                    "data": prep_result,
                    "message": "✅ Preparación del entorno iniciada",
                    "timestamp": datetime.now().isoformat()
                })
                
                # Iniciar monitoreo de readiness en background
                asyncio.create_task(env_prep_orchestrator.wait_for_environment_ready(
                    user_id=str(real_user.id),
                    **user_resources
                ))
            else:
                await websocket.send_json({
                    "type": "environment.preparation_failed",
                    "data": prep_result,
                    "message": "❌ Error iniciando preparación del entorno",
                    "timestamp": datetime.now().isoformat()
                })
        
        logger.info(f"[ChatWS] 🔍 Estado del entorno verificado para usuario {real_user.id}")
        
    except Exception as env_error:
        logger.warning(f"[ChatWS] ⚠️ Error verificando readiness del entorno: {env_error}")
        await websocket.send_json({
            "type": "environment.warning",
            "message": "⚠️ Advertencia: No se pudo verificar el estado del entorno",
            "timestamp": datetime.now().isoformat()
        })

    # 🔧 FASE 5: Servicios de notificaciones y WebSocket
    ws_emitter = get_ws_emitter()
    notification_service = get_schema_notification_service(factory)
    
    # Registrar conexión WebSocket para notificaciones
    ws_emitter.register_connection(str(real_user.id), websocket)
    logger.info(f"[ChatWS] 🔗 Conexión WebSocket registrada para notificaciones del usuario {real_user.id}")
    
    # Suscribir usuario a notificaciones de schema
    notification_service.subscribe_user(real_user.id)
    logger.info(f"[ChatWS] 📧 Usuario {real_user.id} suscrito a notificaciones de schema")

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
            
            # 🔧 FASE 4: Manejar solicitudes de estado del sistema
            if data.get("type") == "system.status.request":
                try:
                    # Obtener estado actual del sistema
                    system_status = await system_readiness_manager.get_system_status()
                    
                    await websocket.send_json({
                        "type": "system.status",
                        "data": system_status,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    logger.info(f"[ChatWS] 🔍 Estado del sistema enviado a usuario {real_user.id}")
                    continue
                    
                except Exception as e:
                    logger.error(f"[ChatWS] ❌ Error obteniendo estado del sistema: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"❌ Error obteniendo estado del sistema: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
            
            # 🔧 FASE 4: Manejar solicitudes de estado del entorno
            if data.get("type") == "environment.status.request":
                try:
                    # Obtener estado actual del entorno
                    env_status = await env_prep_orchestrator.get_environment_status(
                        user_id=str(real_user.id),
                        **user_resources
                    )
                    
                    await websocket.send_json({
                        "type": "environment.status",
                        "data": env_status,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    logger.info(f"[ChatWS] 🔍 Estado del entorno enviado a usuario {real_user.id}")
                    continue
                    
                except Exception as e:
                    logger.error(f"[ChatWS] ❌ Error obteniendo estado del entorno: {str(e)}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"❌ Error obteniendo estado del entorno: {str(e)}",
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
        
        # 🔧 FASE 5: Limpiar conexión y suscripciones
        try:
            ws_emitter.unregister_connection(str(user_id), websocket)
            notification_service.unsubscribe_user(user_id)
            logger.info(f"[ChatWS] 🧹 Conexión WebSocket y suscripciones limpiadas para usuario {user_id}")
        except Exception as cleanup_error:
            logger.warning(f"[ChatWS] ⚠️ Error limpiando conexión: {cleanup_error}")
            
    except Exception as e:
        logger.error(f"❌ Internal WebSocket error - user_id={user_id} - {str(e)}")
        
        # 🔧 FASE 5: Limpiar conexión en caso de error
        try:
            ws_emitter.unregister_connection(str(user_id), websocket)
            notification_service.unsubscribe_user(user_id)
        except Exception as cleanup_error:
            logger.warning(f"[ChatWS] ⚠️ Error limpiando conexión en error: {cleanup_error}")
            
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Internal server error: {str(e)}",
        })
        await websocket.close(code=1011)
