import logging
import requests
from fastapi import HTTPException
from typing import List, Dict, Any

from app.models.app_model import App
from app.schemas.app_schema import AppCreate, AppUpdate
from app.schemas.function_schema import FunctionSchema  # Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class AppService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        logger.info(f"[AppService] ✅ Initialized for user_id={self.user_id}")

    # ----------------------------------------------------------------
    # CREATE
    # ----------------------------------------------------------------
    def create(self, app_data: AppCreate) -> App:
        logger.info(f"[AppService] ➕ Creating new App for user_id={self.user_id}")

        # If a proxy_id is provided, ensure it belongs to the user
        if app_data.proxy_id:
            proxy = self.factory.get_proxy_service().get_by_id(app_data.proxy_id)
            if not proxy:
                logger.warning(f"[AppService] ❌ Invalid proxy_id={app_data.proxy_id} for user_id={self.user_id}")
                raise HTTPException(status_code=400, detail="Invalid proxy_id")

        new_app = App(**app_data.dict(), user_id=self.user_id)
        self.db.add(new_app)
        self.db.commit()
        self.db.refresh(new_app)
        logger.info(f"[AppService] ✅ App created with ID={new_app.id}")
        return new_app

    # ----------------------------------------------------------------
    # READ
    # ----------------------------------------------------------------
    def get_all(self) -> List[App]:
        logger.info(f"[AppService] 📦 Getting all Apps for user_id={self.user_id}")
        return self.db.query(App).filter(App.user_id == self.user_id).all()

    def get_by_id(self, app_id: int) -> App:
        logger.info(f"[AppService] 🔍 Fetching App ID={app_id} for user_id={self.user_id}")
        app = self.db.query(App).filter(App.id == app_id, App.user_id == self.user_id).first()
        if not app:
            logger.error(f"[AppService] ❌ App ID={app_id} not found for user_id={self.user_id}")
            raise HTTPException(status_code=404, detail="App not found")
        return app

    # ----------------------------------------------------------------
    # UPDATE
    # ----------------------------------------------------------------
    def update(self, app_id: int, app_data: AppUpdate) -> App:
        logger.info(f"[AppService] ✏️ Updating App ID={app_id} for user_id={self.user_id}")
        app = self.get_by_id(app_id)

        # If proxy_id is being updated, validate ownership
        if app_data.proxy_id is not None:
            proxy = self.factory.get_proxy_service().get_by_id(app_data.proxy_id)
            if not proxy:
                logger.warning(f"[AppService] ❌ Invalid proxy_id={app_data.proxy_id} for user_id={self.user_id}")
                raise HTTPException(status_code=400, detail="Invalid proxy_id")

        for field, value in app_data.dict(exclude_unset=True).items():
            setattr(app, field, value)

        self.db.commit()
        self.db.refresh(app)
        logger.info(f"[AppService] ✅ App ID={app.id} updated")
        return app

    # ----------------------------------------------------------------
    # DELETE
    # ----------------------------------------------------------------
    def delete(self, app_id: int) -> dict:
        logger.info(f"[AppService] 🗑️ Deleting App ID={app_id} for user_id={self.user_id}")
        app = self.get_by_id(app_id)
        self.db.delete(app)
        self.db.commit()
        logger.info(f"[AppService] ✅ App ID={app_id} deleted")
        return {"detail": "App deleted successfully"}

    # ----------------------------------------------------------------
    # 🔌 GET FUNCTIONS (Custom or MCP)
    # ----------------------------------------------------------------
    def get_functions(self, app: App) -> List[Dict[str, Any]]:
        """
        Returns the list of functions associated with the given App.
        • Custom → from local DB
        • MCP → from external endpoint
        """
        logger.info(f"[AppService] 🧠 Getting functions for app {app.name} (id={app.id})")

        if app.mcp_integration_id:
            try:
                integration = app.mcp_integration
                if not integration or not integration.get_functions_url:
                    logger.warning(f"[AppService] 🚫 MCP integration misconfigured for app_id={app.id}")
                    raise HTTPException(status_code=400, detail="MCP integration misconfigured")

                url = integration.get_functions_url
                logger.debug(f"[AppService] 🌐 Fetching MCP functions from {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                functions = response.json()
                logger.info(f"[AppService] ✅ Retrieved {len(functions)} functions from MCP for app_id={app.id}")
                return functions

            except Exception as e:
                logger.exception(f"[AppService] ❌ Failed to fetch MCP functions for app_id={app.id}")
                raise HTTPException(status_code=502, detail="Failed to fetch MCP functions")

        # Custom App: use FunctionService
        logger.debug(f"[AppService] 🔧 Delegating to FunctionService for app_id={app.id}")
        return self.factory.get_function_service().get_by_app(app.id)
