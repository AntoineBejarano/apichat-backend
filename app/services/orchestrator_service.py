import logging
from typing import List, Dict, Optional, Any, TYPE_CHECKING

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.schemas.chat_schema import ChatMessage
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from app.services.mcp.manager import MCPConnectorManager

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Servicio central que resuelve la intención del usuario y ejecuta
    las acciones necesarias (consultas SQL, funciones HTTP o herramientas
    MCP) devolviendo una respuesta final y un listado de *steps* para
    trazabilidad en frontend.
    """

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db: Session = factory.db
        self.user_id: int = factory.user.id

        # Servicios hijos obtenidos perezosamente del factory -----------------
        self.openai = factory.get_openai_service()
        self.agents = factory.get_agent_service()
        self.databases = factory.get_database_service()
        self.functions = factory.get_function_service()
        self.apps = factory.get_apps_service()
        self.mcp_integrations = factory.get_mcp_integration_service()
        self.executor = factory.get_executor_service

        logger.info("[OrchestratorService] Inicializado para user_id=%s", self.user_id)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    async def handle_user_message(
        self,
        database_id: Optional[int],
        app_id: Optional[int],
        agent_id: Optional[int],
        message: ChatMessage,
    ) -> Dict[str, Any]:
        """Punto de entrada principal desde los routers HTTP/WebSocket.
        Resuelve un mensaje de usuario y devuelve:

        ```json
        {
          "assistant_response": "...texto final...",
          "steps": ["step1", "step2", ...]
        }
        ```
        """

        steps: List[str] = []
        ctx: Dict[str, Any] = {}  # almacena resultados intermedios

        try:
            logger.info("[%s] 📥 Mensaje: %s", self.user_id, message.content)
            steps.append("Mensaje recibido")

            # 1️⃣  Prompt del agente (opcional) -----------------------------
            system_prompt = ""
            if agent_id:
                system_prompt = self.agents.get_prompt(agent_id)
                steps.append(f"Prompt cargado del agente {agent_id}")

            # 2️⃣  Conección DB (opcional) ---------------------------------
            db_conn: Optional[DatabaseConnection] = None
            if database_id:
                db_conn = self.databases.get_sql_instance(database_id)
                steps.append(f"Conexión a DB {database_id} establecida")

            # 3️⃣  Localizar App o MCPIntegration ---------------------------
            functions: List[Function] = []
            mcp_metadata: Optional[dict] = None

            app: Optional[App] = self.apps.get_by_id(app_id)
            if app:
                steps.append(f"App {app_id} encontrada → {app.name}")
                functions = self.functions.get_by_app(app_id)
            else:
                mcp = self.mcp_integrations.get_by_id(app_id)
                if not mcp:
                    raise HTTPException(status_code=404, detail="App o MCPIntegration no encontrada")
                mcp_metadata = mcp.mcp_metadata
                steps.append(f"MCPIntegration {app_id} encontrada → {mcp.name}")

            # 4️⃣  LLM: generar plan de acciones ---------------------------
            logger.debug("[%s] 🧠 Llamando LLM para generar plan", self.user_id)
            plan: Dict[str, Any] = await self.openai.plan_actions(
                user_id=self.user_id,
                system_prompt=system_prompt,
                user_message=message,
                db_schema=db_conn.schema if db_conn else None,
                available_functions=functions,
                available_mcp_tools=mcp_metadata,
            )
            steps.append("Plan generado por IA")

            # 5️⃣  Ejecutar acciones secuenciales --------------------------
            for idx, action in enumerate(plan.get("actions", []), start=1):
                tag = f"Step {idx}: {action['type']}"

                try:
                    if action["type"] == "db_query":
                        
                        sql_rendered = action["sql"].format(**ctx)
                        result = self.databases.execute_sql(db_conn, sql_rendered)
                        ctx[action.get("store_as", f"result_{idx}")] = result
                        steps.append(f"{tag} ✅")
                    elif action["type"] == "api_function":
                        params = self._render_params(action["params"], ctx)
                        result = self.executor.execute_by_id(action["function_id"], params)
                        ctx[action.get("store_as", f"result_{idx}")] = result
                        steps.append(f"{tag} ✅")
                    elif action["type"] == "mcp_tool":
                        params = self._render_params(action["params"], ctx)
                        result = self.execute_decision(
                            {"tool_name": action["tool_name"], "params": params},
                            mcp_metadata,
                        )
                        ctx[action.get("store_as", f"result_{idx}")] = result
                        steps.append(f"{tag} ✅")
                    else:
                        raise ValueError("Tipo de acción desconocido")
                except Exception as action_exc:
                    logger.exception("%s ❌ %s", tag, action_exc)
                    steps.append(f"{tag} ❌ {action_exc}")
                    return self._error_response(steps, action_exc)

            # 6️⃣  Respuesta final del asistente ---------------------------
            final_text = plan.get("assistant_response", "He terminado las acciones solicitadas.")
            steps.append("Respuesta final generada")
            logger.info("[%s] ✅ Flujo completo", self.user_id)

            return {"assistant_response": final_text, "steps": steps}

        except Exception as exc:
            logger.exception("[%s] ❌ Error general: %s", self.user_id, exc)
            return self._error_response(steps, exc)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------
    @staticmethod
    def _render_params(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Sustituye placeholders {{var}} en los params por valores en *context*."""
        import re, json

        def _replace(value):
            if isinstance(value, str):
                matches = re.findall(r"{{(.*?)}}", value)
                for m in matches:
                    if m in context:
                        value = value.replace(f"{{{{{m}}}}}", json.dumps(context[m]) if not isinstance(context[m], str) else str(context[m]))
            return value

        return {k: _replace(v) for k, v in params.items()}

    @staticmethod
    def _error_response(steps: List[str], exc: Exception) -> Dict[str, Any]:
        return {
            "error": "Ocurrió un error procesando tu mensaje.",
            "details": str(exc),
            "steps": steps + ["Error detectado"],
        }

    # ------------------------------------------------------------------
    # Ejecución de herramientas MCP
    # ------------------------------------------------------------------
    def execute_decision(self, decision: dict, mcp_metadata: dict) -> dict:
        logger.debug("[%s] Ejecutando herramienta MCP %s", self.user_id, decision["tool_name"])
        mcp = MCPConnectorManager(mcp_metadata)
        available = [t["name"] for t in mcp.get_tools()]

        if decision["tool_name"] not in available:
            raise HTTPException(status_code=404, detail="Herramienta MCP no disponible")

        return mcp.execute_tool(decision["tool_name"], decision.get("params", {}))
