from typing import Dict, Any, Optional, List, TypedDict

from langgraph.graph import StateGraph
from app.core.service_factory import ServiceFactory
from app.schemas.plan_schema import PlanModel
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function

import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Estado del GuidedGraph
# ──────────────────────────────────────────────────────
class GuidedState(TypedDict, total=False):
    chat_id: str
    message: ChatMessage

    # contexto opcional
    db_ids: Optional[List[Any]]                 # IDs de DB (lo que te llegue: UUID/int)
    db_schema: Optional[str]
    functions: List[Function]
    available_mcp_tools: Optional[Any]
    history: List[Dict[str, Any]]
    available_dbs: Optional[List[Dict[str, Any]]]  # p.ej. [{"db_id": X, "dialect": "postgresql"}]
    db_dialect: Optional[str]                   # inferido

    # salidas
    plan: PlanModel
    assistant_response: str
    error: str


class GuidedGraph:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory

    async def run(self, context: GuidedState) -> GuidedState:
        builder = StateGraph(GuidedState)

        async def plan_or_reply(state: GuidedState) -> GuidedState:
            try:
                logger.info("[GuidedGraph] 📥 Generating plan / reply")

                # 1) Inferir dialecto (si no viene ya)
                dialect = state.get("db_dialect") or self._infer_db_dialect(state)
                if dialect:
                    logger.info("[GuidedGraph] 🧪 Dialecto inferido: %s", dialect)

                # 2) Inyectar el dialecto en el schema para ayudar al LLM
                db_schema = state.get("db_schema")
                if db_schema and dialect:
                    db_schema = f"-- DIALECT: {dialect}\n{db_schema}"

                # 3) Llamar al planner (devolverá plan o respuesta simple)
                result = await self.factory.get_openai_service().plan_actions(
                    chat_id=state["chat_id"],
                    user_message=state["message"],
                    db_schema=db_schema,
                    available_functions=state.get("functions", []),
                    available_mcp_tools=state.get("available_mcp_tools"),
                    history=state.get("history", []),
                )

                # — Plan con acciones
                if result.get("actions"):
                    plan = PlanModel.model_validate(result)
                    logger.info("[GuidedGraph] ✅ Plan generado (%d acciones)", len(plan.actions))
                    return {**state, "plan": plan, "db_dialect": dialect} if dialect else {**state, "plan": plan}

                # — Respuesta simple
                if result.get("assistant_response"):
                    logger.info("[GuidedGraph] ✅ Respuesta simple generada")
                    return {
                        **state,
                        "assistant_response": result["assistant_response"],
                        "db_dialect": dialect
                    } if dialect else {
                        **state,
                        "assistant_response": result["assistant_response"],
                    }

                # — Fallback
                logger.warning("[GuidedGraph] ⚠️ Modelo sin respuesta")
                return {
                    **state,
                    "assistant_response": "Disculpa, no he entendido tu mensaje.",
                    "db_dialect": dialect
                } if dialect else {
                    **state,
                    "assistant_response": "Disculpa, no he entendido tu mensaje.",
                }

            except Exception as e:
                logger.exception("[GuidedGraph] ❌ Error generando plan/respuesta")
                return {
                    **state,
                    "error": str(e),
                    "assistant_response": "Ha ocurrido un error interno. Inténtalo de nuevo."
                }

        builder.add_node("plan_or_reply", plan_or_reply)
        builder.set_entry_point("plan_or_reply")
        builder.set_finish_point("plan_or_reply")

        graph = builder.compile()
        return await graph.ainvoke(context)

    # ──────────────────────────────────────────────────────
    #   Helpers
    # ──────────────────────────────────────────────────────
    def _infer_db_dialect(self, state: GuidedState) -> Optional[str]:
        """
        Intenta obtener el dialecto de:
        1) available_dbs[0]['dialect'] si hay exactamente una DB disponible,
        2) db_ids[0] → construir engine y leer engine.dialect.name,
        3) None si no se puede inferir.
        """
        # 1) available_dbs con un único elemento y dialecto explícito
        avail = state.get("available_dbs") or []
        if isinstance(avail, list) and len(avail) == 1:
            dialect = (avail[0] or {}).get("dialect")
            if isinstance(dialect, str) and dialect.strip():
                return dialect.strip()

        # 2) db_ids → construir engine y detectar dialecto
        db_ids = state.get("db_ids") or []
        if isinstance(db_ids, list) and len(db_ids) == 1:
            db_id = db_ids[0]
            try:
                db_service = self.factory.get_database_service()
                record = db_service.get_record(db_id)  # tu método acepta int/uuid según tu modelo
                if not record:
                    return None
                engine = db_service.build_sqlalchemy_engine(record)
                return getattr(engine.dialect, "name", None)
            except Exception as e:
                logger.debug("[GuidedGraph] No se pudo inferir dialecto desde db_id=%s: %s", db_id, e)
                return None

        # 3) No se puede inferir
        return None
