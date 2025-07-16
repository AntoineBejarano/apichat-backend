import openai
import logging
from typing import List, Dict, Any, Optional
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.models.function_model import Function
from app.core.servicefactory import ServiceFactory

logger = logging.getLogger(__name__)
openai.api_key = settings.OPENAI_API_KEY


class OpenAIService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db
        self.user = factory.user
        self.langchain_service = factory.get_langchain_service()
        self.model = settings.OPENAI_MODEL
        self.history_service = factory.get_chat_history_service()
        self.function_service = factory.get_function_service()
        self.executor_service = factory.get_executor_service()
        self.database_service = factory.get_database_service()

    async def chat_with_openai(
        self,
        message: Dict[str, Any],
        group_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            history = self.history_service.get_chat_history(self.user.id)
            user_message = ChatMessage(**message)
            self.history_service.append_to_history(self.user.id, user_message)

            messages = [msg.model_dump() for msg in history] + [user_message.model_dump()]
            functions: List[Function] = self.function_service.get_functions_by_group(group_id)
            openai_functions = [f.to_openai_format() for f in functions]

            logger.info(f"[{self.user.email}] Sending message to OpenAI with {len(openai_functions)} functions")
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                functions=openai_functions,
                function_call="auto"
            )

            choice = response.choices[0]
            message = choice.message

            if choice.finish_reason == "function_call":
                fn_name = message["function_call"]["name"]
                arguments = message["function_call"].get("arguments", "{}")

                try:
                    result = self.executor_service.execute_by_name(self.user.id, fn_name, arguments)
                    result_msg = {
                        "role": "function",
                        "name": fn_name,
                        "content": str(result)
                    }
                    self.history_service.append_to_history(self.user.id, ChatMessage(**result_msg))
                    return {"choices": [{"message": result_msg}]}
                except Exception as e:
                    logger.exception(f"❌ Error ejecutando función {fn_name}: {e}")
                    error_msg = {
                        "role": "assistant",
                        "content": f"❌ Error ejecutando la función: {str(e)}"
                    }
                    self.history_service.append_to_history(self.user.id, ChatMessage(**error_msg))
                    return {"choices": [{"message": error_msg}]}

            self.history_service.append_to_history(self.user.id, ChatMessage(**message))
            return response.to_dict()

        except Exception as e:
            logger.exception(f"❌ Error general en chat_with_openai: {str(e)}")
            return {"choices": [{"message": {"role": "assistant", "content": f"❌ Error interno: {str(e)}"}}]}

    async def detect_intent_and_respond(
        self,
        db_id: Optional[int],
        app_id: Optional[int],
        system_prompt: str,
        message: ChatMessage
    ) -> Dict[str, Any]:
        try:
            history = self.history_service.get_chat_history(self.user.id)
            self.history_service.append_to_history(self.user.id, message)
            messages = [{"role": "system", "content": system_prompt}] + \
                       [msg.model_dump() for msg in history] + [message.model_dump()]

            db_conn = self.database_service.get_sql_database_by_id(db_id) if db_id else None
            functions = self.function_service.get_functions_by_app_id(app_id) if app_id else []

            logger.info(f"[{self.user.email}] detect_intent_and_respond con {len(functions)} funciones y prompt: {system_prompt}")
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                functions=[f.to_openai_format() for f in functions],
                function_call="auto"
            )

            choice = response.choices[0]
            ai_msg = choice.message

            if ai_msg.get("function_call"):
                fn_name = ai_msg["function_call"]["name"]
                arguments = ai_msg["function_call"].get("arguments", "{}")
                try:
                    result = self.executor_service.execute_by_name(self.user.id, fn_name, arguments)
                    result_msg = {
                        "role": "function",
                        "name": fn_name,
                        "content": str(result)
                    }
                    self.history_service.append_to_history(self.user.id, ChatMessage(**result_msg))
                    return result_msg
                except Exception as e:
                    logger.exception(f"❌ Error ejecutando función {fn_name}: {str(e)}")
                    return {"role": "assistant", "content": f"❌ Error ejecutando función: {str(e)}"}

            if db_conn and "SELECT" in ai_msg.get("content", "").upper():
                try:
                    result = self.langchain_service.ask_database_question(db_conn, ai_msg["content"])
                    return {"role": "db", "content": result}
                except Exception as e:
                    logger.exception(f"❌ Error al consultar DB: {str(e)}")
                    return {"role": "assistant", "content": f"❌ Error en consulta DB: {str(e)}"}

            self.history_service.append_to_history(self.user.id, ChatMessage(**ai_msg))
            return ai_msg

        except Exception as e:
            logger.exception(f"❌ Error general en detect_intent_and_respond: {str(e)}")
            return {"role": "assistant", "content": f"❌ Error interno: {str(e)}"}
