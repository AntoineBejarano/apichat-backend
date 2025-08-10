import logging
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.proxy_model import Proxy
from app.schemas.proxy_schema import ProxyCreate, ProxyUpdate
from app.services.base_service import BaseService  # ✅

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ProxyService(BaseService):
    """Service to manage user proxies and return configurations."""

    def __init__(self, factory: "ServiceFactory") -> None:
        super().__init__(factory)
        logger.info("[ProxyService] ✅ Initialized for user_id=%s", self.user.id)

    # ---------------------------------------------------------------- #
    # CREATE                                                           #
    # ---------------------------------------------------------------- #
    def create(self, data: ProxyCreate) -> Proxy:
        logger.info("[ProxyService] ➕ Creating proxy: «%s»", data.name)
        proxy = Proxy(user_id=self.user.id, **data.model_dump())
        self.db.add(proxy)
        self.db.commit()
        self.db.refresh(proxy)
        logger.debug("[ProxyService] ✅ Proxy created with ID=%s", proxy.id)
        return proxy

    # ---------------------------------------------------------------- #
    # READ                                                             #
    # ---------------------------------------------------------------- #
    def list_all(self) -> List[Proxy]:
        logger.info("[ProxyService] 📄 Listing all proxies for user_id=%s", self.user.id)
        return self.db.query(Proxy).filter_by(user_id=self.user.id).all()

    def get_by_id(self, proxy_id: int) -> Optional[Proxy]:
        logger.debug("[ProxyService] 🔍 Getting proxy_id=%s for user_id=%s", proxy_id, self.user.id)
        return self.db.query(Proxy).filter_by(id=proxy_id, user_id=self.user.id).first()

    def get_by_user_and_database(self, database_name: str) -> Optional[Proxy]:
        logger.info("[ProxyService] 🔍 Getting proxy for user_id=%s and database='%s'", self.user.id, database_name)
        return self.db.query(Proxy).filter_by(user_id=self.user.id, database=database_name).first()

    def get_proxy_for_app(self, app_id: int) -> Optional[Proxy]:
        """Returns the proxy configured for a given app, ensuring it belongs to the user."""
        logger.debug("[ProxyService] 🧭 Getting proxy for app_id=%s", app_id)
        from app.models.app_model import App  # avoid circular import

        app = self.db.query(App).filter(App.id == app_id, App.user_id == self.user.id).first()
        if not app:
            logger.warning("[ProxyService] ❌ App ID %s not found or not owned by user %s", app_id, self.user.id)
            return None

        if not app.proxy_id:
            logger.info("[ProxyService] ℹ️ App ID %s has no proxy configured", app_id)
            return None

        proxy = self.get_by_id(app.proxy_id)
        if not proxy:
            logger.warning("[ProxyService] ❌ Proxy ID %s not found or not owned by user %s", app.proxy_id, self.user.id)
            return None

        logger.info("[ProxyService] ✅ Found proxy ID %s for app ID %s", proxy.id, app.id)
        return proxy

    # ---------------------------------------------------------------- #
    # UPDATE                                                           #
    # ---------------------------------------------------------------- #
    def update(self, proxy_id: int, updates: ProxyUpdate) -> Proxy:
        proxy = self.get_by_id(proxy_id)
        if not proxy:
            logger.error("[ProxyService] ❌ Proxy not found: ID=%s", proxy_id)
            raise ValueError("Proxy not found")

        logger.info("[ProxyService] ♻️ Updating proxy_id=%s", proxy_id)
        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(proxy, field, value)

        proxy.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(proxy)
        logger.debug("[ProxyService] ✅ Proxy updated successfully.")
        return proxy

    # ---------------------------------------------------------------- #
    # DELETE                                                           #
    # ---------------------------------------------------------------- #
    def delete(self, proxy_id: int) -> bool:
        proxy = self.get_by_id(proxy_id)
        if not proxy:
            logger.error("[ProxyService] ❌ Proxy not found for deletion: ID=%s", proxy_id)
            raise ValueError("Proxy not found")

        logger.warning("[ProxyService] 🗑️ Deleting proxy_id=%s", proxy_id)
        self.db.delete(proxy)
        self.db.commit()
        return True

    # ---------------------------------------------------------------- #
    # CONFIG HELPERS                                                   #
    # ---------------------------------------------------------------- #
    def get_proxy_for_user(self, proxy_id: Optional[int]) -> Optional[Proxy]:
        if proxy_id is None:
            logger.info("[ProxyService] 🔌 No proxy_id specified. Continuing without proxy.")
            return None
        proxy = self.get_by_id(proxy_id)
        if not proxy:
            logger.warning("[ProxyService] ⚠️ Proxy_id=%s not owned by user or does not exist", proxy_id)
        return proxy

    def get_http_config(self, proxy_id: Optional[int]) -> Optional[dict]:
        proxy = self.get_proxy_for_user(proxy_id)
        if not proxy:
            return None
        logger.info("[ProxyService] 🛰️ Fetching HTTP config for proxy_id=%s", proxy_id)
        return {
            "base_url": proxy.base_url,
            "headers": proxy.headers or {},
            "auth": proxy.auth or None,
        }

    def get_sql_config(self, proxy_id: Optional[int]) -> Optional[dict]:
        proxy = self.get_proxy_for_user(proxy_id)
        if not proxy:
            return None
        logger.info("[ProxyService] 🗄️ Fetching SQL config for proxy_id=%s", proxy_id)
        return {
            "host": proxy.host,
            "port": proxy.port,
            "username": proxy.username,
            "password": proxy.password,
            "database": proxy.database,
            "dialect": proxy.dialect,
        }
