#!/usr/bin/env python3
"""
🚀 GuidedService - Servicio para ejecutar grafos guiados
────────────────────────────────────────────────────────
Implementación real del servicio de grafos guiados que usa GuidedGraph.
"""
import logging
from typing import Dict, Any, Optional
from uuid import UUID

from app.core.service_factory import ServiceFactory
from app.services.execution.graphs.guided_graph import GuidedGraph, GuidedState
from app.schemas.chat_schema import ChatMessage

logger = logging.getLogger(__name__)


class GuidedService:
    """
    🚀 Servicio real para ejecutar grafos guiados.
    
    Este servicio reemplaza el stub temporal en StrategyService
    y proporciona funcionalidad completa usando GuidedGraph.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.guided_graph = GuidedGraph(factory)
    
    async def run_guided_graph(
        self,
        chat_id: UUID,
        user_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🚀 Ejecuta un grafo guiado completo usando GuidedGraph.
        
        Args:
            chat_id: ID del chat
            user_message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado completo del grafo guiado
        """
        logger.info(f"[GuidedService] 🚀 Iniciando grafo guiado para chat_id={chat_id}")
        
        try:
            # Crear mensaje del chat
            message = ChatMessage(
                role="user",
                content=user_message,
                chat_id=str(chat_id)
            )
            
            # Preparar estado inicial para GuidedGraph
            initial_state: GuidedState = {
                "chat_id": str(chat_id),
                "message": message,
                "db_ids": context.get('db_ids'),
                "app_ids": context.get('app_ids'),
                "compact_schemas": context.get('compact_schemas'),
                "cache_status": context.get('cache_status'),
                "app_descriptors": context.get('app_descriptors'),
                "functions": context.get('functions'),
                "available_mcp_tools": context.get('available_mcp_tools'),
                "history": context.get('history'),
                "db_dialect": context.get('db_dialect')
            }
            
            # Ejecutar el grafo guiado
            logger.info(f"[GuidedService] 🔄 Ejecutando GuidedGraph para: '{user_message[:50]}...'")
            final_state = await self.guided_graph.run(initial_state)
            
            # Procesar resultado
            if final_state.get("error"):
                logger.error(f"[GuidedService] ❌ Error en grafo guiado: {final_state['error']}")
                return {
                    "content": f"❌ Error ejecutando grafo guiado: {final_state['error']}",
                    "chat_id": str(chat_id),
                    "mode": "guided",
                    "status": "error",
                    "error": final_state["error"]
                }
            
            # Extraer respuesta del asistente
            assistant_response = final_state.get("assistant_response", "No se generó respuesta")
            plan = final_state.get("plan")
            
            # Construir respuesta
            response = {
                "content": assistant_response,
                "chat_id": str(chat_id),
                "mode": "guided",
                "status": "completed",
                "fallback": False,  # No es fallback, es implementación real
                "message": "Grafo guiado ejecutado exitosamente"
            }
            
            # Agregar información del plan si está disponible
            if plan:
                response["plan"] = {
                    "id": str(plan.id) if hasattr(plan, 'id') else None,
                    "name": plan.name if hasattr(plan, 'name') else None,
                    "description": plan.description if hasattr(plan, 'description') else None,
                    "steps_count": len(plan.steps) if hasattr(plan, 'steps') else 0
                }
            
            # Agregar información del contexto procesado
            response["context_summary"] = {
                "has_databases": bool(final_state.get('db_ids')),
                "has_apps": bool(final_state.get('app_ids')),
                "intent": final_state.get('intent', {}).value if final_state.get('intent') else None,
                "intent_confidence": final_state.get('intent_confidence'),
                "requires_resources": final_state.get('requires_resources'),
                "cache_hits": final_state.get('cache_hits', 0),
                "cache_misses": final_state.get('cache_misses', 0),
                "processing_time": final_state.get('processing_time')
            }
            
            logger.info(f"[GuidedService] ✅ Grafo guiado completado exitosamente para chat_id={chat_id}")
            return response
            
        except Exception as e:
            logger.error(f"[GuidedService] ❌ Error inesperado en run_guided_graph: {e}")
            return {
                "content": f"❌ Error inesperado ejecutando grafo guiado: {str(e)}",
                "error": str(e),
                "chat_id": str(chat_id),
                "mode": "guided",
                "status": "error",
                "fallback": False
            }
    
    async def get_guided_graph_status(self) -> Dict[str, Any]:
        """
        📊 Obtiene el estado del servicio de grafos guiados.
        
        Returns:
            Estado del servicio
        """
        return {
            "service": "GuidedService",
            "status": "active",
            "implementation": "real",
            "guided_graph_available": True,
            "message": "Servicio de grafos guiados completamente implementado"
        }
