import logging
from typing import Union, Optional
from datetime import datetime, timezone
from fastapi import HTTPException, status, Request
from sqlalchemy.orm import Session
from fastapi import WebSocket

from app.models.user_model import User
from app.models.session_model import Session as SessionModel
from app.common.ws_emitter import WebSocketEmitter

logger = logging.getLogger(__name__)

class ServiceFactory:
    def __init__(self, db: Session, request: Union[Request, WebSocket, None] = None):
        self.db = db
        self.request = request
        logger.info("🧪 Inicializando ServiceFactory...")

        self._user: Optional[User] = None

        # ⚡ OPTIMIZACIÓN: Pre-inicializar servicios críticos
        self._usage_service = None
        self._chat_history_service = None
        self._openai_service = None
        self._agent_service = None
        self._database_service = None
        self._cache_service = None
        self._schema_explorer_service = None
        self._detailed_schema_cache = None
        self._detailed_schema_cache_service = None
        self._sql_guardrails_service = None
        self._function_guardrails_service = None
        self._description_selector_service = None
        self._intent_classifier_service = None
        self._app_descriptor_cache_service = None
        self._telemetry_service = None
        self._vector_search_service = None
        self._prompt_engineering_service = None
        self._query_validation_service = None
        self._performance_monitoring_service = None
        
        # Lazy-loaded services (los demás)
        self._function_service = None
        self._integration_service = None
        self._executor_service = None
        self._user_service = None
        self._session_service = None
        self._strategy_service = None
        self._openapi_processor = None
        self._mcp_integration_service = None
        self._chat_service = None
        self._langchain_service = None
        self._app_service = None  # Unificado: solo _app_service
        self._proxy_service = None
        self._sql_executor_service = None
        self._user_role_service = None
        self._role_service = None
        self._billing_service = None
        self._permission_service = None
        self._orchestrator_service = None
        self._background_task_service = None
        self._event_definition_service = None
        self._event_trigger_service = None
        self._trigger_service = None
        self._executed_strategy_service = None
        self._execution_engine_service = None
        self._resource_selector_service = None
        self._plan_builder_service = None
        self._error_handler_service = None
        self._ws_emitter = None


    @property
    def user(self) -> User:
        if self._user is None:
            self._user = self._load_user()
        return self._user

    def _load_user(self) -> User:
        if self.request is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Request not available")

        logger.debug("🔍 Cargando usuario desde session_token...")

        # Detecta si es WebSocket o HTTP Request
        token = None
        if hasattr(self.request, "cookies"):
            token = self.request.cookies.get("session_token")
        if not token and hasattr(self.request, "headers"):
            token = self.request.headers.get("Authorization")

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

    # ⚡ OPTIMIZACIÓN: Servicios críticos pre-inicializados
    def get_usage_service(self) -> "UsageService":
        if not self._usage_service:
            from app.services.usage_service import UsageService
            logger.debug("⚙️ Inicializando UsageService")
            self._usage_service = UsageService(self)
        return self._usage_service

    def get_chat_history_service(self) -> "ChatHistoryService":
        if not self._chat_history_service:
            from app.services.chat_history_service import ChatHistoryService
            logger.debug("⚙️ Inicializando ChatHistoryService")
            self._chat_history_service = ChatHistoryService(self)
        return self._chat_history_service

    def get_openai_service(self) -> "OpenAIService":
        if not self._openai_service:
            from app.services.openai_service import OpenAIService
            logger.debug("⚙️ Inicializando OpenAIService")
            self._openai_service = OpenAIService(self)
        return self._openai_service

    def get_agent_service(self) -> "AgentService":
        if not self._agent_service:
            from app.services.agent_service import AgentService
            logger.debug("⚙️ Inicializando AgentService")
            self._agent_service = AgentService(self)
        return self._agent_service

    def get_database_service(self) -> "DatabaseService":
        if not self._database_service:
            from app.services.database_service import DatabaseService
            logger.debug("⚙️ Inicializando DatabaseService")
            self._database_service = DatabaseService(self)
        return self._database_service

    def get_cache_service(self) -> "CacheService":
        if not self._cache_service:
            from app.services.cache_service import CacheService
            logger.debug("⚙️ Inicializando CacheService")
            self._cache_service = CacheService()
        return self._cache_service

    def get_schema_explorer_service(self) -> "SchemaExplorerService":
        if not self._schema_explorer_service:
            from app.services.schema_explorer_service import SchemaExplorerService
            logger.debug("⚙️ Inicializando SchemaExplorerService")
            cache_service = self.get_cache_service()
            database_service = self.get_database_service()
            self._schema_explorer_service = SchemaExplorerService(cache_service, database_service)
        return self._schema_explorer_service

    def get_detailed_schema_cache(self) -> "DetailedSchemaCache":
        if not self._detailed_schema_cache:
            from app.services.detailed_schema_cache import DetailedSchemaCache
            logger.debug("🦄 Inicializando DetailedSchemaCache")
            self._detailed_schema_cache = DetailedSchemaCache()
        return self._detailed_schema_cache

    def get_vector_search_service(self) -> "VectorSearchService":
        if not self._vector_search_service:
            from app.services.vector_search_service import VectorSearchService
            logger.debug("🔍 Inicializando VectorSearchService")
            # Obtener API key de OpenAI desde configuración
            openai_api_key = None  # TODO: Obtener desde configuración
            self._vector_search_service = VectorSearchService(openai_api_key)
        return self._vector_search_service

    def get_prompt_engineering_service(self) -> "PromptEngineeringService":
        if not self._prompt_engineering_service:
            from app.services.prompt_engineering_service import PromptEngineeringService
            logger.debug("🎯 Inicializando PromptEngineeringService")
            self._prompt_engineering_service = PromptEngineeringService()
        return self._prompt_engineering_service

    def get_query_validation_service(self) -> "QueryValidationService":
        if not self._query_validation_service:
            from app.services.query_validation_service import QueryValidationService
            logger.debug("⚙️ Inicializando QueryValidationService")
            self._query_validation_service = QueryValidationService(self)
        return self._query_validation_service

    def get_performance_monitoring_service(self) -> "PerformanceMonitoringService":
        if not self._performance_monitoring_service:
            from app.services.performance_monitoring_service import PerformanceMonitoringService
            logger.debug("⚙️ Inicializando PerformanceMonitoringService")
            self._performance_monitoring_service = PerformanceMonitoringService(self)
        return self._performance_monitoring_service

    # Servicios lazy-loaded (menos críticos)
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
        if self._mcp_integration_service is None:
            from app.services.mcp_integration_service import MCPIntegrationService
            self._mcp_integration_service = MCPIntegrationService(self)
        return self._mcp_integration_service

    def get_mcp_service(self):
        """Alias para get_mcp_integration_service para compatibilidad"""
        return self.get_mcp_integration_service()

    def get_chat_service(self) -> "ChatService":
        if not self._chat_service:
            from app.services.chat_service import ChatService
            logger.debug("⚙️ Inicializando ChatService")
            self._chat_service = ChatService(self)
        return self._chat_service

    def get_langchain_service(self) -> "LangchainService":
        if not self._langchain_service:
            from app.services.langchain_service import LangchainService
            logger.debug("⚙️ Inicializando LangchainService")
            self._langchain_service = LangchainService(self)
        return self._langchain_service

    def get_apps_service(self) -> "AppService":
        # Alias para mantener compatibilidad, pero ahora devuelve AppService
        if not self._app_service:
            from app.services.app_service import AppService
            logger.debug("⚙️ Inicializando AppService")
            self._app_service = AppService(self)
        return self._app_service

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

    def get_background_task_service(self) -> "BackgroundTaskService":
        if not self._background_task_service:
            from app.services.background_task_service import BackgroundTaskService
            logger.debug("⚙️ Inicializando BackgroundTaskService")
            self._background_task_service = BackgroundTaskService()
        return self._background_task_service

    def get_usage_service(self) -> "UsageService":
        if not self._usage_service:
            from app.services.usage_service import UsageService
            logger.debug("⚙️ Inicializando UsageService")
            self._usage_service = UsageService(self)
        return self._usage_service

    def get_event_definition_service(self) -> "EventDefinitionService":
        if not self._event_definition_service:
            from app.services.event_definition_service import EventDefinitionService
            logger.debug("⚙️ Inicializando EventDefinitionService")
            self._event_definition_service = EventDefinitionService(self)
        return self._event_definition_service

    def get_event_trigger_service(self) -> "EventTriggerService":
        if not self._event_trigger_service:
            from app.services.event_trigger_service import EventTriggerService
            logger.debug("⚙️ Inicializando EventTriggerService")
            self._event_trigger_service = EventTriggerService(self)
        return self._event_trigger_service

    def get_trigger_service(self) -> "TriggerService":
        if not self._trigger_service:
            from app.services.trigger_service import TriggerService
            logger.debug("⚙️ Inicializando TriggerService")
            self._trigger_service = TriggerService(self)
        return self._trigger_service

    def get_executed_strategy_service(self) -> "ExecutedStrategyService":
        if not self._executed_strategy_service:
            from app.services.executed_strategy_service import ExecutedStrategyService
            logger.debug("⚙️ Inicializando ExecutedStrategyService")
            self._executed_strategy_service = ExecutedStrategyService(self)
        return self._executed_strategy_service

    def get_execution_engine_service(self) -> "ExecutionEngineService":
        if not self._execution_engine_service:
            from app.services.execution_engine_service import ExecutionEngineService
            logger.debug("⚙️ Inicializando ExecutionEngineService")
            self._execution_engine_service = ExecutionEngineService(self)
        return self._execution_engine_service

    def get_resource_selector_service(self) -> "ResourceSelectorService":
        """Obtiene el servicio de selección de recursos."""
        if not self._resource_selector_service:
            from app.services.execution.resource_selector_service import ResourceSelectorService
            logger.debug("⚙️ Inicializando ResourceSelectorService")
            self._resource_selector_service = ResourceSelectorService()
        return self._resource_selector_service

    def get_plan_builder_service(self) -> "PlanBuilderService":
        """Obtiene el servicio de construcción de planes."""
        if not self._plan_builder_service:
            from app.services.ai.plan_builder_service import PlanBuilderService
            logger.debug("⚙️ Inicializando PlanBuilderService")
            self._plan_builder_service = PlanBuilderService()
        return self._plan_builder_service

    def get_error_handler_service(self) -> "ErrorHandlerService":
        """Obtiene el servicio de manejo de errores."""
        if not self._error_handler_service:
            from app.services.execution.error_handler_service import ErrorHandlerService
            logger.debug("⚙️ Inicializando ErrorHandlerService")
            ws_emitter = self.get_ws_emitter()
            self._error_handler_service = ErrorHandlerService(ws_emitter)
        return self._error_handler_service

    def get_ws_emitter(self) -> Optional[WebSocketEmitter]:
        """Obtiene el emisor de eventos WebSocket si está disponible."""
        if self._ws_emitter is None and isinstance(self.request, WebSocket):
            self._ws_emitter = WebSocketEmitter(self.request)
        return self._ws_emitter

    def get_app_service(self) -> "AppService":
        if not self._app_service:
            from app.services.app_service import AppService
            logger.debug("⚙️ Inicializando AppService")
            self._app_service = AppService(self)
        return self._app_service


    def get_detailed_schema_cache_service(self) -> "DetailedSchemaCacheService":
        if not self._detailed_schema_cache_service:
            from app.services.detailed_schema_cache_service import DetailedSchemaCacheService
            logger.debug("⚙️ Inicializando DetailedSchemaCacheService")
            self._detailed_schema_cache_service = DetailedSchemaCacheService(self)
        return self._detailed_schema_cache_service

    def get_sql_guardrails_service(self) -> "SQLGuardrailsService":
        if not self._sql_guardrails_service:
            from app.services.execution.sql_guardrails_service import SQLGuardrailsService
            logger.debug("⚙️ Inicializando SQLGuardrailsService")
            self._sql_guardrails_service = SQLGuardrailsService()
        return self._sql_guardrails_service

    def get_function_guardrails_service(self) -> "FunctionGuardrailsService":
        if not self._function_guardrails_service:
            from app.services.execution.function_guardrails import FunctionGuardrailsService
            logger.debug("⚙️ Inicializando FunctionGuardrailsService")
            self._function_guardrails_service = FunctionGuardrailsService()
        return self._function_guardrails_service

    def get_description_selector_service(self):
        """Obtener servicio de selección por descripción"""
        if self._description_selector_service is None:
            from app.services.description_selector_service import DescriptionSelectorService
            logger.debug("⚙️ Inicializando DescriptionSelectorService")
            self._description_selector_service = DescriptionSelectorService(self)
        return self._description_selector_service

    def get_intent_classifier_service(self):
        """Obtener servicio de clasificación de intenciones"""
        if self._intent_classifier_service is None:
            from app.services.intent_classifier_service import IntentClassifierService
            logger.debug("⚙️ Inicializando IntentClassifierService")
            self._intent_classifier_service = IntentClassifierService(self)
        return self._intent_classifier_service

    def get_app_descriptor_cache_service(self):
        """Obtener servicio de cache de descriptores de apps"""
        if self._app_descriptor_cache_service is None:
            from app.services.app_descriptor_cache_service import AppDescriptorCacheService
            logger.debug("⚙️ Inicializando AppDescriptorCacheService")
            self._app_descriptor_cache_service = AppDescriptorCacheService(self)
        return self._app_descriptor_cache_service

    def get_telemetry_service(self):
        """Obtener servicio de telemetría (alias para compatibilidad)"""
        return self.get_advanced_telemetry_service()

    def get_advanced_telemetry_service(self):
        """Obtener servicio de telemetría avanzado (FASE 13)"""
        if self._telemetry_service is None:
            from app.services.management.advanced_telemetry_service import AdvancedTelemetryService
            logger.debug("⚙️ Inicializando AdvancedTelemetryService (FASE 13)")
            self._telemetry_service = AdvancedTelemetryService(self)
        return self._telemetry_service


def get_service_factory():
    """Dependency para obtener el ServiceFactory"""
    from app.core.database import get_db
    db = next(get_db())
    return ServiceFactory(db=db)