"""
Graph Runner Module
───────────────────
Maneja la ejecución de los grafos de exploración y guía.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class GraphRunner:
    """
    Ejecuta los grafos de exploración y guía del orchestrator.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.exploration_service = factory.get_strategy_service()
        self.guided_service = factory.get_strategy_service()  # Mismo servicio, diferente modo
    
    def select_graph_runner(self, explorer: bool):
        """
        Selecciona el runner apropiado basado en el modo.
        
        Args:
            explorer: True para modo exploración, False para modo guiado
            
        Returns:
            Servicio apropiado para ejecutar el grafo
        """
        if explorer:
            logger.info("[GraphRunner] 🧭 Usando modo exploración")
            return self.exploration_service
        else:
            logger.info("[GraphRunner] 🎯 Usando modo guiado")
            return self.guided_service
    
    def normalize_graph_output(self, output: Any) -> Dict[str, Any]:
        """
        Normaliza la salida del grafo para asegurar consistencia.
        
        Args:
            output: Salida del grafo
            
        Returns:
            Salida normalizada
        """
        logger.info(f"[GraphRunner] 🔄 Normalizando salida del grafo: {type(output)}")
        
        if isinstance(output, dict):
            normalized = output.copy()
        elif hasattr(output, 'model_dump'):
            # Objeto Pydantic
            normalized = output.model_dump()
        elif hasattr(output, '__dict__'):
            # Objeto con atributos
            normalized = {}
            for key, value in output.__dict__.items():
                if not key.startswith('_'):
                    normalized[key] = value
        else:
            # Otro tipo - convertir a string
            normalized = {"content": str(output)}
        
        # Asegurar que siempre tenga un campo 'content'
        if "content" not in normalized:
            if "result" in normalized:
                normalized["content"] = normalized["result"]
            elif "output" in normalized:
                normalized["content"] = normalized["output"]
            else:
                normalized["content"] = str(normalized)
        
        logger.info(f"[GraphRunner] ✅ Salida normalizada: {list(normalized.keys())}")
        return normalized
    
    async def run_exploration_graph(
        self,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo de exploración.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado de la exploración
        """
        logger.info("[GraphRunner] 🧭 Ejecutando grafo de exploración")
        
        try:
            # Ejecutar el grafo de exploración
            result = await self.exploration_service.run_exploration_graph(
                chat_id=chat_id,
                user_message=message,
                context=context
            )
            
            # Normalizar la salida
            normalized_result = self.normalize_graph_output(result)
            
            logger.info("[GraphRunner] ✅ Grafo de exploración ejecutado exitosamente")
            return normalized_result
            
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error ejecutando grafo de exploración: {e}")
            return {
                "error": f"Error en exploración: {str(e)}",
                "content": "No se pudo procesar la consulta en modo exploración."
            }
    
    async def run_guided_graph(
        self,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo guiado.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado del grafo guiado
        """
        logger.info("[GraphRunner] 🎯 Ejecutando grafo guiado")
        
        try:
            # Ejecutar el grafo guiado
            result = await self.guided_service.run_guided_graph(
                chat_id=chat_id,
                user_message=message,
                context=context
            )
            
            # Normalizar la salida
            normalized_result = self.normalize_graph_output(result)
            
            logger.info("[GraphRunner] ✅ Grafo guiado ejecutado exitosamente")
            return normalized_result
            
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error ejecutando grafo guiado: {e}")
            return {
                "error": f"Error en modo guiado: {str(e)}",
                "content": "No se pudo procesar la consulta en modo guiado."
            }
    
    async def run_graph(
        self,
        explorer: bool,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo apropiado basado en el modo.
        
        Args:
            explorer: True para modo exploración, False para modo guiado
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado del grafo ejecutado
        """
        if explorer:
            return await self.run_exploration_graph(chat_id, message, context)
        else:
            return await self.run_guided_graph(chat_id, message, context)
