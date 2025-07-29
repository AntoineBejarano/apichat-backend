import logging
from datetime import datetime

from sqlalchemy import func
from fastapi import HTTPException

from app.models.token_usage_model import TokenUsage
from app.models.function_call_log_model import FunctionCallLog
from app.models.chat_history_model import ChatHistory
from app.models.function_model import Function
from app.models.subscription_model import Subscription
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

        message_tokens = self.db.query(
            func.coalesce(func.sum(ChatHistory.token_count), 0)
        ).filter(
            ChatHistory.chat.has(user_id=self.user.id)
        ).scalar()

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

    def get_monthly_function_executions(self) -> int:
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self.db.query(FunctionCallLog).filter(
            FunctionCallLog.user_id == self.user.id,
            FunctionCallLog.timestamp >= start_of_month
        ).count()

    def check_plan_limit(self):
        # Validar plan desde subscription activa
        subscription = self.db.query(Subscription).filter(
            Subscription.user_id == self.user.id,
            Subscription.is_active == True
        ).first()

        if not subscription or not subscription.plan:
            logger.warning(f"🚫 Usuario {self.user.id} sin suscripción activa.")
            raise HTTPException(status_code=403, detail="No tienes un plan activo.")

        plan = subscription.plan

        # Validar tokens
        token_limit = getattr(plan, "token_limit", None)
        tokens_used = self.get_monthly_token_usage()

        if token_limit is not None and tokens_used >= token_limit:
            logger.warning(f"⛔ Token limit reached: {tokens_used}/{token_limit} para user {self.user.id}")
            raise HTTPException(status_code=403, detail="Has alcanzado tu límite de tokens mensuales.")

        # Validar ejecuciones de funciones
        max_exec = getattr(plan, "max_executions", None)
        if max_exec is not None:
            executions = self.get_monthly_function_executions()
            if executions >= max_exec:
                logger.warning(f"⛔ Execution limit reached: {executions}/{max_exec} para user {self.user.id}")
                raise HTTPException(status_code=403, detail="Has alcanzado tu límite de ejecuciones mensuales.")

        logger.info(f"✅ Plan OK para usuario {self.user.id} - tokens: {tokens_used}/{token_limit}, execs: {executions if max_exec else '-'}")
