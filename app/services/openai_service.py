# app/services/openai_service.py
import json
import logging
import asyncio
import re
from uuid import UUID
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING, NamedTuple

from fastapi import HTTPException
from openai import OpenAI
from pydantic import ValidationError
from langchain.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryOut
from app.models.function_model import Function
from app.utils.text import truncate_words
from app.schemas.plan_schema import PlanModel  # ✅ evitar ciclos

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────
#   Constantes de prompt
# ──────────────────────────────────────────────────────
PROMPT_SQL_HEADER = "### SQL Schema (read-only)"
PROMPT_SQL_DIALECT_HEADER = "### SQL Dialect"
PROMPT_FUNCTIONS_HEADER = "### Functions disponibles"
PROMPT_MCP_HEADER = "### MCP Tools disponibles"

PLANNER_SYSTEM_PROMPT_PREFIX = (
    "Tu tarea es actuar como un asistente conversacional inteligente capaz de generar planes de acción en formato JSON "
    "usando herramientas como funciones (`api_function`), consultas a base de datos (`db_query`) o herramientas MCP (`mcp_tool`).\n\n"
    "Cuando el mensaje del usuario sea trivial, social o no requiera ejecutar ninguna acción "
    "(por ejemplo: \"Hola\", \"¿Qué tal estás?\", \"¿Estás ahí?\", \"Gracias\"), responde de manera breve, amable y adaptándote al idioma del usuario. "
    "No generes un plan en estos casos.\n\n"
    "Cuando el mensaje del usuario implique resolver una necesidad, tomar decisiones complejas o acceder a datos, "
    "responde primero con: \"Estoy generando tu plan, dame un segundo...\" (en el idioma del usuario) y después devuelve un JSON con el plan "
    "llamando a la función `return_plan`. No incluyas texto fuera del JSON cuando generes un plan.\n\n"
    "Si el mensaje del usuario es ambiguo, pide educadamente que aclare su intención.\n\n"
    "Si se proporciona un dialecto SQL, RESPÉTALO estrictamente y evita comandos de otros dialectos."
    "Cuando insertes variables del contexto en `assistant_response`, "
    "usa SIEMPRE el formato {{nombre_variable}} (doble llave). No uses {variable}.\n"
)

PROMPT_SUFFIX = (
    "---\n"
    "Devuelve SIEMPRE la llamada de función `return_plan` y un JSON que cumpla con este esquema:\n"
    f"{json.dumps(PlanModel.model_json_schema(), indent=2)}\n"
    "No incluyas texto fuera del JSON."
)

# *Hints* mínimos por dialecto (para evitar SHOW TABLES en Postgres, etc.)
_DIALECT_HINTS: Dict[str, str] = {
    "postgresql": (
        "Usa SQL válido para PostgreSQL. "
        "Ejemplo para listar tablas: "
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema NOT IN ('pg_catalog','information_schema');"
    ),
    "mysql": "Usa SQL válido para MySQL. Ejemplo para listar tablas: SHOW TABLES;",
    "mssql": "Usa SQL válido para SQL Server. Ejemplo para listar tablas: SELECT name FROM sys.tables;",
    "sqlite": "Usa SQL válido para SQLite. Ejemplo para listar tablas: SELECT name FROM sqlite_master WHERE type='table';",
}

# ──────────────────────────────────────────────────────
#   Utilidades
# ──────────────────────────────────────────────────────
def _json_default(obj: Any):
    import uuid, datetime
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def _extract_dialect(db_schema: Optional[str]) -> Optional[str]:
    """
    Busca en el schema una línea tipo:  -- DIALECT: postgresql
    y devuelve 'postgresql' si existe.
    """
    if not db_schema:
        return None
    m = re.search(r"^\s*--\s*DIALECT:\s*([A-Za-z0-9_+-]+)\s*$", db_schema, re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1).strip().lower()
    return None

class CompletionResult(NamedTuple):
    content: str
    token_count: int

