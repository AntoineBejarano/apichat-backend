# app/routers/chat_router.py
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import time
import logging

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage, ChatCreate, ChatOut
from app.schemas.chat_history_schema import ChatHistoryOut
from app.schemas.chat_ask_schema import ChatAskRequest, ChatAskResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["💬 Chat IA"],
    responses={404: {"description": "No encontrado"}},
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.post(
    "/",
    response_model=ChatOut,
    summary="🧠 Crear nuevo chat",
    description="Crea una nueva sesión de chat del usuario con IA.",
)
def create_chat(chat: ChatCreate, factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_service().create_chat(chat)

@router.get(
    "/",
    response_model=List[ChatOut],
    summary="📚 Listar chats del usuario",
    description="Devuelve todos los chats del usuario autenticado.",
)
def list_user_chats(factory: ServiceFactory = Depends(get_factory)):
    return factory.get_chat_service().get_all()

@router.get(
    "/{chat_id}",
    response_model=ChatOut,
    summary="📖 Obtener chat específico",
    description="Obtiene un chat específico del usuario autenticado.",
)
def get_chat(chat_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    chat = factory.get_chat_service().get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return chat

@router.delete(
    "/{chat_id}",
    summary="🗑️ Eliminar chat",
    description="Elimina un chat específico del usuario autenticado.",
)
def delete_chat(chat_id: UUID, factory: ServiceFactory = Depends(get_factory)):
    success = factory.get_chat_service().delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat no encontrado")
    return {"message": "Chat eliminado exitosamente"}

@router.post(
    "/send",
    summary="✉️ Enviar mensaje a IA",
    description="Envía un mensaje a la IA y obtiene la respuesta. Parámetros opcionales para contexto.",
)
async def send_message(
    message: ChatMessage,
    chat_id: Optional[UUID] = None,
    agent_id: Optional[UUID] = None,
    db_ids: Optional[List[UUID]] = None,
    app_ids: Optional[List[UUID]] = None,
    explorer: bool = False,
    iterative_rag: bool = False,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Envía un mensaje a la IA y obtiene la respuesta.
    
    Parámetros:
    - message: El mensaje del usuario
    - chat_id: ID del chat (opcional, se crea uno nuevo si no se proporciona)
    - agent_id: ID del agente (opcional)
    - db_ids: Lista de IDs de bases de datos para contexto (opcional)
    - app_ids: Lista de IDs de aplicaciones para contexto (opcional)
    - explorer: Modo explorador (opcional, default: False)
    - iterative_rag: Usar flujo RAG iterativo (opcional, default: False)
    """
    try:
        # Si no se proporciona chat_id, usar el chat más reciente o crear uno nuevo
        if not chat_id:
            chat_service = factory.get_chat_service()
            chats = chat_service.get_all(limit=1)
            if chats:
                chat_id = chats[0].id
            else:
                new_chat = chat_service.create_chat(ChatCreate(name="Auto Chat"))
                chat_id = new_chat.id

        # Decidir qué flujo usar
        orchestrator_service = factory.get_orchestrator_service()
        
        if iterative_rag:

            # Usar el nuevo flujo RAG iterativo
            response = await orchestrator_service.run_iterative_rag(
                chat_id=chat_id,
                message=message,
                db_ids=db_ids or [],
                app_ids=app_ids or [],
                explorer=explorer,
                max_iterations=3
            )
        else:
            # Usar el flujo tradicional
            response = await orchestrator_service.handle_user_message(
                chat_id=chat_id,
                db_ids=db_ids or [],
                app_ids=app_ids or [],
                explorer=explorer,
                agent_id=agent_id,
                message=message,
            )

        # Preparar respuesta
        result = {
            "success": True,
            "chat_id": chat_id,
            "assistant_response": response.get("assistant_response", "🤖 No response generated"),
            "execution_results": response.get("execution_results", {}),
            "steps": response.get("steps", []),
        }
        
        # Agregar información específica del flujo iterativo si se usó
        if iterative_rag:
            result["iterative_rag"] = True
            result["iterations_used"] = response.get("iterations_used", 0)
        
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )

@router.post(
    "/{chat_id}/message",
    summary="✉️ Enviar mensaje a chat específico",
    description="Envía un mensaje a la IA dentro de un chat específico.",
)
async def send_message_to_chat(
    chat_id: UUID,
    message: ChatMessage,
    agent_id: Optional[UUID] = None,
    db_ids: Optional[List[UUID]] = None,
    app_ids: Optional[List[UUID]] = None,
    explorer: bool = False,
    factory: ServiceFactory = Depends(get_factory),
):
    """
    Envía un mensaje a la IA dentro de un chat específico.
    
    Parámetros:
    - chat_id: ID del chat
    - message: El mensaje del usuario
    - agent_id: ID del agente (opcional)
    - db_ids: Lista de IDs de bases de datos para contexto (opcional)
    - app_ids: Lista de IDs de aplicaciones para contexto (opcional)
    - explorer: Modo explorador (opcional, default: False)
    """
    try:
        # Llamar al orchestrator con los mismos parámetros que el WebSocket
        response = await factory.get_orchestrator_service().handle_user_message(
            chat_id=chat_id,
            db_ids=db_ids or [],
            app_ids=app_ids or [],
            explorer=explorer,
            agent_id=agent_id,
            message=message,
        )

        return {
            "success": True,
            "chat_id": chat_id,
            "assistant_response": response.get("assistant_response", "🤖 No response generated"),
            "execution_results": response.get("execution_results", {}),
            "steps": response.get("steps", []),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"❌ Error procesando mensaje: {str(e)}"
        )

@router.post(
    "/ask",
    summary="🧠 Chat inteligente con grounding → plan → SQL → validación → ejecución",
    description="Nuevo endpoint que implementa el flujo completo de la Fase 5: intención → grounding → plan → SQL → validación → ejecución",
)
async def chat_ask(
    request: ChatAskRequest,
    factory: ServiceFactory = Depends(get_factory_full),  # 🔧 Necesita todas las fases
):
    """
    🧠 Chat inteligente con flujo completo de la Fase 5:
    
    1. **Resolución de contexto**: snapshot_id activo del dbId seleccionado
    2. **Intent Router**: structured vs diffuse
    3. **Grounding**: embeddings top-k o lookup directo en catálogo
    4. **Plan**: tablas base, joins permitidos, filtros, proyecciones
    5. **SQL Generation**: estricto, solo SELECT, con LIMIT y TIMEOUT
    6. **Validación**: Parser SQL + catálogo
    7. **Ejecución**: read-only, schemas permitidos
    8. **Respuesta**: resultado + explicación + SQL mostrado
    
    Args:
        request: ChatAskRequest con query, db_id, y parámetros opcionales
        
    Returns:
        Respuesta estructurada con resultado, explicación y SQL
    """
    try:
        start_time = time.time()
        logger.info(f"[ChatRouter] 🧠 Iniciando chat inteligente para DB {request.db_id}")
        
        # 🔧 FASE 5: 1. RESOLUCIÓN DE CONTEXTO
        context_resolver = factory.get_context_resolver_service()
        if not context_resolver:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de resolución de contexto no disponible"
            )
        
        # Resolver snapshot_id activo y contexto
        context = await context_resolver.resolve_context(
            user_id=factory.user.id,
            db_id=request.db_id,
            app_id=request.app_id
        )
        
        if not context.get("snapshot_ready"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schema no está listo para la DB {request.db_id}. Estado: {context.get('schema_status', 'unknown')}"
            )
        
        logger.info(f"[ChatRouter] ✅ Contexto resuelto: snapshot {context['snapshot_id']}")
        
        # 🔧 FASE 5: 2. INTENT ROUTER
        intent_router = factory.get_intent_router_service()
        if not intent_router:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de intención no disponible"
            )
        
        # Clasificar intención (structured vs diffuse)
        intent_result = await intent_router.classify_intent(
            query=request.query,
            context=context,
            user_id=factory.user.id
        )
        
        logger.info(f"[ChatRouter] 🎯 Intención clasificada: {intent_result.intent_type} (confianza: {intent_result.confidence_score:.2f})")
        
        # 🔧 FASE 5: 3. GROUNDING
        grounding_service = factory.get_grounding_service()
        if not grounding_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de grounding no disponible"
            )
        
        # Grounding basado en tipo de intención
        if intent_result.intent_type == "db_query" and intent_result.confidence_score > 0.7:
            # Structured: lookup directo en catálogo
            grounding_result = await grounding_service.structured_grounding(
                query=request.query,
                context=context,
                intent_metadata=intent_result.metadata
            )
        else:
            # Diffuse: embeddings top-k
            grounding_result = await grounding_service.diffuse_grounding(
                query=request.query,
                context=context,
                top_k=10
            )
        
        logger.info(f"[ChatRouter] 🔍 Grounding completado: {len(grounding_result.get('chunks', []))} chunks")
        
        # 🔧 FASE 5: 4. PLANIFICACIÓN CON GRAFO
        planner_service = factory.get_planner_service()
        if not planner_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de planificación no disponible"
            )
        
        # Crear plan usando el grafo de relaciones
        plan = await planner_service.create_plan(
            query=request.query,
            context=context,
            grounding_result=grounding_result,
            intent_result=intent_result
        )
        
        if plan.get("status") == "needs_clarification":
            return {
                "success": False,
                "status": "needs_clarification",
                "message": "Necesito más información para completar tu consulta",
                "clarification_questions": plan.get("clarification_questions", []),
                "missing_info": plan.get("missing_info", {}),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
        
        logger.info(f"[ChatRouter] 🧭 Plan creado: {plan.get('tables', [])} tablas, {plan.get('joins', [])} joins")
        
        # 🔧 FASE 5: 5. SQL GENERATION
        sql_generator = factory.get_sql_generator_service()
        if not sql_generator:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de generación SQL no disponible"
            )
        
        # Generar SQL estricto
        sql_result = await sql_generator.generate_sql(
            plan=plan,
            context=context,
            query=request.query
        )
        
        if sql_result.get("status") == "cannot_generate":
            return {
                "success": False,
                "status": "cannot_generate",
                "message": "No puedo generar SQL válido para tu consulta",
                "reason": sql_result.get("reason", "Consulta no compatible"),
                "suggestions": sql_result.get("suggestions", []),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
        
        generated_sql = sql_result.get("sql")
        logger.info(f"[ChatRouter] 🗃️ SQL generado: {generated_sql[:100]}...")
        
        # 🔧 FASE 5: 6. VALIDACIÓN SQL
        validator_service = factory.get_sql_validator_service()
        if not validator_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de validación SQL no disponible"
            )
        
        # Validar SQL contra catálogo
        validation_result = await validator_service.validate_sql(
            sql=generated_sql,
            context=context,
            plan=plan
        )
        
        if not validation_result.get("is_valid"):
            return {
                "success": False,
                "status": "validation_failed",
                "message": "El SQL generado no es válido",
                "errors": validation_result.get("errors", []),
                "suggestions": validation_result.get("suggestions", []),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
        
        logger.info(f"[ChatRouter] ✅ SQL validado correctamente")
        
        # 🔧 FASE 5: 7. EJECUCIÓN
        executor_service = factory.get_sql_executor_service()
        if not executor_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Servicio de ejecución SQL no disponible"
            )
        
        # Ejecutar SQL de forma segura
        execution_result = await executor_service.execute_sql(
            sql=generated_sql,
            context=context,
            timeout_seconds=30,  # 🔧 Configurable por ENV
            max_rows=1000        # 🔧 Configurable por ENV
        )
        
        if execution_result.get("status") == "error":
            return {
                "success": False,
                "status": "execution_failed",
                "message": "Error ejecutando la consulta",
                "error": execution_result.get("error"),
                "sql": generated_sql,
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
        
        logger.info(f"[ChatRouter] ✅ SQL ejecutado: {execution_result.get('row_count', 0)} filas")
        
        # 🔧 FASE 5: 8. RESPUESTA ESTRUCTURADA
        explanation_service = factory.get_explanation_service()
        explanation = ""
        if explanation_service:
            explanation = await explanation_service.explain_query(
                plan=plan,
                sql=generated_sql,
                results=execution_result,
                context=context
            )
        
        # Calcular tiempo total
        total_time_ms = int((time.time() - start_time) * 1000)
        
        # 🔧 FASE 5: Guardar en Redis para estado de sesión
        session_service = factory.get_session_service()
        if session_service:
            await session_service.save_chat_session(
                user_id=factory.user.id,
                db_id=request.db_id,
                snapshot_id=context.get("snapshot_id"),
                query=request.query,
                sql=generated_sql,
                results=execution_result
            )
        
        logger.info(f"[ChatRouter] 🎉 Chat inteligente completado en {total_time_ms}ms")
        
        return {
            "success": True,
            "status": "completed",
            "message": "Consulta procesada exitosamente",
            
            # 🔧 FASE 5: Resultado principal
            "result": {
                "data": execution_result.get("data", []),
                "row_count": execution_result.get("row_count", 0),
                "columns": execution_result.get("columns", []),
                "execution_time_ms": execution_result.get("execution_time_ms", 0)
            },
            
            # 🔧 FASE 5: Explicación y SQL
            "explanation": explanation,
            "sql": generated_sql,
            "sql_formatted": sql_result.get("sql_formatted", generated_sql),
            
            # 🔧 FASE 5: Metadatos del proceso
            "metadata": {
                "intent_type": intent_result.intent_type,
                "intent_confidence": intent_result.confidence_score,
                "grounding_method": "structured" if intent_result.intent_type == "db_query" else "diffuse",
                "chunks_used": len(grounding_result.get("chunks", [])),
                "plan_tables": plan.get("tables", []),
                "plan_joins": plan.get("joins", []),
                "validation_passed": True,
                "execution_success": True
            },
            
            # 🔧 FASE 5: Métricas de performance
            "performance": {
                "total_time_ms": total_time_ms,
                "grounding_time_ms": grounding_result.get("processing_time_ms", 0),
                "planning_time_ms": plan.get("processing_time_ms", 0),
                "sql_generation_time_ms": sql_result.get("processing_time_ms", 0),
                "validation_time_ms": validation_result.get("processing_time_ms", 0),
                "execution_time_ms": execution_result.get("execution_time_ms", 0)
            },
            
            # 🔧 FASE 5: Contexto usado
            "context": {
                "db_id": str(request.db_id),
                "snapshot_id": str(context.get("snapshot_id", "")),
                "schema_version": context.get("schema_version", ""),
                "tables_available": context.get("total_tables", 0),
                "relationships_available": context.get("total_relationships", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ChatRouter] ❌ Error en chat inteligente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

