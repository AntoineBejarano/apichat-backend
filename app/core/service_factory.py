import logging
from typing import Optional, TYPE_CHECKING
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.user_model import User
from app.models.session_model import Session as SessionModel

if TYPE_CHECKING:
    from app.services.agent_service import AgentService
    from app.services.function_service import FunctionService
    from app.services.integration_service import IntegrationService
    from app.services.database_service import DatabaseService
    from app.services.openai_service import OpenAIService
    from app.services.orchestrator_service import OrchestratorService
    from app.services.user_service import UserService
    from app.services.session_service import SessionService
    from app.services.strategy_service import StrategyService
    from app.services.function_executor_service import FunctionExecutor
    from app.services.openapi_service import OpenAPIProcessor
    from app.services.chat_history_service import ChatHistoryService
    from app.services.chat_service import ChatService
    from app.services.langchain_service import LangChainService
    from app.services.app_service import AppService
    from app.services.proxy_service import ProxyService
    from app.services.sql_executor_service import SQLExecutorService
    from app.services.user_role_service import UserRoleService 
    from app.services.role_service import RoleService
    from app.services.billing_service import BillingService
    from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)

class ServiceFactory:
    def __init__(self, db: Session, request: Request):
        self.db = db
        self.request = request
        logger.info("🧪 Inicializando ServiceFactory...")

        self._user: Optional[User] = None

        # Lazy-loaded services
        self._agent_service = None
        self._function_service = None
        self._integration_service = None
        self._database_service = None
        self._openai_service = None
        self._executor_service = None
        self._user_service = None
        self._session_service = None
        self._strategy_service = None
        self._openapi_processor = None
        self._mcp_integration_service = None
        self._chat_history_service = None
        self._chat_service = None
        self._langchain_service = None
        self._apps_service = None
        self._proxy_service = None
        self._sql_executor_service = None
        self._user_role_service = None
        self._role_service = None
        self._billing_service = None
        self._permission_service = None
        self._orchestrator_service = None

    @property
    def user(self) -> User:
        if self._user is None:
            self._user = self._load_user()
        return self._user

    def _load_user(self) -> User:
        logger.debug("🔍 Cargando usuario desde session_token...")
        token = self.request.cookies.get("session_token") or self.request.headers.get("Authorization")

        if not token:
            logger.warning("❌ Token de sesión no proporcionado")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session token provided")

        session = self.db.query(SessionModel).filter_by(session_token=token).first()

        if not session or session.expires_at < datetime.now(timezone.utc):
            logger.warning("❌ Sesión inválida o expirada")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

        session.last_used_at = datetime.now(timezone.utc)
        self.db.commit()

        user = self.db.query(User).filter_by(id=session.user_id).first()
        if not user:
            logger.warning(f"❌ Usuario con ID {session.user_id} no encontrado")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        logger.info(f"✅ Usuario autenticado: {user.email}")
        return user

    # Servicios con logs por inicialización
    def get_agent_service(self) -> "AgentService":
        if not self._agent_service:
            from app.services.agent_service import AgentService
            logger.debug("⚙️ Inicializando AgentService")
            self._agent_service = AgentService(self)
        return self._agent_service

    def get_function_service(self) -> "FunctionService":
        if not self._function_service:
            from app.services.function_service import FunctionService
            logger.debug("⚙️ Inicializando FunctionService")
            self._function_service = FunctionService(self)
        return self._function_service

    def get_integration_service(self) -> "IntegrationService":
        if not self._integration_service:
            from app.services.integration_service import IntegrationService
            logger.debug("⚙️ Inicializando IntegrationService")
            self._integration_service = IntegrationService(self)
        return self._integration_service

    def get_database_service(self) -> "DatabaseService":
        if not self._database_service:
            from app.services.database_service import DatabaseService
            logger.debug("⚙️ Inicializando DatabaseService")
            self._database_service = DatabaseService(self)
        return self._database_service

    def get_openai_service(self) -> "OpenAIService":
        if not self._openai_service:
            from app.services.openai_service import OpenAIService
            logger.debug("⚙️ Inicializando OpenAIService")
            self._openai_service = OpenAIService(self)
        return self._openai_service

    def get_executor_service(self) -> "FunctionExecutor":
        if not self._executor_service:
            from app.services.function_executor_service import FunctionExecutor
            logger.debug("⚙️ Inicializando FunctionExecutor")
            self._executor_service = FunctionExecutor(self)
        return self._executor_service

    def get_user_service(self) -> "UserService":
        if not self._user_service:
            from app.services.user_service import UserService
            logger.debug("⚙️ Inicializando UserService")
            self._user_service = UserService(self)
        return self._user_service

    def get_session_service(self) -> "SessionService":
        if not self._session_service:
            from app.services.session_service import SessionService
            logger.debug("⚙️ Inicializando SessionService")
            self._session_service = SessionService(self)
        return self._session_service

    def get_strategy_service(self) -> "StrategyService":
        if not self._strategy_service:
            from app.services.strategy_service import StrategyService
            logger.debug("⚙️ Inicializando StrategyService")
            self._strategy_service = StrategyService(self)
        return self._strategy_service

    def get_openapi_processor(self) -> "OpenAPIProcessor":
        if not self._openapi_processor:
            from app.services.openapi_service import OpenAPIProcessor
            logger.debug("⚙️ Inicializando OpenAPIProcessor")
            self._openapi_processor = OpenAPIProcessor(self)
        return self._openapi_processor

    def get_mcp_integration_service(self):
        if not self._mcp_integration_service:
            from app.services.mcp_integration_service import MCPIntegrationService
            logger.debug("⚙️ Inicializando MCPIntegrationService")
            self._mcp_integration_service = MCPIntegrationService(self)
        return self._mcp_integration_service

    def get_chat_history_service(self) -> "ChatHistoryService":
        if not self._chat_history_service:
            from app.services.chat_history_service import ChatHistoryService
            logger.debug("⚙️ Inicializando ChatHistoryService")
            self._chat_history_service = ChatHistoryService(self)
        return self._chat_history_service

    def get_chat_service(self) -> "ChatService":
        if not self._chat_service:
            from app.services.chat_service import ChatService
            logger.debug("⚙️ Inicializando ChatService")
            self._chat_service = ChatService(self)
        return self._chat_service

    def get_langchain_service(self) -> "LangChainService":
        if not self._langchain_service:
            from app.services.langchain_service import LangChainService
            logger.debug("⚙️ Inicializando LangChainService")
            self._langchain_service = LangChainService(self)
        return self._langchain_service

    def get_apps_service(self) -> "AppService":
        if not self._apps_service:
            from app.services.app_service import AppService
            logger.debug("⚙️ Inicializando AppService")
            self._apps_service = AppService(self)
        return self._apps_service

    def get_proxy_service(self) -> "ProxyService":
        if not self._proxy_service:
            from app.services.proxy_service import ProxyService
            logger.debug("⚙️ Inicializando ProxyService")
            self._proxy_service = ProxyService(self)
        return self._proxy_service

    def get_sql_executor_service(self) -> "SQLExecutorService":
        if not self._sql_executor_service:
            from app.services.sql_executor_service import SQLExecutorService
            logger.debug("⚙️ Inicializando SQLExecutorService")
            self._sql_executor_service = SQLExecutorService(self)
        return self._sql_executor_service

    def get_user_role_service(self) -> "UserRoleService":
        if not self._user_role_service:
            from app.services.user_role_service import UserRoleService
            logger.debug("⚙️ Inicializando UserRoleService")
            self._user_role_service = UserRoleService(self)
        return self._user_role_service

    def get_role_service(self) -> "RoleService":
        if not self._role_service:
            from app.services.role_service import RoleService
            logger.debug("⚙️ Inicializando RoleService")
            self._role_service = RoleService(self)
        return self._role_service

    def get_billing_service(self) -> "BillingService":
        if not self._billing_service:
            from app.services.billing_service import BillingService
            logger.debug("⚙️ Inicializando BillingService")
            self._billing_service = BillingService(self)
        return self._billing_service

    def get_permission_service(self) -> "PermissionService":
        if not self._permission_service:
            from app.services.permission_service import PermissionService
            logger.debug("⚙️ Inicializando PermissionService")
            self._permission_service = PermissionService(self)
        return self._permission_service

    def get_orchestrator_service(self) -> "OrchestratorService":
        if not self._orchestrator_service:
            from app.services.orchestrator_service import OrchestratorService
            logger.debug("⚙️ Inicializando OrchestratorService")
            self._orchestrator_service = OrchestratorService(self)
        return self._orchestrator_service
