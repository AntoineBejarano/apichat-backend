"""
UnifiedChatService - Chat unificado con triggering automático
────────────────────────────────────────────────────────────
Servicio de chat que integra:
- Chat tradicional con bases de datos
- Triggering automático de APIs
- Búsqueda vectorial unificada
- Configuración personalizada por usuario
"""

import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from app.services.ai.api_triggering_service import APITriggeringService
from app.services.context.unified_vector_search_service import (
    UnifiedVectorSearchService,
    SearchContext
)
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Respuesta unificada del chat"""
    success: bool
    message: str
    response_type: str  # "database", "api", "mixed", "error"
    data: Any
    execution_results: Optional[List[Dict[str, Any]]] = None
    suggestions: Optional[List[str]] = None
    requires_confirmation: bool = False


class UnifiedChatService:
    """
    Servicio de chat unificado que combina chat tradicional con triggering automático.
    Detecta automáticamente si el usuario quiere trabajar con DB o APIs.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        
        # Servicios especializados
        self.api_triggering_service = APITriggeringService(factory)
        self.unified_search_service = UnifiedVectorSearchService(factory)
        self.orchestrator_service = OrchestratorService(factory)
        
        self.logger.info("[UnifiedChatService] 🚀 Inicializado con chat unificado")
    
    async def process_chat_message(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID] = None,
        app_id: Optional[UUID] = None,
        db_id: Optional[UUID] = None,
        auto_execute_apis: bool = False
    ) -> ChatResponse:
        """
        Procesar mensaje de chat con detección automática de intención.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            chat_id: ID del chat (opcional)
            app_id: ID de la app (opcional)
            db_id: ID de la base de datos (opcional)
            auto_execute_apis: Si ejecutar APIs automáticamente
            
        Returns:
            Respuesta unificada del chat
        """
        try:
            self.logger.info(f"[UnifiedChatService] 💬 Procesando mensaje: '{message[:50]}...' para user_id={user_id}")
            
            # 1. Detectar intención del mensaje
            intent = await self._detect_message_intent(message, user_id, app_id, db_id)
            
            self.logger.info(f"[UnifiedChatService] 🎯 Intención detectada: {intent['type']} (confianza: {intent['confidence']:.2f})")
            
            # 2. Procesar según la intención detectada
            if intent['type'] == 'api_call':
                return await self._handle_api_intent(message, user_id, app_id, db_id, auto_execute_apis)
            elif intent['type'] == 'database_query':
                return await self._handle_database_intent(message, user_id, chat_id, db_id)
            elif intent['type'] == 'mixed':
                return await self._handle_mixed_intent(message, user_id, chat_id, app_id, db_id, auto_execute_apis)
            else:
                return await self._handle_general_intent(message, user_id, chat_id, app_id, db_id)
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error procesando mensaje: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando mensaje: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _detect_message_intent(
        self,
        message: str,
        user_id: UUID,
        app_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Detectar intención del mensaje usando búsqueda vectorial"""
        try:
            # Crear contexto de búsqueda
            search_context = SearchContext(
                user_id=user_id,
                app_id=app_id,
                db_id=db_id,
                search_types=["database", "api"],
                confidence_threshold=0.5,
                max_results_per_type=3
            )
            
            # Búsqueda unificada
            search_results = await self.unified_search_service.unified_search(message, search_context)
            
            # Analizar resultados
            db_results = [r for r in search_results if r.resource_type == "database"]
            api_results = [r for r in search_results if r.resource_type == "api"]
            
            # Determinar intención basada en resultados
            if api_results and not db_results:
                return {
                    "type": "api_call",
                    "confidence": max([r.similarity_score for r in api_results]),
                    "api_results": api_results
                }
            elif db_results and not api_results:
                return {
                    "type": "database_query",
                    "confidence": max([r.similarity_score for r in db_results]),
                    "db_results": db_results
                }
            elif api_results and db_results:
                return {
                    "type": "mixed",
                    "confidence": max([r.similarity_score for r in api_results + db_results]),
                    "api_results": api_results,
                    "db_results": db_results
                }
            else:
                return {
                    "type": "general",
                    "confidence": 0.3,
                    "message": "No se detectó intención específica"
                }
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error detectando intención: {e}")
            return {
                "type": "general",
                "confidence": 0.1,
                "error": str(e)
            }
    
    async def _handle_api_intent(
        self,
        message: str,
        user_id: UUID,
        app_id: Optional[UUID],
        db_id: Optional[UUID],
        auto_execute: bool
    ) -> ChatResponse:
        """Manejar intención de llamada a API"""
        try:
            # Procesar triggering de API
            triggering_result = await self.api_triggering_service.process_triggering_request(
                query=message,
                user_id=user_id,
                app_id=app_id,
                db_id=db_id,
                auto_execute=auto_execute
            )
            
            if triggering_result.get("success"):
                if triggering_result.get("requires_confirmation"):
                    return ChatResponse(
                        success=True,
                        message="Encontradas funciones relevantes. ¿Deseas ejecutarlas?",
                        response_type="api",
                        data=triggering_result,
                        requires_confirmation=True
                    )
                else:
                    return ChatResponse(
                        success=True,
                        message="Funciones ejecutadas automáticamente",
                        response_type="api",
                        data=triggering_result,
                        execution_results=triggering_result.get("execution_results", [])
                    )
            else:
                return ChatResponse(
                    success=False,
                    message=triggering_result.get("message", "No se encontraron funciones relevantes"),
                    response_type="api",
                    data=triggering_result,
                    suggestions=triggering_result.get("suggestions", [])
                )
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error manejando intención de API: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando solicitud de API: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_database_intent(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> ChatResponse:
        """Manejar intención de consulta a base de datos"""
        try:
            # Usar el orchestrator existente para consultas de DB
            from app.schemas.chat_schema import ChatMessage
            
            chat_message = ChatMessage(content=message)
            
            # Crear chat si no existe
            if not chat_id:
                chat_service = self.factory.get_chat_service()
                new_chat = chat_service.create_chat()
                chat_id = new_chat.id
            
            # Procesar con orchestrator
            orchestrator_response = await self.orchestrator_service.handle_user_message(
                chat_id=chat_id,
                db_ids=[db_id] if db_id else [],
                app_ids=[],
                explorer=False,
                agent_id=None,
                message=chat_message
            )
            
            return ChatResponse(
                success=True,
                message="Consulta de base de datos procesada",
                response_type="database",
                data=orchestrator_response,
                execution_results=orchestrator_response.get("execution_results", [])
            )
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error manejando intención de DB: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando consulta de base de datos: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_mixed_intent(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID],
        app_id: Optional[UUID],
        db_id: Optional[UUID],
        auto_execute: bool
    ) -> ChatResponse:
        """Manejar intención mixta (DB + API)"""
        try:
            # Procesar ambas intenciones
            api_response = await self._handle_api_intent(message, user_id, app_id, db_id, auto_execute)
            db_response = await self._handle_database_intent(message, user_id, chat_id, db_id)
            
            # Combinar resultados
            combined_data = {
                "api_result": api_response.data,
                "database_result": db_response.data,
                "api_success": api_response.success,
                "database_success": db_response.success
            }
            
            combined_message = "Procesamiento mixto completado"
            if api_response.success and db_response.success:
                combined_message = "Consultas de base de datos y APIs ejecutadas exitosamente"
            elif api_response.success:
                combined_message = "APIs ejecutadas, consulta de DB falló"
            elif db_response.success:
                combined_message = "Consulta de DB ejecutada, APIs fallaron"
            else:
                combined_message = "Ambas operaciones fallaron"
            
            return ChatResponse(
                success=api_response.success or db_response.success,
                message=combined_message,
                response_type="mixed",
                data=combined_data,
                execution_results=(
                    (api_response.execution_results or []) + 
                    (db_response.execution_results or [])
                ),
                requires_confirmation=api_response.requires_confirmation
            )
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error manejando intención mixta: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando solicitud mixta: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_general_intent(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID],
        app_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> ChatResponse:
        """Manejar intención general o no específica"""
        try:
            # Usar el orchestrator para procesamiento general
            from app.schemas.chat_schema import ChatMessage
            
            chat_message = ChatMessage(content=message)
            
            # Crear chat si no existe
            if not chat_id:
                chat_service = self.factory.get_chat_service()
                new_chat = chat_service.create_chat()
                chat_id = new_chat.id
            
            # Procesar con orchestrator
            orchestrator_response = await self.orchestrator_service.handle_user_message(
                chat_id=chat_id,
                db_ids=[db_id] if db_id else [],
                app_ids=[app_id] if app_id else [],
                explorer=False,
                agent_id=None,
                message=chat_message
            )
            
            return ChatResponse(
                success=True,
                message="Mensaje procesado",
                response_type="general",
                data=orchestrator_response,
                execution_results=orchestrator_response.get("execution_results", [])
            )
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error manejando intención general: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando mensaje: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def confirm_api_execution(
        self,
        plan_data: Dict[str, Any],
        user_id: UUID
    ) -> ChatResponse:
        """Confirmar ejecución de plan de API"""
        try:
            # Ejecutar plan confirmado
            from app.services.ai.api_triggering_service import TriggeringPlan
            
            plan = TriggeringPlan(
                function_id=UUID(plan_data["function_id"]),
                function_name=plan_data["function_name"],
                endpoint=plan_data["endpoint"],
                method=plan_data["method"],
                parameters=plan_data["parameters"],
                confidence=plan_data["confidence"],
                requires_confirmation=plan_data["requires_confirmation"],
                estimated_execution_time=plan_data["estimated_execution_time"]
            )
            
            result = await self.api_triggering_service.execute_confirmed_plan(plan, user_id)
            
            return ChatResponse(
                success=result.success,
                message=f"Función {result.function_name} {'ejecutada' if result.success else 'falló'}",
                response_type="api",
                data={
                    "function_name": result.function_name,
                    "endpoint": result.endpoint,
                    "result": result.result,
                    "execution_time": result.execution_time,
                    "error": result.error
                },
                execution_results=[{
                    "function_name": result.function_name,
                    "success": result.success,
                    "result": result.result,
                    "error": result.error
                }]
            )
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error confirmando ejecución: {e}")
            return ChatResponse(
                success=False,
                message=f"Error ejecutando función: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def get_chat_suggestions(
        self,
        partial_message: str,
        user_id: UUID,
        app_id: Optional[UUID] = None,
        db_id: Optional[UUID] = None
    ) -> List[str]:
        """Obtener sugerencias de chat basadas en el contexto"""
        try:
            search_context = SearchContext(
                user_id=user_id,
                app_id=app_id,
                db_id=db_id,
                search_types=["database", "api"],
                confidence_threshold=0.3,
                max_results_per_type=3
            )
            
            suggestions = await self.unified_search_service.get_search_suggestions(
                partial_message, search_context, max_suggestions=5
            )
            
            return suggestions
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error obteniendo sugerencias: {e}")
            return []
    
    async def get_chat_analytics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtener analytics del chat unificado"""
        try:
            # Analytics de triggering
            triggering_analytics = await self.api_triggering_service.get_triggering_analytics(user_id)
            
            # Analytics de búsqueda
            search_analytics = await self.unified_search_service.get_search_analytics()
            
            return {
                "triggering_analytics": triggering_analytics,
                "search_analytics": search_analytics,
                "total_requests": triggering_analytics.get("total_requests", 0),
                "success_rate": (
                    triggering_analytics.get("successful_executions", 0) /
                    max(triggering_analytics.get("total_requests", 1), 1)
                ) * 100
            }
            
        except Exception as e:
            self.logger.error(f"[UnifiedChatService] ❌ Error obteniendo analytics: {e}")
            return {}
