import logging
from sqlalchemy.orm import Session
from fastapi import Request, HTTPException, status

from app.services.agent_service import AgentService
from app.services.function_service import FunctionService
from app.services.integration_service import IntegrationService
from app.services.database_service import DatabaseService
from app.services.openai_service import OpenAIService
from app.services.chat_orchestrator_service import OrchestratorService
from app.services.user_service import UserService
from app.services.session_service import SessionService
from app.services.strategy_service import StrategyService
from app.services.executor import FunctionExecutor

from app.models.user_model import User
from app.models.session_model import Session as SessionModel

logger = logging.getLogger(__name__)


class ServiceFactory:
    def __init__(self, db: Session, request: Request):
        self.db = db
        self.request = request
        logger.info("🧪 Inicializando ServiceFactory...")

        self._user: User = self._load_user()

        self._agent_service = None
        self._function_service = None
        self._integration_service = None
        self._database_service = None
        self._openai_service = None
        self._executor_service = None
        self._user_service = None
        self._session_service = None
        self._strategy_service = None

    def _load_user(self) -> User:
        logger.debug("🔍 Cargando usuario desde session_token...")

        token = self.request.cookies.get("session_token") or self.request.headers.get("Authorization")
        if not token:
            logger.warning("❌ Token de sesión no proporcionado")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session token provided")

        session = self.db.query(SessionModel).filter_by(session_token=token).first()
        if not session or session.expires_at < session.created_at:
            logger.warning("❌ Sesión inválida o expirada")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

        user = self.db.query(User).filter_by(id=session.user_id).first()
        if not user:
            logger.warning(f"❌ Usuario con ID {session.user_id} no encontrado")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        logger.info(f"✅ Usuario {user.email} autenticado correctamente")
        return user

    @property
    def user(self) -> User:
        return self._user

    def get_orchestrator_service(self) -> OrchestratorService:
        logger.debug("⚙️ Creando instancia de OrchestratorService")
        return OrchestratorService(self)

    def get_executor_service(self) -> FunctionExecutor:
        if not self._executor_service:
            logger.debug("⚙️ Inicializando FunctionExecutor")
            self._executor_service = FunctionExecutor(self)
        return self._executor_service

    def get_openai_service(self) -> OpenAIService:
        if not self._openai_service:
            logger.debug("⚙️ Inicializando OpenAIService")
            self._openai_service = OpenAIService(self)
        return self._openai_service

    def get_user_service(self) -> UserService:
        if not self._user_service:
            logger.debug("⚙️ Inicializando UserService")
            self._user_service = UserService(self)
        return self._user_service

    def get_session_service(self) -> SessionService:
        if not self._session_service:
            logger.debug("⚙️ Inicializando SessionService")
            self._session_service = SessionService(self)
        return self._session_service

    def get_agent_service(self) -> AgentService:
        if not self._agent_service:
            logger.debug("⚙️ Inicializando AgentService")
            self._agent_service = AgentService(self)
        return self._agent_service

    def get_function_service(self) -> FunctionService:
        if not self._function_service:
            logger.debug("⚙️ Inicializando FunctionService")
            self._function_service = FunctionService(self)
        return self._function_service

    def get_integration_service(self) -> IntegrationService:
        if not self._integration_service:
            logger.debug("⚙️ Inicializando IntegrationService")
            self._integration_service = IntegrationService(self)
        return self._integration_service

    def get_database_service(self) -> DatabaseService:
        if not self._database_service:
            logger.debug("⚙️ Inicializando DatabaseService")
            self._database_service = DatabaseService(self)
        return self._database_service

    def get_strategy_service(self) -> StrategyService:
        if not self._strategy_service:
            logger.debug("⚙️ Inicializando StrategyService")
            self._strategy_service = StrategyService(self)
        return self._strategy_service
