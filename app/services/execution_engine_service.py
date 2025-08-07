# app/services/execution_engine_service.py
from __future__ import annotations

import json, re, logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from langgraph.graph import StateGraph, START, END

if TYPE_CHECKING:                       # evita import cíclicos en tiempo real
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ExecutionEngineService:
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.user_id: UUID = factory.user.id
        self.history_service = factory.get_chat_history_service()

    # ────────────────────────────────────────────────────────────────
    #   PÚBLICO · Entry-point
    # ────────────────────────────────────────────────────────────────
    def run(
        self,
        plan: Dict[str, Any],
        chat_id: UUID,
        ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        logger.info("[ExecutionEngine] 🚀 Ejecutando plan…")

        actions: List[Dict[str, Any]] = plan.get("actions", [])
        if not actions:
            logger.warning("[ExecutionEngine] Plan sin acciones → nada que ejecutar")
            return {
                "assistant_response": plan.get("assistant_response", ""),
                "variables": {},
            }

        ctx = ctx or {}

        # 1) ────── Construcción dinámica del grafo ──────
        graph = StateGraph(dict)

        for idx, action in enumerate(actions, start=1):
            node_id = f"node_{idx}"
            graph.add_node(node_id, self._build_runner(action, chat_id))

            # edge desde START si no depende de previos
            if idx == 1 or not self._has_dependency(action):
                graph.add_edge(START, node_id)
            else:
                graph.add_edge(f"node_{idx-1}", node_id)

        graph.add_edge(f"node_{len(actions)}", END)

        logger.debug("[ExecutionEngine] 🗺  Grafo con %d nodos", len(graph.nodes))

        # 2) ────── Ejecución ──────
        result_state = graph.compile().invoke({"ctx": ctx})
        variables = result_state["ctx"]

        # 3) ────── Render final de assistant_response ──────
        assistant_resp = self._render_text(
            plan.get("assistant_response", ""),
            variables,
        )

        logger.info("[ExecutionEngine] ✅ Plan ejecutado y respuesta renderizada")
        return {
            "assistant_response": assistant_resp,
            "variables": variables,
        }

    # ────────────────────────────────────────────────────────────────
    #   BUILD DEL RUNNER POR NODO
    # ────────────────────────────────────────────────────────────────
    def _build_runner(self, action: Dict[str, Any], chat_id: UUID):
        def node(state: Dict[str, Any]) -> Dict[str, Any]:
            ctx = state["ctx"]
            logger.info("[ExecutionEngine] ▶️ Acción %s", action["type"])
            try:
                if action["type"] == "db_query":
                    result = self._run_db_query(action, ctx)
                elif action["type"] == "api_function":
                    result = self._run_api_function(action, ctx, chat_id)
                elif action["type"] == "mcp_tool":
                    result = self._run_mcp_tool(action, ctx)
                else:
                    raise ValueError(f"Tipo de acción desconocido: {action['type']}")

                key = action.get("store_as") or f"result_{len(ctx)}"
                ctx[key] = result
                logger.info("[ExecutionEngine] ✅ Resultado guardado en '%s'", key)

                # 👉 Extras normalizados para plantillas: {{key_list}} y {{key_pretty}}
                extras = self._normalize_extras(result)
                for suffix, value in extras.items():
                    ctx[f"{key}_{suffix}"] = value

            except Exception as e:
                logger.exception("[ExecutionEngine] ❌ Error en acción: %s", e)
                ctx[f"error_{action['type']}"] = str(e)

            return {"ctx": ctx}

        return node


    # ────────────────────────────────────────────────────────────────
    #   HANDLERS INDIVIDUALES
    # ────────────────────────────────────────────────────────────────
    # … dentro de class ExecutionEngineService …

    def _run_db_query(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        # 1) Resolver database_id (igual que ya lo tienes)
        db_id = action.get("database_id")
        if not db_id:
            ctx_db_ids = (ctx.get("db_ids") or []) if isinstance(ctx.get("db_ids"), list) else []
            if len(ctx_db_ids) == 1:
                db_id = ctx_db_ids[0]
            else:
                raise ValueError("Acción db_query sin 'database_id' y no se puede inferir uno único")

        # 2) Dialecto
        db_service = self.factory.get_database_service()
        dialect = (db_service.get_dialect_name(db_id) or "").lower()

        # 3) Conexión (directa; si tienes proxy, mantén tu lógica de proxy)
        proxy_cfg = None
        if action.get("proxy_id"):
            proxy_cfg = self.factory.get_proxy_service().get_sql_config(action["proxy_id"])
            logger.warning("[ExecutionEngine] Proxy SQL no soportado en DatabaseService.get_sql_instance; usando conexión directa")

        db_conn = db_service.get_sql_instance(db_id)

        # 4) Ejecutar por SQL directo o pregunta NL → pero reescribiendo si hace falta
        if sql := action.get("sql"):
            rendered_sql = self._render_text(sql, ctx)
            fixed_sql = self._rewrite_sql_for_dialect(rendered_sql, dialect)
            return db_service.execute_sql(db_conn, fixed_sql)

        if question := action.get("question"):
            rendered_q = self._render_text(question, ctx)
            return self.factory.get_langchain_service().ask_database_question(db_conn, rendered_q)

        raise ValueError("Acción db_query sin 'sql' ni 'question'")


    def _run_api_function(self, action: Dict[str, Any], ctx: Dict[str, Any], chat_id: UUID):
        self.factory.get_usage_service().check_limit()
        params = self._render_params(action.get("params", {}), ctx)

        proxy = None
        if action.get("proxy_id"):
            proxy = self.factory.get_proxy_service().get_http_config(action["proxy_id"])

        result, tokens_used, call_id = self.factory.get_executor_service().execute_and_log(
            function_id=action["function_id"],
            params=params,
            proxy=proxy,
        )

        # Registrar en historial como función
        self.history_service.create_message({
            "chat_id": chat_id,
            "user_id": self.user_id,
            "role": "function",
            "content": str(result),
            "name": action.get("tool_name") or "api_function",
            "token_count": tokens_used,
            "is_function_call": True,
            "function_call_id": call_id,
        })
        return result

    def _run_mcp_tool(self, action: Dict[str, Any], ctx: Dict[str, Any]):
        params = self._render_params(action.get("params", {}), ctx)

        proxy = None
        if action.get("proxy_id"):
            proxy = self.factory.get_proxy_service().get_http_config(action["proxy_id"])

        return self.factory.get_mcp_integration_service().execute(
            action["tool_name"], params, proxy
        )

    # ────────────────────────────────────────────────────────────────
    #   HELPERS
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _has_dependency(action: Dict[str, Any]) -> bool:
        return bool(re.findall(r"\{\{(.*?)\}\}", json.dumps(action)))

    @staticmethod
    def _render_text(template: str, variables: Dict[str, Any]) -> str:
        """
        Sustituye {{variable}} y (de forma tolerante) {variable}
        por str(variables[variable]) si existe.
        """
        # 1) {{var}}
        def repl_double(m):
            key = m.group(1).strip()
            return str(variables.get(key, f"{{{{{key}}}}}"))
        out = re.sub(r"\{\{(.*?)\}\}", repl_double, template)

        # 2) {var}  -> solo identificadores simples para evitar romper JSON/SQL
        def repl_single(m):
            key = m.group(1)
            return str(variables[key]) if key in variables else m.group(0)
        out = re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", repl_single, out)

        return out

    def _render_params(self, params: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {k: self._render_text(str(v), ctx) if isinstance(v, str) else v for k, v in params.items()}

    @staticmethod
    def _rewrite_sql_for_dialect(sql: str, dialect: str) -> str:
        s = sql.strip().lower()

        # SHOW TABLES
        if s.startswith("show tables"):
            if dialect in ("postgresql", "postgres", "pg"):
                return (
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema');"
                )
            if dialect in ("sqlite",):
                return "SELECT name AS table_name FROM sqlite_master WHERE type='table';"
            if dialect in ("mssql", "sqlserver"):
                return "SELECT name AS table_name FROM sys.tables;"
            # mysql sí soporta SHOW TABLES → no tocar

        # DESCRIBE <table>
        m = re.match(r"^describe\s+([a-z0-9_\.]+)\s*;?$", s, re.IGNORECASE)
        if m:
            tbl = m.group(1)
            if dialect in ("postgresql", "postgres", "pg"):
                return (
                    "SELECT column_name, data_type, is_nullable "
                    f"FROM information_schema.columns WHERE table_name = '{tbl}';"
                )
            if dialect in ("sqlite",):
                return f"PRAGMA table_info('{tbl}');"
            if dialect in ("mssql", "sqlserver"):
                return (
                    "SELECT c.name AS column_name, t.Name AS data_type, c.is_nullable "
                    "FROM sys.columns c "
                    "INNER JOIN sys.types t ON c.user_type_id = t.user_type_id "
                    f"WHERE c.object_id = OBJECT_ID('{tbl}');"
                )
            # mysql soporta DESCRIBE → no tocar

        # Por defecto, devolver tal cual
        return sql
    
    def _normalize_extras(self, result):
        """
        Si result es una lista de filas (tuplas o dicts), genera:
        - list: lista simple de valores (si son de 1 columna o dict de 1 clave)
        - pretty: string bonito con comas
        """
        items = []
        if isinstance(result, list):
            for r in result:
                if isinstance(r, tuple) or isinstance(r, list):
                    items.append(r[0] if len(r) == 1 else str(r))
                elif isinstance(r, dict):
                    if "table_name" in r:
                        items.append(r["table_name"])
                    elif len(r) == 1:
                        items.append(next(iter(r.values())))
                    else:
                        items.append(str(r))
                else:
                    items.append(str(r))
        else:
            return {}

        pretty = ", ".join(map(str, items)) if items else ""
        return {"list": items, "pretty": pretty}
