import json
import logging
from uuid import UUID
from typing import Any, Dict, List, Optional, TYPE_CHECKING, NamedTuple
import asyncio

from openai import OpenAI
from fastapi import HTTPException
from pydantic import ValidationError
from langchain.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.utils.text import truncate_words
from app.services.orchestrator_service import PlanModel  # Importamos nuestro modelo Pydantic

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

PROMPT_SQL_HEADER = "### SQL Schema (read‑only)"
PROMPT_FUNCTIONS_HEADER = "### Functions disponibles"
PROMPT_MCP_HEADER = "### MCP Tools disponibles"
PROMPT_SUFFIX = (
    "---\n"
    "Devuelve SIEMPRE la llamada de función `return_plan` y un JSON que cumpla con este esquema:\n"
    f"{PlanModel.schema_json(indent=2)}\n"
    "No incluyas texto fuera del JSON."
)


def json_default(obj):
    """Conversión segura para objetos no serializables por JSON estándar."""
    import uuid
    import datetime
    from decimal import Decimal

    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)  # fallback genérico


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
        "parameters": PlanModel.model_json_schema(),  # Usamos el esquema real de Pydantic
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

    async def plan_actions(
        self,
        chat_id: UUID,
        system_prompt: str,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict] = None,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Genera y valida un plan de acciones estructurado."""
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

            logger.info(
                "[OpenAIService] 📝 Generando plan de acciones (model=%s, temp=%s, msgs=%d)",
                self.model,
                settings.OPENAI_TEMPERATURE,
                len(messages),
            )
            logger.debug("[OpenAIService] Contexto → %s", truncate_words(str(messages), 60))

            payload = {
                "model": self.model,
                "functions": [self.RETURN_PLAN_FUNC],
                "function_call": {"name": "return_plan"},
                "temperature": settings.OPENAI_TEMPERATURE,
                "messages": messages,
            }
            safe_payload = json.loads(json.dumps(payload, default=json_default))

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(**safe_payload)
            )

            self.factory.get_usage_service().register_token_usage(
                model=self.model,
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )

            choice = resp.choices[0]
            if choice.message.get("function_call"):
                args_raw = choice.message["function_call"].get("arguments", "{}")
                try:
                    plan_obj = self.parser.parse(args_raw)
                    logger.info(
                        "[OpenAIService] 📦 Plan validado con %d acciones",
                        len(plan_obj.actions),
                    )
                    return plan_obj.model_dump()
                except ValidationError as ve:
                    logger.error("[OpenAIService] ❌ Error validando plan: %s", ve)
                    raise HTTPException(status_code=500, detail="Plan devuelto no es válido")

            return {"actions": [], "assistant_response": choice.message.get("content", "")}

        except json.JSONDecodeError as decode_err:
            logger.error("[OpenAIService] ❌ JSON inválido: %s", decode_err)
            raise HTTPException(status_code=500, detail="LLM devolvió JSON inválido")
        except Exception as exc:
            logger.exception("[OpenAIService] ❌ Error en plan_actions: %s", exc)
            raise HTTPException(status_code=500, detail=f"OpenAI error: {exc}")

    async def chat_completion(
        self,
        chat_id: UUID,
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

            logger.info(
                "[OpenAIService] 💬 Generando respuesta simple (model=%s, temp=%s, msgs=%d)",
                self.model,
                settings.OPENAI_TEMPERATURE,
                len(messages),
            )
            logger.debug("[OpenAIService] Chat context → %s", truncate_words(str(messages), 60))

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": settings.OPENAI_TEMPERATURE,
            }
            safe_payload = json.loads(json.dumps(payload, default=json_default))

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self.client.chat.completions.create(**safe_payload)
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
