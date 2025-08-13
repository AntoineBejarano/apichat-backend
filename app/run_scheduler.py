# run_scheduler.py

import logging
from app.core.database import get_db_session
from app.core.service_factory import ServiceFactory
from app.services.scheduler_service import SchedulerService
from app.models.user_model import User
from app.models.strategy_model import Strategy
from sqlalchemy.exc import SQLAlchemyError

# ────────────────────────────────
# 🔧 FASE 9: Logging configuration centralizada
# ────────────────────────────────
from app.utils.logging_config import setup_logging

# 🔧 FASE 9: Usar configuración centralizada
setup_logging(level="INFO")
logger = logging.getLogger("run_scheduler")
logger.info("🔧 FASE 9: Scheduler iniciado con logging centralizado")


def main():
    logger.info("🚀 Iniciando ejecución de estrategias CRON programadas...")

    db = get_db_session()

    try:
        # Buscar usuarios que tengan estrategias CRON activas
        users_with_strategies = (
            db.query(User)
            .join(User.strategies)
            .filter(Strategy.trigger_type == "cron", Strategy.is_active == True)
            .distinct()
            .all()
        )
        logger.info("🔍 %d usuarios con estrategias CRON encontradas", len(users_with_strategies))
    except SQLAlchemyError as e:
        logger.exception("❌ Error al consultar usuarios con estrategias: %s", str(e))
        db.close()
        return

    success_count = 0
    error_count = 0

    for user in users_with_strategies:
        logger.info("⚙️ Ejecutando estrategias para user_id=%s", user.id)
        try:
            factory = ServiceFactory(db=db, request=None, user=user)
            scheduler = SchedulerService(factory)
            scheduler.run_cron_strategies()
            success_count += 1
            logger.info("✅ Estrategias ejecutadas correctamente para user_id=%s", user.id)
        except Exception as e:
            error_count += 1
            logger.exception("❌ Error al ejecutar estrategias para user_id=%s: %s", user.id, str(e))

    db.close()

    logger.info("📊 Resultado final: %d usuarios procesados con éxito, %d con errores", success_count, error_count)
    logger.info("🏁 Finalizada ejecución global del scheduler.")


if __name__ == "__main__":
    main()
