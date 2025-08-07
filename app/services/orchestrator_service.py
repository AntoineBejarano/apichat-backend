# app/services/orchestrator_service.py
"""
OrchestratorService
───────────────────
1. Guarda el mensaje del usuario.
2. Lanza Guided / Exploration Graph y obtiene:
      • una respuesta simple, o
      • un PlanModel con acciones.
3. Si hay plan, ejecuta acciones con ExecutionEngineService y
   renderiza la respuesta final.
4. Devuelve siempre `assistant_response` al front y registra todo.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.schemas.plan_schema import PlanModel

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Modelo auxiliar (por si lo sigues usando en PlanModel)
# ──────────────────────────────────────────────────────
class ActionModel(BaseModel):
    type: str = Field(..., description="db_query, api_function, mcp_tool")
    sql: Optional[str] = None
    question: Optional[str] = None
    function_id: Optional[int] = None
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    store_as: Optional[str] = None
    proxy_id: Optional[int] = None


# ──────────────────────────────────────────────────────
#   Servicio
# ──────────────────────────────────────────────────────
class OrchestratorService:
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        self.history_service = factory.get_chat_history_service()
        logger.info("[OrchestratorService] Initialized for user_id=%s", self.user_id)

    # ===================================================
    #  PUBLIC ENTRY-POINT
    # ===================================================
    async def handle_user_message(
        self,
        chat_id: UUID,
        db_ids: Optional[List[UUID]],
        app_ids: Optional[List[UUID]],
        explorer: bool,
        agent_id: Optional[UUID],
        message: ChatMessage,
    ) -> Dict[str, Any]:

        # 1) Límite de uso
        self.factory.get_usage_service().check_limit()

        # 2) Guardar mensaje del usuario
        self._store_user_message(chat_id, message)

        # 3) Prompt del agente (si aplica)
        system_prompt = self._load_agent_prompt(agent_id)

        # 4) Historial reciente
        history_records = self.history_service.get_history(chat_id, limit=20)
        history = [ChatHistoryOut.model_validate(rec).model_dump() for rec in history_records]

        # 5) Ejecutar grafo Guided / Exploration
        context: Dict[str, Any] = {
            "chat_id": chat_id,
            "db_ids": db_ids,
            "app_ids": app_ids,
            "explorer": explorer,
            "agent_id": agent_id,
            "message": message,
            "history": history,
            "system_prompt": system_prompt,
            "user_id": self.user_id,
        }
        graph_runner = self._select_graph_runner(explorer)
        graph_output = await graph_runner.run(context)

        # 6) Procesar salida del grafo
        assistant_response: str
        executed_strategy_id: Optional[UUID] = graph_output.get("executed_strategy_id")
        execution_results: Optional[Dict[str, Any]] = None

        # a) Respuesta simple
        if graph_output.get("assistant_response"):
            assistant_response = graph_output["assistant_response"]

        # b) Hay plan con acciones → ejecutamos
        elif graph_output.get("plan"):
            plan: PlanModel = graph_output["plan"]

            # --- preparar contexto para la ejecución
            # Usa db_ids inferidos por el grafo si existen,
            # en caso contrario los que venían de la llamada original.
            exec_db_ids = graph_output.get("db_ids") or db_ids
            available_dbs = self.factory.get_database_service().get_user_databases()

            try:
                engine_out = self.factory.get_execution_engine_service().run(
                    plan.model_dump(),
                    chat_id,
                    ctx={
                        "db_ids": exec_db_ids,
                        "available_dbs": available_dbs,
                    },
                )
                assistant_response = engine_out["assistant_response"]
                execution_results = engine_out["variables"]
            except Exception as e:
                logger.exception("[Orchestrator] Execution engine error: %s", e)
                assistant_response = (
                    "He generado un plan, pero ocurrió un error al ejecutarlo."
                )

        # c) El grafo devolvió error
        else:
            err = graph_output.get("error", "unknown")
            logger.error("[Orchestrator] Graph error: %s", err)
            raise HTTPException(500, "Error interno al procesar tu solicitud.")

        # 7) Guardar respuesta del asistente
        self._save_assistant_message(
            chat_id,
            assistant_response,
            token_count=None,
            executed_strategy_id=executed_strategy_id,
        )

        # 8) Devolver al front
        return {
            **graph_output,
            "assistant_response": assistant_response,
            "execution_results": execution_results,
        }

    # ===================================================
    #  Helpers
    # ===================================================
    def _select_graph_runner(self, explorer: bool):
        from app.services.graphs.exploration_graph import ExplorationGraph
        from app.services.graphs.guided_graph import GuidedGraph
        GraphClass = ExplorationGraph if explorer else GuidedGraph
        logger.info("[OrchestratorService] Using graph: %s", GraphClass.__name__)
        return GraphClass(self.factory)

    def _store_user_message(self, chat_id: UUID, message: ChatMessage) -> None:
        try:
            self.history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role=message.role,
                    content=message.content,
                    name=message.name,
                    is_function_call=False,
                )
            )
            logger.info("[OrchestratorService] User message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store user message: %s", e)

    def _load_agent_prompt(self, agent_id: Optional[UUID]) -> str:
        if not agent_id:
            return ""
        try:
            prompt = self.factory.get_agent_service().get_prompt(agent_id)
            logger.info("[OrchestratorService] Loaded prompt for agent_id=%s", agent_id)
            return prompt
        except Exception as e:
            logger.warning("[OrchestratorService] Agent prompt load failed: %s", e)
            return ""

    def _save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        try:
            self.history_service.create_message(
                data=ChatHistoryCreate(
                    chat_id=chat_id,
                    user_id=self.user_id,
                    role="assistant",
                    content=content,
                    token_count=token_count,
                    is_function_call=False,
                    executed_strategy_id=executed_strategy_id,
                )
            )
            logger.info("[OrchestratorService] Assistant message stored")
        except Exception as e:
            logger.exception("[OrchestratorService] Failed to store assistant message: %s", e)
