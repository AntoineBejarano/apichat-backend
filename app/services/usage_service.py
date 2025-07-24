import logging
from datetime import datetime

from sqlalchemy import func
from fastapi import HTTPException

from app.models.token_usage_model import TokenUsage
from app.models.function_call_log_model import FunctionCallLog
from app.models.chat_history_model import ChatHistory
from app.models.function_model import Function
from app.schemas.usage_schema import UsageOut, FunctionUsage

logger = logging.getLogger(__name__)

class UsageService:
    def __init__(self, factory):
        self.db = factory.db
        self.user = factory.user

    def register_token_usage(self, prompt_tokens: int, completion_tokens: int, model: str):
        total = prompt_tokens + completion_tokens
        logger.info(f"🧾 Registrando uso de tokens: user_id={self.user.id}, model={model}, total={total}")

        usage = TokenUsage(
            user_id=self.user.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            model=model
        )
        self.db.add(usage)
        self.db.commit()

    def get_usage(self) -> UsageOut:
        logger.info(f"📊 Obteniendo uso total de tokens para usuario {self.user.id}")

        # Tokens usados en mensajes normales
        message_tokens = self.db.query(
            func.coalesce(func.sum(ChatHistory.token_count), 0)
        ).filter(
            ChatHistory.chat.has(user_id=self.user.id)
        ).scalar()

        # Llamadas a funciones, usando join con Function
        function_data = self.db.query(
            Function.name.label("function_name"),
            func.count(FunctionCallLog.id).label("count"),
            func.coalesce(func.sum(FunctionCallLog.token_count), 0).label("tokens_used")
        ).join(Function, FunctionCallLog.function_id == Function.id
        ).filter(
            FunctionCallLog.user_id == self.user.id
        ).group_by(
            Function.name
        ).all()

        function_calls = [
            FunctionUsage.model_validate({
                "function_name": row.function_name,
                "count": row.count,
                "tokens_used": row.tokens_used
            })
            for row in function_data
        ]

        total_function_tokens = sum(f.tokens_used for f in function_calls)
        total_tokens = (message_tokens or 0) + total_function_tokens

        return UsageOut(
            total_tokens=total_tokens,
            function_calls=function_calls
        )

    def get_monthly_token_usage(self) -> int:
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        usage = self.db.query(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0)
        ).filter(
            TokenUsage.user_id == self.user.id,
            TokenUsage.timestamp >= start_of_month
        ).scalar()
        return usage or 0

    def check_plan_limit(self):
        if not self.user.plan:
            logger.warning(f"🚫 User {self.user.id} has no assigned plan.")
            raise HTTPException(status_code=403, detail="You don't have an active plan.")

        token_limit = getattr(self.user.plan, "token_limit", None)
        if token_limit is None:
            logger.info(f"✅ User {self.user.id} has no token limit.")
            return

        total_used = self.db.query(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0)
        ).filter(
            TokenUsage.user_id == self.user.id
        ).scalar() or 0

        if total_used >= token_limit:
            logger.warning(f"⛔ User {self.user.id} reached the plan limit of {token_limit} tokens.")
            raise HTTPException(status_code=403, detail="You have reached your token limit.")
        else:
            logger.info(f"🟢 User {self.user.id} has used {total_used}/{token_limit} tokens.")
