import logging
import re
import json
from typing import Dict, Any, List, Optional
from uuid import UUID
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

class ExecutionEngineService:
    """
    Motor de ejecución:
      - Recibe un plan de acciones
      - Construye un grafo con LangGraph
      - Ejecuta tareas en paralelo si no hay dependencias
      - Usa LangChain para consultas en lenguaje natural a DB
      - Usa ProxyService si la acción o la app tienen proxy configurado
      - Encapsula ejecución MCP en método interno
    """

    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        self.history_service = factory.get_chat_history_service()

    def run(self, plan: Dict[str, Any], chat_id: UUID, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info("[ExecutionEngineService] 🚀 Iniciando ejecución de plan")
        actions = plan.get("actions", [])
        ctx = ctx or {}

        # Crear grafo
        graph = StateGraph(dict)

        for idx, action in enumerate(actions, start=1):
            node_id = f"node_{idx}"
            graph.add_node(node_id, self._make_node_runner(action, chat_id))

            # Dependencias → si no tiene, ejecuta en paralelo desde start
            if idx > 1 and not self._has_dependency(action, ctx):
                graph.add_edge("start", node_id)
            else:
                prev_node = f"node_{idx-1}" if idx > 1 else "start"
                graph.add_edge(prev_node, node_id)

        if actions:
            graph.add_edge(f"node_{len(actions)}", END)

        compiled = graph.compile()
        logger.debug("[ExecutionEngineService] 🗺 Grafo: %s", graph.nodes)

        # Ejecutar el grafo
        state = compiled.invoke({"ctx": ctx})
        results = state.get("ctx", {})

        logger.info("[ExecutionEngineService] ✅ Ejecución completada")
        return results

    def _make_node_runner(self, action: Dict[str, Any], chat_id: UUID):
        """Crea un runner para cada nodo del grafo."""
        def runner(state: Dict[str, Any]) -> Dict[str, Any]:
            logger.info(f"[ExecutionEngineService] ▶️ Ejecutando acción: {action['type']}")
            ctx = state.get("ctx", {})

            try:
                if action["type"] == "db_query":
                    result = self._execute_db_action(action, ctx)
                elif action["type"] == "api_function":
                    result = self._execute_api_function(action, ctx, chat_id)
                elif action["type"] == "mcp_tool":
                    result = self._execute_mcp_action(action, ctx)
                else:
                    raise ValueError(f"Tipo de acción desconocido: {action['type']}")

                store_key = action.get("store_as") or f"result_{action['type']}"
                ctx[store_key] = result
                logger.info(f"[ExecutionEngineService] ✅ Acción {action['type']} guardada como {store_key}")

            except Exception as e:
                logger.exception(f"[ExecutionEngineService] ❌ Error en acción {action['type']}")
                ctx[f"error_{action['type']}"] = str(e)

            return {"ctx": ctx}

        return runner

    def _execute_db_action(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        proxy_config = None
        if action.get("proxy_id"):
            proxy_config = self.factory.get_proxy_service().get_sql_config(action["proxy_id"])
            logger.debug(f"[ExecutionEngineService] 🌐 Usando proxy SQL: {proxy_config}")

        db_conn = self.factory.get_database_service().get_sql_instance_from_action(action, proxy_config)

        if "sql" in action and action["sql"]:
            sql = action["sql"].format(**ctx)
            return self.factory.get_database_service().execute_sql(db_conn, sql)
        elif "question" in action and action["question"]:
            return self.factory.get_langchain_service().ask_database_question(db_conn, action["question"])
        else:
            raise ValueError("Acción db_query sin 'sql' o 'question'")

    def _execute_api_function(self, action: Dict[str, Any], ctx: Dict[str, Any], chat_id: UUID):
        self.factory.get_usage_service().check_limit()
        params = self._render_params(action.get("params", {}), ctx)

        proxy_config = None
        if action.get("proxy_id"):
            proxy_config = self.factory.get_proxy_service().get_http_config(action["proxy_id"])
            logger.debug(f"[ExecutionEngineService] 🌐 Usando proxy HTTP: {proxy_config}")

        func_id = action["function_id"]

        result, tokens_used, call_id = self.factory.get_executor_service().execute_and_log(
            function_id=func_id,
            params=params,
            proxy=proxy_config
        )

        self.history_service.create_message(
            data={
                "chat_id": chat_id,
                "user_id": self.user_id,
                "role": "function",
                "content": str(result),
                "name": action.get("name"),
                "token_count": tokens_used,
                "is_function_call": True,
                "function_call_id": call_id
            }
        )
        return result

    def _execute_mcp_action(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        """Encapsula la ejecución de herramientas MCP (Make, n8n, etc.)."""
        tool_name = action.get("tool_name")
        params = self._render_params(action.get("params", {}), ctx)

        proxy_config = None
        if action.get("proxy_id"):
            proxy_config = self.factory.get_proxy_service().get_http_config(action["proxy_id"])
            logger.debug(f"[ExecutionEngineService] 🌐 Usando proxy MCP Tool: {proxy_config}")

        return self.factory.get_mcp_integration_service().execute(tool_name, params, proxy_config)

    def _has_dependency(self, action: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        text_to_search = (
            str(action.get("params", "")) +
            str(action.get("sql", "")) +
            str(action.get("question", ""))
        )
        matches = re.findall(r"{{(.*?)}}", text_to_search)
        return bool(matches)

    @staticmethod
    def _render_params(params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        def _replace(value):
            if isinstance(value, str):
                for m in re.findall(r"{{(.*?)}}", value):
                    if m in context:
                        v = context[m]
                        value = value.replace(f"{{{{{m}}}}}", json.dumps(v) if not isinstance(v, str) else str(v))
            return value
        return {k: _replace(v) for k, v in params.items()}
