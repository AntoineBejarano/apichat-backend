import json
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, NamedTuple
import asyncio

from openai import OpenAI
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.utils.text import truncate_words

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

PROMPT_SQL_HEADER = "### SQL Schema (read‑only)"
PROMPT_FUNCTIONS_HEADER = "### Functions disponibles"
PROMPT_MCP_HEADER = "### MCP Tools disponibles"
PROMPT_SUFFIX = (
    "---\n"
    "Devuelve SIEMPRE la llamada de función `return_plan` y un JSON con `actions[]` "
    "y `assistant_response`. No incluyas texto fuera del JSON."
)

class CompletionResult(NamedTuple):
    content: str
    token_count: int

class OpenAIService:
    """Servicio que envuelve la API de OpenAI y genera planes de acción o chat libre."""

    RETURN_PLAN_FUNC: Dict[str, Any] = {
        "name": "return_plan",
        "description": (
            "Devuelve el plan de acciones (`actions`) y el texto final "
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

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user = factory.user
        self.history_service = factory.get_chat_history_service()
        self.function_service = factory.get_function_service()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        logger.info("[OpenAIService] Instanciado para user=%s", self.user.email)

    async def plan_actions(
        self,
        chat_id: int,
        system_prompt: str,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Genera y devuelve un plan de acciones estructurado."""
        try:
            if history is None:
                history_msgs = self.history_service.get_history(chat_id)[-8:]
                history = [msg.model_dump() for msg in history_msgs]

            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(
                        system_prompt, db_schema, available_functions, available_mcp_tools
                    ),
                },
                *history,
                user_message.model_dump(),
            ]

            logger.debug("[OpenAIService] Contexto · %s", truncate_words(str(messages), 60))

            # Ejecutar llamada síncrona en un executor para no bloquear
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    functions=[self.RETURN_PLAN_FUNC],
                    function_call={"name": "return_plan"},
                    temperature=settings.OPENAI_TEMPERATURE,
                    messages=messages,
                )
            )

            self.factory.get_usage_service().register_token_usage(
                model=self.model,
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )

            choice = resp.choices[0]
            if choice.message.get("function_call"):
                args_raw = choice.message["function_call"].get("arguments", "{}")
                plan = json.loads(args_raw)
                logger.info(
                    "[OpenAIService] Plan recibido con %d acciones", len(plan.get("actions", []))
                )
                return plan

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

    async def chat_completion(
        self,
        chat_id: int,
        system_prompt: str,
        user_message: ChatMessage,
    ) -> CompletionResult:
        """Chat libre sin funciones. Devuelve contenido + tokens usados."""
        try:
            history = self.history_service.get_history(chat_id)[-8:]
            messages = [
                {"role": "system", "content": system_prompt or "You are a helpful assistant."},
                *[msg.model_dump() for msg in history],
                user_message.model_dump(),
            ]

            logger.debug("[OpenAIService] Chat context · %s", truncate_words(str(messages), 60))

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=settings.OPENAI_TEMPERATURE,
                )
            )

            self.factory.get_usage_service().register_token_usage(
                model=self.model,
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )

            choice = resp.choices[0]
            content = choice.message.get("content", "")
            token_count = getattr(resp.usage, "total_tokens", None) or 0
            return CompletionResult(content=content, token_count=token_count)

        except Exception as exc:
            logger.exception("[OpenAIService] ❌ Error en chat_completion: %s", exc)
            raise HTTPException(status_code=500, detail=f"OpenAI chat error: {exc}")

    def _build_system_prompt(
        self,
        custom_prompt: str,
        db_schema: Optional[str],
        functions: List[Function],
        mcp_tools: Optional[dict],
    ) -> str:
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
