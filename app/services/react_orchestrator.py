"""
🔧 FASE 7: ReAct Orchestrator (Simplificación del Orchestrator)
────────────────────────────────────────────────────────────────
ReAct (Reasoning + Acting) como coordinador principal que simplifica
drásticamente la lógica del orchestrator actual.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate
from app.core.langsmith_config import traceable_if_enabled
from app.services.execution.graphs.exploration_graph import ExplorationGraph
from app.services.execution.graphs.guided_graph import GuidedGraph
from app.services.ai.langchain_service import LangchainService

logger = logging.getLogger(__name__)


class ReActOrchestrator:
    """
    🧠 ReAct Orchestrator: Coordinador principal simplificado
    
    Think → Act → Observe → Repeat hasta resolver completamente
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # 🧠 Servicios principales
        self.langchain_service = LangchainService(factory)
        self.exploration_graph = ExplorationGraph(factory)
        self.guided_graph = GuidedGraph(factory)
        
        # 🔧 Configuración ReAct
        self.max_iterations = 5  # Máximo de iteraciones ReAct
        self.thinking_prompt = """
        Eres un asistente inteligente que usa ReAct (Reasoning + Acting) para resolver problemas.
        
        Para cada pregunta del usuario, debes:
        1. THINK: Analizar qué necesitas hacer
        2. ACT: Ejecutar la acción apropiada
        3. OBSERVE: Evaluar el resultado
        4. Repetir si es necesario
        
        Acciones disponibles:
        - "explore": Usar ExplorationGraph para consultas de BD generales
        - "guide": Usar GuidedGraph para consultas específicas con contexto
        - "sql_direct": Generar y ejecutar SQL directamente
        - "complete": Respuesta final completa
        
        Responde en formato JSON:
        {
            "action": "explore|guide|sql_direct|complete",
            "reasoning": "Explicación de por qué eliges esta acción",
            "sql": "SQL si es sql_direct, null en otro caso",
            "context_needed": "Qué contexto adicional necesitas"
        }
        """
        
        logger.info("[ReActOrchestrator] 🚀 Inicializado con ReAct como coordinador principal")
    
    @traceable_if_enabled(
        name="react_orchestrator_handle_message",
        tags=["react", "orchestrator"],
        metadata={"service": "ReActOrchestrator"}
    )
    async def handle_message(
        self,
        chat_id: UUID,
        message: ChatMessage,
        db_ids: Optional[List[UUID]] = None,
        app_ids: Optional[List[UUID]] = None,
        explorer: bool = True
    ) -> Dict[str, Any]:
        """
        🧠 Método principal: Maneja mensajes usando ReAct
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            db_ids: IDs de bases de datos (opcional)
            app_ids: IDs de aplicaciones (opcional)
            explorer: Modo explorador vs guiado
            
        Returns:
            Respuesta procesada con ReAct
        """
        start_time = time.time()
        logger.info(f"[ReActOrchestrator] 🧠 Iniciando ReAct para: '{message.content[:50]}...'")
        
        # 🎯 Contexto inicial
        context = {
            "chat_id": str(chat_id),
            "user_id": str(self.user_id),
            "message": message.content,
            "db_ids": [str(db_id) for db_id in (db_ids or [])],
            "app_ids": [str(app_id) for db_id in (app_ids or [])],
            "explorer": explorer,
            "iteration": 0,
            "history": [],
            "results": []
        }
        
        # 🔄 Loop ReAct principal
        while context["iteration"] < self.max_iterations:
            context["iteration"] += 1
            logger.info(f"[ReActOrchestrator] 🔄 Iteración ReAct {context['iteration']}/{self.max_iterations}")
            
            # 🧠 THINK: LLM decide qué hacer
            thought = await self._think(context)
            if not thought:
                logger.error("[ReActOrchestrator] ❌ Error en fase THINK")
                break
            
            # 📝 Guardar pensamiento en historial
            await self._save_reasoning_step(chat_id, "think", thought["reasoning"])
            
            # 🎯 ACT: Ejecutar la acción decidida
            if thought["action"] == "complete":
                logger.info("[ReActOrchestrator] ✅ ReAct completado")
                break
            
            result = await self._act(thought, context)
            if not result:
                logger.error(f"[ReActOrchestrator] ❌ Error en fase ACT: {thought['action']}")
                break
            
            # 📝 Guardar resultado de la acción
            await self._save_reasoning_step(chat_id, "act", f"Acción: {thought['action']}, Resultado: {str(result)[:100]}...")
            
            # 👁️ OBSERVE: Evaluar resultado y actualizar contexto
            context = await self._observe(result, context)
            
            # 🔍 Verificar si ya tenemos respuesta completa
            if self._is_complete(context):
                logger.info("[ReActOrchestrator] ✅ Respuesta completa obtenida")
                break
        
        # 🎯 Respuesta final
        response_time = int((time.time() - start_time) * 1000)
        final_response = self._build_final_response(context, response_time)
        
        logger.info(f"[ReActOrchestrator] ✅ ReAct completado en {response_time}ms, {context['iteration']} iteraciones")
        return final_response
    
    async def _think(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🧠 FASE THINK: LLM analiza qué hacer
        """
        try:
            # Construir prompt con contexto
            prompt = f"""
            {self.thinking_prompt}
            
            Contexto actual:
            - Mensaje del usuario: {context['message']}
            - Bases de datos disponibles: {context['db_ids']}
            - Aplicaciones disponibles: {context['app_ids']}
            - Modo: {'explorador' if context['explorer'] else 'guiado'}
            - Iteración: {context['iteration']}
            - Historial de acciones: {context['history']}
            
            ¿Qué acción debes tomar?
            """
            
            # Obtener respuesta del LLM
            response = await self.langchain_service.llm.ainvoke(prompt)
            content = response.content.strip()
            
            # Parsear JSON de la respuesta
            try:
                import json
                thought = json.loads(content)
                
                # Validar estructura
                required_fields = ["action", "reasoning", "sql", "context_needed"]
                if all(field in thought for field in required_fields):
                    logger.info(f"[ReActOrchestrator] 🧠 THINK: {thought['action']} - {thought['reasoning'][:50]}...")
                    return thought
                else:
                    logger.error(f"[ReActOrchestrator] ❌ THINK: Respuesta malformada, campos faltantes")
                    return None
                    
            except json.JSONDecodeError:
                logger.error(f"[ReActOrchestrator] ❌ THINK: No se pudo parsear JSON: {content}")
                return None
                
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error en THINK: {e}")
            return None
    
    async def _act(self, thought: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🎯 FASE ACT: Ejecuta la acción decidida
        """
        try:
            action = thought["action"]
            logger.info(f"[ReActOrchestrator] 🎯 ACT: Ejecutando {action}")
            
            if action == "explore":
                # Usar ExplorationGraph
                return await self._execute_exploration_graph(context)
                
            elif action == "guide":
                # Usar GuidedGraph
                return await self._execute_guided_graph(context)
                
            elif action == "sql_direct":
                # Generar y ejecutar SQL directamente
                return await self._execute_sql_direct(thought.get("sql"), context)
                
            else:
                logger.warning(f"[ReActOrchestrator] ⚠️ ACT: Acción desconocida: {action}")
                return None
                
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error en ACT: {e}")
            return None
    
    async def _execute_exploration_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta ExplorationGraph"""
        try:
            # Preparar estado para ExplorationGraph
            graph_state = {
                "chat_id": context["chat_id"],
                "message": ChatMessage(role="user", content=context['message']),
                "db_ids": context["db_ids"],
                "app_ids": context["app_ids"]
            }
            
            result = await self.exploration_graph.run(graph_state)
            logger.info("[ReActOrchestrator] ✅ ExplorationGraph ejecutado")
            return result
            
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error en ExplorationGraph: {e}")
            return {"error": f"Error en ExplorationGraph: {str(e)}"}
    
    async def _execute_guided_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta GuidedGraph"""
        try:
            # Preparar estado para GuidedGraph
            graph_state = {
                "chat_id": context["chat_id"],
                "message": ChatMessage(role="user", content=context['message']),
                "db_ids": context["db_ids"],
                "app_ids": context["app_ids"]
            }
            
            result = await self.guided_graph.run(graph_state)
            logger.info("[ReActOrchestrator] ✅ GuidedGraph ejecutado")
            return result
            
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error en GuidedGraph: {e}")
            return {"error": f"Error en GuidedGraph: {str(e)}"}
    
    async def _execute_sql_direct(self, sql: Optional[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta SQL directamente"""
        try:
            if not sql and context["db_ids"]:
                # Generar SQL si no se proporciona
                db_id = context["db_ids"][0]
                sql_result = await self.langchain_service.generate_sql_from_question(
                    context["message"], 
                    UUID(db_id)
                )
                sql = sql_result.get("sql")
            
            if sql:
                # Ejecutar SQL usando ExecutionEngine
                execution_service = self.factory.get_execution_engine_service()
                action = {
                    "type": "db_query",
                    "sql": sql,
                    "database_id": context["db_ids"][0] if context["db_ids"] else None
                }
                
                result = await execution_service._run_db_query(action, context)
                logger.info("[ReActOrchestrator] ✅ SQL ejecutado directamente")
                return result
            else:
                return {"error": "No se pudo generar SQL válido"}
                
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error ejecutando SQL: {e}")
            return {"error": f"Error ejecutando SQL: {str(e)}"}
    
    async def _observe(self, result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        👁️ FASE OBSERVE: Evalúa resultado y actualiza contexto
        """
        try:
            # Agregar resultado al historial
            context["results"].append(result)
            context["history"].append({
                "action": "executed",
                "result": str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            })
            
            # Evaluar si el resultado es satisfactorio
            if self._is_satisfactory_result(result):
                context["satisfactory"] = True
                logger.info("[ReActOrchestrator] 👁️ OBSERVE: Resultado satisfactorio")
            else:
                context["satisfactory"] = False
                logger.info("[ReActOrchestrator] 👁️ OBSERVE: Resultado no satisfactorio, continuando...")
            
            return context
            
        except Exception as e:
            logger.exception(f"[ReActOrchestrator] ❌ Error en OBSERVE: {e}")
            return context
    
    def _is_satisfactory_result(self, result: Dict[str, Any]) -> bool:
        """Determina si un resultado es satisfactorio"""
        if "error" in result:
            return False
        
        # Verificar si tenemos contenido útil
        content_fields = ["content", "result", "assistant_response", "rows"]
        for field in content_fields:
            if field in result and result[field]:
                return True
        
        return False
    
    def _is_complete(self, context: Dict[str, Any]) -> bool:
        """Determina si ReAct está completo"""
        return (
            context.get("satisfactory", False) or
            context["iteration"] >= self.max_iterations or
            len(context["results"]) > 0
        )
    
    def _build_final_response(self, context: Dict[str, Any], response_time: int) -> Dict[str, Any]:
        """Construye la respuesta final"""
        if context["results"]:
            # Usar el último resultado satisfactorio
            final_result = context["results"][-1]
            
            return {
                "content": final_result.get("content", final_result.get("result", str(final_result))),
                "source": "react_orchestrator",
                "iterations": context["iteration"],
                "response_time_ms": response_time,
                "method": "react_hybrid",
                "context_used": {
                    "db_ids": context["db_ids"],
                    "app_ids": context["app_ids"],
                    "explorer": context["explorer"]
                },
                "react_history": context["history"]
            }
        else:
            return {
                "content": "No se pudo procesar la solicitud después de múltiples intentos.",
                "error": "ReAct falló después de todas las iteraciones",
                "iterations": context["iteration"],
                "response_time_ms": response_time
            }
    
    async def _save_reasoning_step(self, chat_id: UUID, step_type: str, content: str):
        """Guarda un paso de razonamiento en el historial del chat"""
        try:
            chat_history_service = self.factory.get_chat_history_service()
            if chat_history_service:
                await chat_history_service.create_chat_history(
                    ChatHistoryCreate(
                        chat_id=chat_id,
                        user_id=self.user_id,
                        role="assistant",
                        content=f"[ReAct {step_type.upper()}] {content}",
                        idempotency_key=f"react_{step_type}_{uuid4()}"
                    )
                )
        except Exception as e:
            logger.warning(f"[ReActOrchestrator] ⚠️ No se pudo guardar paso de razonamiento: {e}")
