from typing import Dict, Any, List, Optional, TypedDict

from langgraph.graph import StateGraph
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage
from app.schemas.plan_schema import PlanModel
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function

import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Estado compartido del grafo
# ──────────────────────────────────────────────────────
class ExplorationState(TypedDict, total=False):
    chat_id: str
    message: ChatMessage
    history: List[Dict[str, Any]]

    # Recursos inferidos
    db_ids: List[str]
    db_conns: List[DatabaseConnection]
    db_dialect: Optional[str]
    apps: List[App]
    functions: List[Function]
    proxy_id: Optional[str]

    # Salidas posibles
    plan: PlanModel
    assistant_response: str
    error: str


# ──────────────────────────────────────────────────────
#   Grafo Exploration
# ──────────────────────────────────────────────────────
class ExplorationGraph:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory

    async def run(self, context: ExplorationState) -> ExplorationState:
        builder = StateGraph(ExplorationState)

        # ── Nodo 1: inferir BDs, apps y funciones ───────────────────────────────
        async def infer_resources(state: ExplorationState) -> ExplorationState:
            message: ChatMessage = state["message"]
            langchain = self.factory.get_langchain_service()

            db_conns: List[DatabaseConnection] = []
            db_ids: List[str] = []
            db_dialect: Optional[str] = None

            # Bases de datos
            try:
                db = langchain.get_database_retriever().infer_best_database(message.content)
                if db:
                    # Instancia SQL para schema
                    db_conns = [self.factory.get_database_service().get_sql_instance(db.id)]
                    db_ids = [db.id]

                    # Intentar inferir dialecto a partir del engine real
                    try:
                        record = self.factory.get_database_service().get_record(db.id)
                        if record:
                            engine = self.factory.get_database_service().build_sqlalchemy_engine(record)
                            db_dialect = getattr(engine.dialect, "name", None)
                            if db_dialect:
                                logger.info("[ExplorationGraph] 🧪 Dialecto inferido: %s", db_dialect)
                    except Exception as e:
                        logger.debug("[ExplorationGraph] No se pudo inferir dialecto: %s", e)

                logger.info("[ExplorationGraph] 🧠 DB inferred: %s", getattr(db, "name", "None") if db else "None")
            except Exception as e:
                logger.warning("[ExplorationGraph] ⚠️ DB inference failed: %s", e)

            # Aplicaciones y funciones
            try:
                apps = langchain.get_app_retriever().search_relevant_apps(message.content)
                functions: List[Function] = []
                proxy_id = None
                for app in apps:
                    functions.extend(self.factory.get_function_service().get_by_app(app.id))
                    if app.proxy_id:
                        proxy_id = app.proxy_id
                logger.info("[ExplorationGraph] 🤖 Inferred apps: %s", [a.name for a in apps])
            except Exception as e:
                logger.warning("[ExplorationGraph] ⚠️ App inference failed: %s", e)
                apps, functions, proxy_id = [], [], None

            return {
                **state,
                "db_ids": db_ids,
                "db_conns": db_conns,
                "db_dialect": db_dialect,
                "apps": apps,
                "functions": functions,
                "proxy_id": proxy_id,
            }

        # ── Nodo 2: llamar a OpenAI y decidir ───────────────────────────────────
        async def plan_or_reply(state: ExplorationState) -> ExplorationState:
            try:
                logger.info("[ExplorationGraph] 🧠 Calling OpenAI for plan or reply...")

                # Construir db_schema con anotación de dialecto
                db_schema = state["db_conns"][0]._schema if state.get("db_conns") else None
                if db_schema and state.get("db_dialect"):
                    db_schema = f"-- DIALECT: {state['db_dialect']}\n{db_schema}"

                result = await self.factory.get_openai_service().plan_actions(
                    chat_id=state["chat_id"],
                    user_message=state["message"],
                    db_schema=db_schema,
                    available_functions=state.get("functions", []),
                    available_mcp_tools=None,
                    history=state.get("history", []),
                )

                # — Plan con acciones
                if result.get("actions"):
                    plan = PlanModel.model_validate(result)
                    logger.info("[ExplorationGraph] ✅ Plan generado (%d acciones)", len(plan.actions))
                    return {**state, "plan": plan}

                # — Respuesta simple
                if result.get("assistant_response"):
                    logger.info("[ExplorationGraph] ✅ Respuesta simple generada")
                    return {**state, "assistant_response": result["assistant_response"]}

                # — Fallback
                logger.warning("[ExplorationGraph] ⚠️ Modelo no devolvió contenido")
                return {**state, "assistant_response": "Disculpa, no he entendido tu mensaje."}

            except Exception as e:
                logger.exception("[ExplorationGraph] ❌ Error generando plan/respuesta")
                return {
                    **state,
                    "error": str(e),
                    "assistant_response": "Ha ocurrido un error interno. Inténtalo de nuevo.",
                }

        # ── Construcción del grafo ──────────────────────────────────────────────
        builder.add_node("infer_resources", infer_resources)
        builder.add_node("plan_or_reply", plan_or_reply)

        builder.set_entry_point("infer_resources")
        builder.add_edge("infer_resources", "plan_or_reply")
        builder.set_finish_point("plan_or_reply")

        graph = builder.compile()
        return await graph.ainvoke(context)
