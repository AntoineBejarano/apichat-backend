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
        env_prep_orchestrator = None  # Inicializar variable
        system_readiness_manager = None  # Inicializar variable
        
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Error de autenticación: {str(e)}",
        })
        await websocket.close(code=1008)
        return
    
    # El usuario ya está validado arriba, continuar con la lógica del WebSocket

    # 🔧 NUEVO: Definir funciones auxiliares ANTES de usarlas
    async def prepare_user_environment_proactively(websocket, user_id, factory, priority_resources):
        """Prepara entorno del usuario ANTES del primer mensaje"""
        
        try:
            # Obtener recursos prioritarios desde headers
            resource_service = factory.get_resource_selection_service()
            if not resource_service:
                logger.warning(f"[ChatWS] ⚠️ ResourceSelectionService no disponible para usuario {user_id}")
                return {"db_ids": [], "app_ids": []}
            
            # Verificar si hay recursos para preparar
            if resource_service.has_resources_to_prepare(priority_resources):
                resources_summary = resource_service.get_resources_summary(priority_resources)
                
                await websocket.send_json({
                    "type": "environment.preparing_proactively",
                    "message": f"🚀 Preparando tu entorno en background ({resources_summary})...",
                    "resources": priority_resources,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Iniciar preparación en background
                env_orchestrator = factory.get_environment_preparation_orchestrator()
                if env_orchestrator:
                    asyncio.create_task(
                        prepare_environment_background(user_id, priority_resources, websocket, env_orchestrator)
                    )
                    logger.info(f"[ChatWS] 🚀 Preparación proactiva iniciada para usuario {user_id} con {resources_summary}")
                else:
                    logger.warning(f"[ChatWS] ⚠️ EnvironmentPreparationOrchestrator no disponible para usuario {user_id}")
            else:
                # No hay recursos para preparar
                await websocket.send_json({
                    "type": "environment.no_resources",
                    "message": "ℹ️ No hay recursos específicos para preparar",
                    "timestamp": datetime.now().isoformat()
                })
            
            return priority_resources
            
        except Exception as e:
            logger.error(f"[ChatWS] ❌ Error en preparación proactiva para usuario {user_id}: {e}")
            await websocket.send_json({
                "type": "environment.preparation_error",
                "message": "⚠️ Error preparando entorno",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return {"db_ids": [], "app_ids": []}

    async def prepare_environment_background(user_id: str, resources: Dict, websocket, env_orchestrator):
        """Prepara entorno en background y envía notificaciones"""
        
        try:
            # 1. Iniciar preparación
            prep_result = await env_orchestrator.prepare_user_environment(
                user_id=user_id,
                db_uuid=resources.get("db_ids", [None])[0] if resources.get("db_ids") else None,
                app_id=resources.get("app_ids", [None])[0] if resources.get("app_ids") else None
                # 🔧 STRATEGIES: Eliminados completamente (no se usan)
            )
            
            if prep_result.get("success"):
                # 2. Esperar que esté listo
                ready_result = await env_orchestrator.wait_for_environment_ready(
                    user_id=user_id,
                    db_uuid=resources.get("db_ids", [None])[0] if resources.get("db_ids") else None,
                    app_id=resources.get("app_ids", [None])[0] if resources.get("app_ids") else None
                    # 🔧 STRATEGIES: Eliminados completamente (no se usan)
                )
                
                if ready_result.get("ready"):
                    await websocket.send_json({
                        "type": "environment.ready_proactive",
                        "message": "✅ Tu entorno está listo para usar",
                        "resources": resources,
                        "elapsed_seconds": ready_result.get("elapsed_seconds", 0),
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.info(f"[ChatWS] ✅ Entorno preparado proactivamente para usuario {user_id}")
                else:
                    await websocket.send_json({
                        "type": "environment.preparation_timeout",
                        "message": "⏰ Preparación del entorno tardó más de lo esperado",
                        "resources": resources,
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                await websocket.send_json({
                    "type": "environment.preparation_failed",
                    "message": "❌ Error preparando entorno",
                    "error": prep_result.get("error", "Error desconocido"),
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"[ChatWS] ❌ Error en preparación background para usuario {user_id}: {e}")
            await websocket.send_json({
                "type": "environment.preparation_error",
                "message": "❌ Error crítico preparando entorno",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

    # 🔧 PREPARAR FACTORY PARA ORCHESTRATOR (requiere todas las fases)
    try:
        await factory.prepare_for_orchestrator()
        logger.info(f"[ChatWS] ✅ Factory preparado para orquestador")
    except Exception as e:
        logger.error(f"[ChatWS] ❌ Error preparando factory para orquestador: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "❌ Error preparando servicios del sistema",
        })
        await websocket.close(code=1011)
        return

    # 🔧 AHORA INICIALIZAR SERVICIOS DE READINESS (después de preparar el factory)
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
        
        # 🔧 NUEVO: Preparación proactiva del entorno desde headers
        try:
            # 🔧 OPTIMIZADO: Solo extraer DBs y Apps (requieren preparación)
            priority_resources = {
                "db_ids": websocket.headers.get("X-User-Priority-DBs", "").split(",") if websocket.headers.get("X-User-Priority-DBs") else [],
                "app_ids": websocket.headers.get("X-User-Priority-Apps", "").split(",") if websocket.headers.get("X-User-Priority-Apps") else []
                # 🔧 STRATEGIES: Eliminados completamente (no se usan)
            }
            
            # Filtrar valores vacíos y limitar a máximo 2 de cada tipo
            priority_resources["db_ids"] = [db.strip() for db in priority_resources["db_ids"] if db.strip()][:2]
            priority_resources["app_ids"] = [app.strip() for app in priority_resources["app_ids"] if app.strip()][:2]
            
            # Iniciar preparación proactiva si hay recursos
            if any(len(resource_list) > 0 for resource_list in priority_resources.values()):
                logger.info(f"[ChatWS] 🚀 Iniciando preparación proactiva con recursos: {priority_resources}")
                await prepare_user_environment_proactively(websocket, str(real_user.id), factory, priority_resources)
            else:
                logger.info(f"[ChatWS] ℹ️ No hay recursos prioritarios en headers para preparación proactiva")
                
        except Exception as proactive_error:
            logger.warning(f"[ChatWS] ⚠️ Error en preparación proactiva: {proactive_error}")
            await websocket.send_json({
                "type": "environment.warning",
                "message": "⚠️ Advertencia: No se pudo iniciar preparación proactiva del entorno",
                "timestamp": datetime.now().isoformat()
            })
        
    except Exception as readiness_error:
        logger.warning(f"[ChatWS] ⚠️ Error inicializando servicios de readiness: {readiness_error}")
        await websocket.send_json({
            "type": "system.warning",
            "message": "⚠️ Advertencia: No se pudo verificar el estado del sistema",
            "timestamp": datetime.now().isoformat()
        })

    orchestrator = factory.get_orchestrator_service()
    chat_service = factory.get_chat_service()
    
    # 🔧 FASE 4: Verificar readiness del entorno DESPUÉS de recibir el primer mensaje
    # para poder usar los recursos específicos que envía el usuario
    
    # Variable para trackear si ya se verificó el entorno
    environment_verified = False

    # 🔧 FUNCIONES YA DEFINIDAS ARRIBA (eliminadas duplicadas)

    # 🔧 NUEVO: Función para verificar entorno con recursos específicos del usuario
    async def verify_environment_with_user_resources(db_ids, app_ids):
        """Verifica el entorno usando los recursos específicos del usuario"""
        try:
            # Configurar recursos del usuario basados en el mensaje
            user_resources = {
                "db_uuid": db_ids[0] if db_ids else None,
                "app_id": app_ids[0] if app_ids else None
                # 🔧 STRATEGIES: Eliminados completamente (no se usan)
            }
            
            logger.info(f"[ChatWS] 🔍 Verificando entorno con recursos del usuario: DB={db_ids}, App={app_ids}")
            
            # Verificar readiness del entorno
            env_status = await env_prep_orchestrator.get_environment_status(
                user_id=str(real_user.id),
                **user_resources
            )
            
            # Enviar estado del entorno
            await websocket.send_json({
                "type": "environment.status",
                "data": env_status,
                "message": f"🔍 Verificando recursos del entorno (DB: {db_ids}, App: {app_ids})...",
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
                    # 🔧 CORRECCIÓN: Verificar si realmente hay recursos que preparar
                    preparing_resources = prep_result.get("preparing_resources", [])
                    
                    if not preparing_resources:
                        # No hay recursos que preparar = entorno listo inmediatamente
                        await websocket.send_json({
                            "type": "environment.ready",
                            "data": prep_result,
                            "message": "✅ Entorno listo",
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"[ChatWS] ✅ Entorno listo inmediatamente para usuario {real_user.id}")
                    else:
                        # Hay recursos que preparar = iniciar preparación
                        await websocket.send_json({
                            "type": "environment.preparation_started",
                            "data": prep_result,
                            "message": f"🚀 Preparación iniciada para {len(preparing_resources)} recursos",
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Iniciar monitoreo de readiness en background
                        asyncio.create_task(env_prep_orchestrator.wait_for_environment_ready(
                            user_id=str(real_user.id),
                            **user_resources
                        ))
                        
                        logger.info(f"[ChatWS] ✅ Preparación iniciada para {len(preparing_resources)} recursos")
                else:
                    # 🔧 MEJORAR: Proporcionar información específica sobre el error
                    error_message = prep_result.get("error", "Error desconocido")
                error_details = prep_result.get("details", {})
                
                # Detectar si es un problema de esquema corrupto
                if "esquema incompleto" in error_message.lower() or "requiere recreación" in error_message.lower():
                    await websocket.send_json({
                        "type": "environment.corrupted_database",
                        "data": prep_result,
                        "message": "⚠️ Base de datos corrupta detectada",
                        "details": {
                            "problem": "La base de datos tiene un esquema incompleto o corrupto",
                            "solution": "Borrar y recrear la base de datos desde el endpoint",
                            "reason": "Esta DB se creó antes de implementar el sistema de esquemas en Redis"
                        },
                        "timestamp": datetime.now().isoformat()
                    })
                    logger.warning(f"[ChatWS] ⚠️ DB corrupta detectada para usuario {real_user.id}: {error_message}")
                else:
                    await websocket.send_json({
                        "type": "environment.preparation_failed",
                        "data": prep_result,
                        "message": f"❌ Error iniciando preparación del entorno: {error_message}",
                        "timestamp": datetime.now().isoformat()
                    })
            
            logger.info(f"[ChatWS] 🔍 Estado del entorno verificado para usuario {real_user.id}")
            return env_status
            
        except Exception as env_error:
            logger.warning(f"[ChatWS] ⚠️ Error verificando readiness del entorno: {env_error}")
            await websocket.send_json({
                "type": "environment.warning",
                "message": "⚠️ Advertencia: No se pudo verificar el estado del entorno",
                "timestamp": datetime.now().isoformat()
            })
            return {"environment_ready": False, "error": str(env_error)}

    # 🔧 FUNCIONES YA DEFINIDAS ARRIBA (eliminadas duplicadas)

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

            # 🔧 NUEVO: Verificar si es el primer mensaje y el entorno ya está preparado proactivamente
            if not environment_verified:
                # Es el primer mensaje
                logger.info(f"[ChatWS] 🔍 Primer mensaje recibido del usuario")
                
                # Verificar si el entorno ya está listo (preparación proactiva)
                if env_prep_orchestrator is not None:
                    # Intentar obtener estado del entorno preparado proactivamente
                    try:
                        # 🔧 OPTIMIZADO: Solo usar DBs y Apps de headers
                        header_dbs = websocket.headers.get("X-User-Priority-DBs", "").split(",") if websocket.headers.get("X-User-Priority-DBs") else []
                        header_apps = websocket.headers.get("X-User-Priority-Apps", "").split(",") if websocket.headers.get("X-User-Priority-Apps") else []
                        
                        # Filtrar valores vacíos
                        header_dbs = [db.strip() for db in header_dbs if db.strip()]
                        header_apps = [app.strip() for app in header_apps if app.strip()]
                        
                        if header_dbs or header_apps:
                            # Verificar estado del entorno preparado proactivamente
                            env_status = await env_prep_orchestrator.get_environment_status(
                                user_id=str(real_user.id),
                                db_uuid=header_dbs[0] if header_dbs else None,
                                app_id=header_apps[0] if header_apps else None
                                # 🔧 STRATEGIES: Eliminados completamente (no se usan)
                            )
                            
                            if env_status.get("environment_ready", False):
                                await websocket.send_json({
                                    "type": "environment.ready_proactive",
                                    "message": "✅ Tu entorno ya está listo (preparado proactivamente)",
                                    "resources": {
                                        "db_ids": header_dbs,
                                        "app_ids": header_apps
                                        # 🔧 STRATEGIES: No se incluyen (no se preparan proactivamente)
                                    },
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"[ChatWS] ✅ Entorno ya preparado proactivamente para usuario {real_user.id}")
                            else:
                                await websocket.send_json({
                                    "type": "environment.preparing",
                                    "message": "⏳ Entorno aún en preparación...",
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"[ChatWS] ⏳ Entorno aún en preparación para usuario {real_user.id}")
                        else:
                            # No hay recursos en headers, enviar mensaje informativo
                            await websocket.send_json({
                                "type": "environment.info",
                                "message": "ℹ️ No hay recursos específicos configurados",
                                "timestamp": datetime.now().isoformat()
                            })
                            logger.info(f"[ChatWS] ℹ️ No hay recursos específicos para usuario {real_user.id}")
                            
                    except Exception as env_check_error:
                        logger.warning(f"[ChatWS] ⚠️ Error verificando estado del entorno preparado: {env_check_error}")
                        await websocket.send_json({
                            "type": "environment.warning",
                            "message": "⚠️ No se pudo verificar el estado del entorno",
                            "timestamp": datetime.now().isoformat()
                        })
                
                environment_verified = True
                logger.info(f"[ChatWS] ✅ Primer mensaje procesado para usuario {real_user.id}")

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
                    if system_readiness_manager is not None:
                        system_status = await system_readiness_manager.get_system_status()
                    else:
                        system_status = {"system_status": "error", "message": "SystemReadinessManager no disponible"}
                    
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
                     # 🔧 FIX: Definir user_resources basado en headers
                     header_dbs = websocket.headers.get("X-User-Priority-DBs", "").split(",") if websocket.headers.get("X-User-Priority-DBs") else []
                     header_apps = websocket.headers.get("X-User-Priority-Apps", "").split(",") if websocket.headers.get("X-User-Priority-Apps") else []
                     
                     # Filtrar valores vacíos
                     header_dbs = [db.strip() for db in header_dbs if db.strip()]
                     header_apps = [app.strip() for app in header_apps if app.strip()]
                     
                     user_resources = {
                         "db_uuid": header_dbs[0] if header_dbs else None,
                         "app_id": header_apps[0] if header_apps else None
                     }
                     
                     # Obtener estado actual del entorno
                     if env_prep_orchestrator is not None:
                         env_status = await env_prep_orchestrator.get_environment_status(
                             user_id=str(real_user.id),
                             **user_resources
                         )
                     else:
                         env_status = {"environment_ready": False, "message": "Orchestrator no disponible"}
                     
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
                                        message=guided_message,
                                        chat_id=chat_id,
                                        user_id=str(real_user.id)
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

            # 🔧 NUEVO: Los recursos ahora vienen de los headers, no del mensaje
            # Parámetros opcionales (mantenidos para compatibilidad)
            explorer: bool = data.get("explorer", False)

            try:
                response = await orchestrator.handle_user_message(
                    message=msg.content,
                    chat_id=chat_id,
                    user_id=str(real_user.id)
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
        logger.info(f"❌ WebSocket disconnected - user_id={real_user.id}")
        
        # 🔧 FASE 5: Limpiar conexión y suscripciones
        try:
            ws_emitter.unregister_connection(str(real_user.id), websocket)
            notification_service.unsubscribe_user(real_user.id)
            logger.info(f"[ChatWS] 🧹 Conexión WebSocket y suscripciones limpiadas para usuario {real_user.id}")
        except Exception as cleanup_error:
            logger.warning(f"[ChatWS] ⚠️ Error limpiando conexión: {cleanup_error}")
            
    except Exception as e:
        logger.error(f"❌ Internal WebSocket error - user_id={real_user.id} - {str(e)}")
        
        # 🔧 FASE 5: Limpiar conexión en caso de error
        try:
            ws_emitter.unregister_connection(str(real_user.id), websocket)
            notification_service.unsubscribe_user(real_user.id)
        except Exception as cleanup_error:
            logger.warning(f"[ChatWS] ⚠️ Error limpiando conexión en error: {cleanup_error}")
            
        await websocket.send_json({
            "type": "error",
            "message": f"❌ Internal server error: {str(e)}",
        })
        await websocket.close(code=1011)
