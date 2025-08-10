"""
IterativeRAGHandler - Manejador de RAG Iterativo
─────────────────────────────────────────────────
Maneja la ejecución iterativa de RAG para replanificar basándose en resultados intermedios.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.schemas.chat_schema import ChatMessage

logger = logging.getLogger(__name__)


class IterativeRAGHandler:
    """
    Manejador para ejecución iterativa de RAG (Retrieval-Augmented Generation).
    Permite múltiples iteraciones para obtener respuestas más completas.
    """
    
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.performance_monitor = factory.get_performance_monitoring_service()
    
    async def run_iterative_rag(
        self,
        chat_id: UUID,
        message: ChatMessage,
        db_ids: List[UUID],
        app_ids: List[str],
        context_loader: "ContextLoader",
        graph_runner: "GraphRunner",
        explorer: bool = False,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Ejecuta RAG iterativo para obtener respuestas más completas.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            db_ids: IDs de bases de datos
            app_ids: IDs de aplicaciones
            context_loader: Cargador de contexto
            graph_runner: Ejecutor de grafos
            explorer: Modo explorador
            max_iterations: Máximo de iteraciones
            
        Returns:
            Dict con respuesta del asistente y resultados acumulados
        """
        logger.info(f"[IterativeRAGHandler] 🔄 Iniciando flujo RAG iterativo (max {max_iterations} iteraciones)")
        
        # Inicialización
        self.performance_monitor.take_snapshot("iterative_orchestrator_start")
        
        # Cargar contexto inicial
        context_tasks = await context_loader.load_context_parallel(chat_id, message, db_ids, app_ids, explorer)
        context_tasks["explorer"] = explorer
        
        # Variables para el bucle iterativo
        iteration = 1
        accumulated_results = {}
        final_answer = None
        
        while iteration <= max_iterations and not final_answer:
            logger.info(f"[IterativeRAGHandler] 🔄 Iteración {iteration}/{max_iterations}")
            
            # Validar schemas antes de cada iteración
            if not self._validate_context_for_iteration(context_tasks, db_ids, iteration):
                return self._create_error_response("missing_valid_schemas_iteration", iteration)
            
            # Ejecutar grafo (siempre en modo exploración para iterativo)
            execution_results = await graph_runner.run_graph(True, chat_id, message.content, context_tasks)
            execution_results = graph_runner.normalize_graph_output(execution_results)
            
            logger.info(f"[IterativeRAGHandler] ✅ Salida del grafo normalizada en iteración {iteration} (claves: {list(execution_results.keys())})")
            
            # Verificar si tenemos respuesta directa
            if self._has_direct_response(execution_results):
                final_answer = execution_results.get("assistant_response", "")
                logger.info(f"[IterativeRAGHandler] ✅ Respuesta directa obtenida en iteración {iteration}")
                break
            
            # Acumular resultados
            if execution_results.get("variables"):
                accumulated_results.update(execution_results.get("variables", {}))
            
            # Evaluar si tenemos suficiente información
            if self._has_sufficient_information(accumulated_results, iteration):
                logger.info("[IterativeRAGHandler] ✅ Información suficiente encontrada después de 2 iteraciones")
                final_answer = await self._generate_final_answer(
                    message.content, accumulated_results, context_tasks
                )
                break
            
            iteration += 1
        
        # Generar respuesta final si no se obtuvo en el bucle
        if not final_answer:
            logger.warning(f"[IterativeRAGHandler] ⚠️ Máximo de iteraciones alcanzado ({max_iterations})")
            final_answer = await self._generate_final_answer(
                message.content, accumulated_results, context_tasks
            )
        
        self.performance_monitor.take_snapshot("iterative_orchestrator_end")
        
        return {
            "assistant_response": final_answer,
            "execution_results": accumulated_results,
            "iterations_used": iteration - 1,
            "steps": [],  # TODO: agregar pasos detallados
        }
    
    def _validate_context_for_iteration(self, context_tasks: Dict[str, Any], db_ids: List[UUID], iteration: int) -> bool:
        """Valida que el contexto sea válido para la iteración actual."""
        if not db_ids:
            return True
        
        compact_schemas = context_tasks.get("compact_schemas", {})
        if not compact_schemas:
            logger.warning(f"[IterativeRAGHandler] ⚠️ No hay compact_schemas en iteración {iteration}")
            return False
        
        for db_id in db_ids:
            db_key = str(db_id) if hasattr(db_id, 'hex') else db_id
            
            # Buscar tanto con UUID como con str
            schema_found = False
            for key in [db_id, db_key, str(db_id)]:
                if key in compact_schemas and compact_schemas[key] and compact_schemas[key].strip():
                    schema_found = True
                    break
            
            if not schema_found:
                logger.warning(f"[IterativeRAGHandler] ⚠️ No hay compact_schema válido para DB {db_id} en iteración {iteration}")
                return False
        
        logger.info(f"[IterativeRAGHandler] ✅ Compact schemas válidos para {len(db_ids)} DBs en iteración {iteration}")
        return True
    
    def _has_direct_response(self, execution_results: Dict[str, Any]) -> bool:
        """Verifica si el grafo devolvió una respuesta directa."""
        return (
            execution_results.get("assistant_response") and 
            not execution_results.get("plan")
        )
    
    def _has_sufficient_information(self, accumulated_results: Dict[str, Any], iteration: int) -> bool:
        """Determina si tenemos suficiente información para generar respuesta final."""
        return accumulated_results and iteration >= 2
    
    def _create_error_response(self, error_type: str, iteration: int) -> Dict[str, Any]:
        """Crea una respuesta de error estandarizada."""
        error_messages = {
            "missing_valid_schemas_iteration": f"❌ Error: No se pudo obtener información de las bases de datos en la iteración {iteration}."
        }
        
        return {
            "assistant_response": error_messages.get(error_type, "❌ Error desconocido"),
            "error": error_type,
            "iteration": iteration
        }
    
    async def _generate_final_answer(
        self, 
        question: str, 
        accumulated_results: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Genera la respuesta final basándose en todos los resultados acumulados.
        """
        logger.info("[IterativeRAGHandler] 📝 Generando respuesta final con información acumulada")
        
        # Construir prompt con toda la información
        results_summary = self._format_results_for_final_answer(accumulated_results)
        
        final_prompt = f"""
Pregunta del usuario: {question}

Información encontrada en la base de datos:
{results_summary}

Por favor, responde la pregunta del usuario de manera clara y completa usando la información encontrada.
Si no encuentras información específica, menciona qué se buscó y qué alternativas podrían existir.
"""
        
        try:
            openai_service = self.factory.get_openai_service()
            response = openai_service.complete_chat([
                {"role": "system", "content": "Eres un asistente experto que responde preguntas basándose en datos de base de datos. Sé claro, preciso y útil."},
                {"role": "user", "content": final_prompt}
            ])
            return response
        except Exception as e:
            logger.exception(f"[IterativeRAGHandler] ❌ Error generando respuesta final: {e}")
            return f"❌ Error generando respuesta final: {str(e)}"
    
    def _format_results_for_final_answer(self, results: Dict[str, Any]) -> str:
        """
        Formatea los resultados acumulados para la respuesta final.
        """
        if not results:
            return "No se encontró información específica en la base de datos."
        
        lines = []
        for key, value in results.items():
            if isinstance(value, (dict, list)):
                # Para estructuras complejas, mostrar resumen
                if isinstance(value, list):
                    lines.append(f"- {key}: {len(value)} elementos encontrados")
                else:
                    lines.append(f"- {key}: {len(value)} campos disponibles")
            else:
                # Para valores simples, mostrar directamente
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines)
