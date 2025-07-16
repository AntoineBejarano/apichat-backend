"""
Servicio: ProxyService
Responsable de CRUD y utilidades para objetos Proxy
(agrupan configuración común ―base URL, cabeceras, auth― reutilizada por varias Functions).
"""

import logging
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.proxy_model import Proxy
from app.schemas.proxy_schema import ProxyCreate, ProxyUpdate

if TYPE_CHECKING:  # evita importaciones circulares en runtime
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ProxyService:
    """CRUD de proxies por usuario."""

    # ------------------------------------------------------------------ #
    # Constructor                                                        #
    # ------------------------------------------------------------------ #
    def __init__(self, factory: "ServiceFactory") -> None:
        self.db: Session = factory.db
        self.user_id: int = factory.user.id
        logger.info("[ProxyService] Inicializado para user_id=%s", self.user_id)

    # ------------------------------------------------------------------ #
    # CREATE                                                             #
    # ------------------------------------------------------------------ #
    def create(self, data: ProxyCreate) -> Proxy:
        logger.info("[ProxyService] ➕ Creando proxy «%s»", data.name)
        proxy = Proxy(
            user_id=self.user_id,
            **data.model_dump(),              # name, base_url, headers, auth, active
        )
        self.db.add(proxy)
        self.db.commit()
        self.db.refresh(proxy)
        return proxy

    # ------------------------------------------------------------------ #
    # READ                                                               #
    # ------------------------------------------------------------------ #
    def list_all(self) -> List[Proxy]:
        """Devuelve todos los proxies del usuario."""
        return (
            self.db.query(Proxy)
            .filter(Proxy.user_id == self.user_id)
            .all()
        )

    def get_by_id(self, proxy_id: int) -> Optional[Proxy]:
        """Recupera un proxy concreto si pertenece al usuario."""
        return (
            self.db.query(Proxy)
            .filter_by(id=proxy_id, user_id=self.user_id)
            .first()
        )

    # ------------------------------------------------------------------ #
    # UPDATE                                                             #
    # ------------------------------------------------------------------ #
    def update(self, proxy_id: int, updates: ProxyUpdate) -> Proxy:
        proxy = self.get_by_id(proxy_id)
        if not proxy:
            raise ValueError("Proxy not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(proxy, field, value)
        proxy.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(proxy)
        return proxy

    # ------------------------------------------------------------------ #
    # DELETE                                                             #
    # ------------------------------------------------------------------ #
    def delete(self, proxy_id: int) -> bool:
        proxy = self.get_by_id(proxy_id)
        if not proxy:
            raise ValueError("Proxy not found")

        self.db.delete(proxy)
        self.db.commit()
        return True
