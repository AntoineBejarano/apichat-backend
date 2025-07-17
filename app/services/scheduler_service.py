import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from croniter import croniter
from fastapi import HTTPException

from app.models.strategy_model import Strategy
from app.services.function_executor_service import FunctionExecutor

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db: Session = factory.db
        self.user = factory.user
        logger.info("[SchedulerService] ✅ Inicializado para user_id=%s", self.user.id)

    def run_cron_strategies(self):
        """
        Escanea todas las estrategias activas con trigger_type='cron',
        y ejecuta las que deben activarse en este momento según croniter.
        """
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        logger.info("[SchedulerService] 🕒 Ejecutando chequeo de estrategias CRON (%s)", now.isoformat())

        # Buscar estrategias activas con trigger_type = 'cron'
        strategies = (
            self.db.query(Strategy)
            .filter(
                Strategy.trigger_type == "cron",
                Strategy.is_active == True
            )
            .all()
        )

        logger.info("[SchedulerService] 🔍 Encontradas %d estrategias cron activas", len(strategies))

        for strategy in strategies:
            user_id = str(strategy.user_id)
            cron_expr = (strategy.trigger_config or {}).get("cron")

            if not cron_expr:
                logger.warning("[SchedulerService] ⚠️ Estrategia '%s' sin cron válido — user_id=%s", strategy.name, user_id)
                continue

            try:
                last_run = strategy.last_run_at or datetime(1970, 1, 1, tzinfo=timezone.utc)
                iter = croniter(cron_expr, last_run)
                next_time = iter.get_next(datetime)

                logger.debug("[SchedulerService] ⏭️ Próxima ejecución para '%s': %s", strategy.name, next_time.isoformat())

                if next_time <= now:
                    logger.info("[SchedulerService] ✅ Ejecutando estrategia '%s' para user_id=%s", strategy.name, user_id)
                    self._execute_strategy(strategy)
                    strategy.last_run_at = now
                    strategy.status = "success"
                    self.db.commit()
                else:
                    logger.debug("[SchedulerService] ⏳ Aún no toca ejecutar '%s'", strategy.name)

            except Exception as e:
                logger.exception("[SchedulerService] ❌ Error procesando estrategia '%s': %s", strategy.name, str(e))
                strategy.status = "error"
                self.db.commit()

    def _execute_strategy(self, strategy: Strategy):
        """
        Ejecuta los pasos definidos en una estrategia de forma secuencial.
        """
        logger.info("[SchedulerService] ▶ Ejecutando pasos de estrategia '%s'", strategy.name)
        executor = FunctionExecutor(self.factory)

        for i, step in enumerate(strategy.steps):
            function_id = step.get("function_id")
            inputs = step.get("inputs", {})

            if not function_id:
                logger.warning("[SchedulerService] ⚠️ Paso %d sin function_id en estrategia '%s'", i, strategy.name)
                continue

            try:
                logger.info("[SchedulerService] 🔁 Ejecutando paso %d: función %s", i + 1, function_id)
                result = executor.execute_by_id(function_id, inputs)
                logger.info("[SchedulerService] ✅ Paso %d completado con resultado: %s", i + 1, result)
            except Exception as e:
                logger.error("[SchedulerService] ❌ Error en paso %d: %s", i + 1, str(e))
                raise HTTPException(status_code=500, detail=f"Error en paso {i + 1}: {str(e)}")