# ──────────────────────────────────────────────────────
#   Servicio principal
# ──────────────────────────────────────────────────────
class OpenAIService:
    RETURN_PLAN_FUNC: Dict[str, Any] = {
        "name": "return_plan",
        "description": (
            "Devuelve el plan de acciones (`actions`) y el texto final "
            "(`assistant_response`) que el asistente mostrará al usuario."
        ),
        "parameters": PlanModel.model_json_schema(),
    }

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user = factory.user

        self.history_service = factory.get_chat_history_service()
        self.function_service = factory.get_function_service()

        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.parser = PydanticOutputParser(pydantic_object=PlanModel)

        logger.info("[OpenAIService] 🚀 Instanciado para user=%s", self.user.email)

    # ──────────────────────────────────────────────────
    #   PLAN ACTIONS
    # ──────────────────────────────────────────────────
    async def plan_actions(
        self,
        chat_id: UUID,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        # 1) Contexto histórico
        if history is None:
            msgs = self.history_service.get_history(chat_id)[-8:]
            history = [m.model_dump() for m in msgs]

        # 2) Construcción de mensajes
        messages = [
            {
                "role": "system",
                "content": self._build_combined_planner_prompt(
                    db_schema, available_functions, available_mcp_tools
                ),
            },
            *history,
            user_message.model_dump(),
        ]

        logger.info("[OpenAIService] 📝 Generando plan (msgs=%d)", len(messages))
        logger.debug("🔹 Contexto → %s", truncate_words(str(messages), 60))

        payload = {
            "model": self.model,
            "functions": [self.RETURN_PLAN_FUNC],
            "function_call": "auto",               # ← el modelo decide
            "temperature": settings.OPENAI_TEMPERATURE,
            "messages": messages,
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

        # 3) Llamada asíncrona
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, lambda: self.client.chat.completions.create(**safe)
        )

        self.factory.get_usage_service().register_token_usage(
            model=self.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )

        choice = resp.choices[0]
        function_call = getattr(choice.message, "function_call", None)
        content = (choice.message.content or "").strip()

        # 4) Interpretación de la respuesta
        if function_call:
            args_raw = function_call.arguments or "{}"
            try:
                plan_obj = self.parser.parse(args_raw)
                logger.info("[OpenAIService] ✅ Plan validado (%d acciones)", len(plan_obj.actions))
                return plan_obj.model_dump()
            except ValidationError as ve:
                logger.error("❌ Plan inválido: %s", ve)
                raise HTTPException(500, "Plan devuelto no es válido")

        if content:
            logger.info("[OpenAIService] ✅ Respuesta simple generada")
            return {"actions": [], "assistant_response": content}

        logger.warning("[OpenAIService] ⚠️ Sin respuesta del modelo")
        return {
            "actions": [],
            "assistant_response": (
                "Disculpa, no he entendido tu mensaje. ¿Podrías reformularlo?"
            ),
        }

    # ──────────────────────────────────────────────────
    #   CHAT COMPLETION (simple)
    # ──────────────────────────────────────────────────
    async def chat_completion(
        self,
        chat_id: UUID,
        system_prompt: str,
        user_message: ChatMessage,
    ) -> CompletionResult:

        history = self.history_service.get_history(chat_id)[-8:]
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            *[ChatHistoryOut.model_validate(m).model_dump() for m in history],
            user_message.model_dump(),
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.OPENAI_TEMPERATURE,
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None, lambda: self.client.chat.completions.create(**safe)
        )

        self.factory.get_usage_service().register_token_usage(
            model=self.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )

        choice = resp.choices[0]
        return CompletionResult(
            content=choice.message.content or "",
            token_count=resp.usage.total_tokens,
        )

    # ──────────────────────────────────────────────────
    #   Prompt builder
    # ──────────────────────────────────────────────────
    def _build_combined_planner_prompt(
        self,
        db_schema: Optional[str],
        functions: List[Function],
        mcp_tools: Optional[dict],
    ) -> str:

        parts: List[str] = [PLANNER_SYSTEM_PROMPT_PREFIX.strip()]

        # Extraer dialecto del schema (si viene anotado)
        dialect = _extract_dialect(db_schema)
        if dialect:
            logger.info("[OpenAIService] 🎛️ Dialecto detectado en schema: %s", dialect)
            hint = _DIALECT_HINTS.get(dialect, f"Usa SQL válido para {dialect}.")
            parts.append(f"{PROMPT_SQL_DIALECT_HEADER}\nDialect: {dialect}\n{hint}")

        # Prompt del agente (si existe)
        try:
            agent_prompt = self.factory.get_agent_service().get_prompt_from_history()
            if agent_prompt:
                parts.append(agent_prompt.strip())
        except Exception as e:
            logger.warning("⚠️ No se pudo obtener prompt de agente: %s", e)

        # Esquema SQL
        if db_schema:
            parts.append(f"{PROMPT_SQL_HEADER}\n{db_schema[:600]}")

        # Funciones disponibles
        if functions:
            fx = [f"• {f.name}: {truncate_words(f.description or '', 12)}"
                  for f in functions]
            parts.append(f"{PROMPT_FUNCTIONS_HEADER}\n" + "\n".join(fx))

        # Herramientas MCP
        if mcp_tools and mcp_tools.get("tools"):
            tl = [f"• {t['name']}: {t.get('description', '')}"
                  for t in mcp_tools["tools"]]
            parts.append(f"{PROMPT_MCP_HEADER}\n" + "\n".join(tl))

        parts.append(PROMPT_SUFFIX)
        return "\n\n".join(parts)
