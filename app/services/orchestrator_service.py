import logging
from typing import List, Dict, Optional, Any, TYPE_CHECKING
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel, Field, ValidationError

from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.schemas.executed_strategy_schema import ExecutedStrategyCreate

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# --- Modelos internos ---
class ActionModel(BaseModel):
    type: str = Field(..., description="db_query, api_function, mcp_tool, etc.")
    sql: Optional[str] = None
    question: Optional[str] = None
    function_id: Optional[int] = None
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    store_as: Optional[str] = None
    proxy_id: Optional[int] = None  # ✅ Nuevo para pasar proxy


class PlanModel(BaseModel):
    actions: List[ActionModel] = Field(default_factory=list)
    assistant_response: str = Field(...)


class OrchestratorService:
    """
    Cerebro de APIchat:
      - Procesa mensajes
      - Decide si es conversación simple o plan complejo
      - Descubre apps y bases conectadas
      - Genera plan con IA
      - Guarda estrategia ejecutada
      - Ejecuta el plan con ExecutionEngine (LangGraph/LangChain)
    """

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: UUID = factory.user.id
        self.history_service = factory.get_chat_history_service()
        logger.info("[OrchestratorService] 🚀 Inicializado para user_id=%s", self.user_id)

    async def handle_user_message(
        self,
        chat_id: UUID,
        database_id: Optional[UUID],
        app_id: Optional[UUID],
        agent_id: Optional[UUID],
        message: ChatMessage
    ) -> Dict[str, Any]:
        steps: List[str] = []
        executed_strategy_id: Optional[UUID] = None

        # 1️⃣ Comprobar límites de uso
        try:
            self.factory.get_usage_service().check_limit()
            steps.append("✅ Límite de tokens OK")
        except HTTPException:
            warning_msg = "⚠️ Límite de tokens alcanzado. Mejora tu plan para continuar."
            self._save_assistant_message(chat_id, warning_msg, 0)
            return {"assistant_response": warning_msg, "steps": steps}

        # 2️⃣ Guardar mensaje del usuario
        self.history_service.create_message(
            data=ChatHistoryCreate(
                chat_id=chat_id,
                user_id=self.user_id,
                role=message.role,
                content=message.content,
                name=message.name,
                is_function_call=False
            )
        )
        steps.append("📩 Mensaje del usuario guardado")

        # 3️⃣ Cargar prompt del agente (si hay)
        system_prompt = ""
        if agent_id:
            system_prompt = self.factory.get_agent_service().get_prompt(agent_id)
            steps.append(f"🤖 Prompt del agente {agent_id} cargado")

        # 4️⃣ Descubrir conexiones disponibles
        available_apps = self.factory.get_apps_service().list_all_for_user()
        available_dbs = self.factory.get_database_service().list_all_for_user()
        steps.append(f"🔍 Descubiertas {len(available_apps)} apps y {len(available_dbs)} bases de datos conectadas")

        # 5️⃣ Preparar funciones y schema DB (si hay selección explícita)
        db_conn = self.factory.get_database_service().get_sql_instance(database_id) if database_id else None
        db_schema = getattr(db_conn, "_schema", None) if db_conn else None

        app = self.factory.get_apps_service().get_by_id(app_id) if app_id else None
        functions = self.factory.get_function_service().get_by_app(app.id) if app else []
        proxy_id = app.proxy_id if app and app.proxy_id else None  # ✅ Obtenemos proxy_id de la app
        steps.append(f"🔧 {len(functions)} funciones disponibles para la app seleccionada")

        # 6️⃣ Historial de chat
        history = self.history_service.get_history(chat_id)
        history_dicts = [ChatHistoryOut.model_validate(m).model_dump() for m in history]

        # 7️⃣ Generar plan con IA
        raw_plan = await self.factory.get_openai_service().plan_actions(
            chat_id=chat_id,
            system_prompt=system_prompt,
            user_message=message,
            db_schema=db_schema,
            available_functions=functions,
            available_mcp_tools=None,
            history=history_dicts
        )
        steps.append("🧠 Plan generado por IA")

        # 8️⃣ Validar plan
        try:
            plan = PlanModel.model_validate(raw_plan)
            steps.append("✅ Plan validado correctamente")
        except ValidationError as ve:
            return self._error_response(steps, ve)

        # 🔹 Añadir proxy_id automáticamente si tenemos proxy asociado
        if proxy_id:
            for action in plan.actions:
                if not action.proxy_id:
                    action.proxy_id = proxy_id
            steps.append(f"🌐 Proxy ID {proxy_id} añadido a todas las acciones")

        # 9️⃣ Si no hay acciones → chat simple
        if not plan.actions:
            assistant_msg = await self.factory.get_openai_service().chat_completion(
                chat_id=chat_id,
                system_prompt=system_prompt,
                user_message=message
            )
            self._save_assistant_message(chat_id, assistant_msg.content, assistant_msg.token_count)
            steps.append("💬 Conversación simple completada")
            return {"assistant_response": assistant_msg.content, "steps": steps}

        # 🔟 Guardar estrategia ejecutada usando ExecutedStrategyService
        executed_strategy = self.factory.get_executed_strategy_service().create(
            ExecutedStrategyCreate(
                chat_id=chat_id,
                plan=plan.model_dump(),
                graph=self._generate_graph(plan.actions),
                is_user_defined=False
            )
        )
        executed_strategy_id = executed_strategy.id
        steps.append(f"📜 Estrategia ejecutada guardada (id={executed_strategy_id})")

        # 1️⃣1️⃣ Ejecutar plan con LangGraph/LangChain
        engine_results = self.factory.get_execution_engine_service().run(
            plan.model_dump(),
            chat_id,
            ctx={"available_apps": available_apps, "available_dbs": available_dbs}
        )
        steps.append("⚙️ Plan ejecutado vía LangGraph + LangChain")

        # 1️⃣2️⃣ Guardar respuesta final
        self._save_assistant_message(chat_id, plan.assistant_response, None, executed_strategy_id)
        steps.append("🧾 Respuesta final generada")

        return {
            "assistant_response": plan.assistant_response,
            "steps": steps,
            "execution_results": engine_results
        }

    def _save_assistant_message(self, chat_id, content, token_count, executed_strategy_id=None):
        self.history_service.create_message(
            data=ChatHistoryCreate(
                chat_id=chat_id,
                user_id=self.user_id,
                role="assistant",
                content=content,
                token_count=token_count,
                is_function_call=False,
                executed_strategy_id=executed_strategy_id
            )
        )

    def _generate_graph(self, actions: List[ActionModel]) -> Dict[str, Any]:
        nodes, edges = [], []
        for idx, action in enumerate(actions):
            node_id = f"node_{idx+1}"
            nodes.append({"id": node_id, "type": action.type, "data": action.model_dump()})
            if idx > 0:
                edges.append({"from": f"node_{idx}", "to": node_id})
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _error_response(steps: List[str], exc: Exception) -> Dict[str, Any]:
        return {"error": str(exc), "steps": steps + ["⚠️ Error encontrado"]}
