import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import openai
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.utils.text import truncate_words

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

# ---------------------------------------------------------------------------
# Config & logger
# ---------------------------------------------------------------------------
openai.api_key = settings.OPENAI_API_KEY
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cabeceras y sufijo fijos (no-parametrizables en .env) ----------------------
# ---------------------------------------------------------------------------
PROMPT_SQL_HEADER = "### SQL Schema (read‑only)"
PROMPT_FUNCTIONS_HEADER = "### Functions disponibles"
PROMPT_MCP_HEADER = "### MCP Tools disponibles"
PROMPT_SUFFIX = (
    "---\n"
    "Devuelve SIEMPRE la llamada de función `return_plan` y un JSON con `actions[]` "
    "y `assistant_response`. No incluyas texto fuera del JSON."
)


class OpenAIService:
    """Servicio que envuelve la API de OpenAI y genera *planes de acción*.

    *Las cabeceras y el sufijo son constantes en el código para evitar
    modificaciones accidentales; el único texto dinámico es el
    `system_prompt` que llega por petición.*
    """

    RETURN_PLAN_FUNC: Dict[str, Any] = {
        "name": "return_plan",
        "description": (
            "Devuelve el plan de acciones (array `actions`) y el texto final "
            "(`assistant_response`) que el asistente mostrará al usuario."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "description": "Pasos secuenciales a realizar antes de responder al usuario.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["db_query", "api_function", "mcp_tool"],
                            },
                            "sql": {"type": "string"},
                            "function_id": {"type": "integer"},
                            "tool_name": {"type": "string"},
                            "params": {"type": "object"},
                            "store_as": {"type": "string"},
                        },
                        "required": ["type"],
                    },
                },
                "assistant_response": {
                    "type": "string",
                    "description": "Respuesta final que verá el usuario.",
                },
            },
            "required": ["actions", "assistant_response"],
        },
    }

    # ------------------------------------------------------------------
    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user = factory.user
        self.history_service = factory.get_chat_history_service()
        self.function_service = factory.get_function_service()
        self.model = settings.OPENAI_MODEL

        logger.info("[OpenAIService] Instanciado para user=%s", self.user.email)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    async def plan_actions(
        self,
        user_id: int,
        system_prompt: str,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict],
    ) -> Dict[str, Any]:
        """Genera y devuelve un *plan de acciones* estructurado."""
        try:
            # 1️⃣  Historial limitado (últimos 8)
            history = self.history_service.get_chat_history(user_id)[-8:]
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(
                        system_prompt, db_schema, available_functions, available_mcp_tools
                    ),
                },
                *[msg.model_dump() for msg in history],
                user_message.model_dump(),
            ]

            logger.debug("[OpenAIService] Contexto · %s", truncate_words(str(messages), 60))

            # 2️⃣  Llamada ChatCompletion
            resp = openai.ChatCompletion.create(
                model=self.model,
                functions=[self.RETURN_PLAN_FUNC],
                function_call={"name": "return_plan"},
                temperature=settings.OPENAI_TEMPERATURE,
                messages=messages,
            )

            choice = resp.choices[0]
            if choice.message.get("function_call"):
                args_raw = choice.message["function_call"].get("arguments", "{}")
                plan = json.loads(args_raw)
                logger.info(
                    "[OpenAIService] Plan recibido con %d acciones", len(plan.get("actions", []))
                )
                return plan

            # Fallback: el modelo no llamó a la función
            return {
                "actions": [],
                "assistant_response": choice.message.get(
                    "content", "Lo siento, no pude entender la petición."
                ),
            }

        except json.JSONDecodeError as decode_err:
            logger.error("[OpenAIService] JSON inválido: %s", decode_err)
            raise HTTPException(status_code=500, detail="LLM devolvió JSON inválido")
        except Exception as exc:
            logger.exception("[OpenAIService] ❌ Error en plan_actions: %s", exc)
            raise HTTPException(status_code=500, detail=f"OpenAI error: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_system_prompt(
        self,
        custom_prompt: str,
        db_schema: Optional[str],
        functions: List[Function],
        mcp_tools: Optional[dict],
    ) -> str:
        """Construye el prompt de sistema combinando:
        - Prompt del agente (dinámico)
        - Resumen de esquema SQL
        - Lista de funciones del App
        - Lista de tools MCP
        - Sufijo con la instrucción JSON
        """
        parts: List[str] = [custom_prompt.strip() or "You are a helpful assistant."]

        if db_schema:
            parts.append(f"{PROMPT_SQL_HEADER}\n" + db_schema[:600])

        if functions:
            fx_lines = [f"• {f.name}: {truncate_words(f.description or '', 12)}" for f in functions]
            parts.append(f"{PROMPT_FUNCTIONS_HEADER}\n" + "\n".join(fx_lines))

        if mcp_tools and mcp_tools.get("tools"):
            tool_lines = [f"• {t['name']}: {t.get('description', '')}" for t in mcp_tools["tools"]]
            parts.append(f"{PROMPT_MCP_HEADER}\n" + "\n".join(tool_lines))

        parts.append(PROMPT_SUFFIX)
        return "\n\n".join(parts)
