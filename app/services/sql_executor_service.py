import logging
import sqlalchemy
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import SQLAlchemyError

from app.services.proxy_service import ProxyService
from app.utils.text import truncate_words

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class SQLExecutorService:
    def __init__(self, factory: "ServiceFactory"):
        self.db = factory.db
        self.user = factory.user
        self.factory = factory
        self.proxy_service: ProxyService = factory.get_proxy_service()
        logger.info("[SQLExecutorService] 🧠 Inicializado para user_id=%s", self.user.id)

    def execute_sql(self, database_id: int, sql: str, proxy_id: Optional[int] = None) -> List[dict]:
        logger.info("[SQLExecutorService] ▶ Ejecutando SQL para DB %s: %s",
                    database_id, truncate_words(sql, 20))

        # 🔌 Obtener proxy (si existe)
        proxy = self.proxy_service.get_by_id(proxy_id)
        if not proxy:
            logger.error("[SQLExecutorService] ❌ Proxy ID %s no válido o no encontrado", proxy_id)
            raise ValueError("Proxy no válido o no encontrado")

        try:
            engine = create_engine(
                proxy.base_url,
                connect_args={"options": proxy.auth or {}}
            )
            logger.debug("[SQLExecutorService] 🔗 Conexión creada con base_url=%s", proxy.base_url)
        except Exception as e:
            logger.exception("[SQLExecutorService] ❌ Error construyendo engine con proxy: %s", str(e))
            raise RuntimeError("Error configurando la conexión SQL")

        # ⚙️ Ejecutar SQL
        try:
            with engine.connect() as conn:
                if sql.strip().lower().startswith("select"):
                    result = conn.execute(sqlalchemy.text(sql))
                    rows = [dict(row) for row in result]
                    logger.info("[SQLExecutorService] ✅ SELECT ejecutado, %d filas", len(rows))
                    return rows
                else:
                    res = conn.execute(sqlalchemy.text(sql))
                    conn.commit()
                    logger.info("[SQLExecutorService] ✅ DML ejecutado, %d filas afectadas", res.rowcount)
                    return [{"rows_affected": res.rowcount}]
        except SQLAlchemyError as e:
            logger.exception("[SQLExecutorService] ❌ Error durante la ejecución SQL: %s", str(e))
            raise RuntimeError("Error ejecutando SQL en la base de datos")
