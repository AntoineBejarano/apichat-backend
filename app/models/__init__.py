# app/models/__init__.py

from sqlalchemy.orm import configure_mappers

# Importa Base para registrar en el registry de SQLAlchemy
from app.models.base_model import Base

# Importa todos los modelos para que sus clases estén registradas
from app.models.user_model import User
from app.models.agent_model import Agent
from app.models.chat_model import Chat
from app.models.chat_history_model import ChatHistory
from app.models.function_call_log_model import FunctionCallLog
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from app.models.integration_model import Integration
from app.models.mcp_integration_model import MCPIntegration
from app.models.openapi_model import OpenAPIIntegration
from app.models.permission_model import Permission
from app.models.plan_model import Plan
from app.models.proxy_model import Proxy
from app.models.role_model import Role
from app.models.session_model import Session
from app.models.strategy_model import Strategy
from app.models.token_usage_model import TokenUsage
from app.models.subscription_model import Subscription
from app.models.oauth_model import OAuthAccount
from app.models.function_group_model import FunctionGroup
from app.models.event_definition_model import EventDefinition
from app.models.trigger_model import Trigger
from app.models.event_trigger_model import EventTrigger
from app.models.llm_runs_model import LLMRun

__all__ = [
    "Base",
    "User", "Agent", "Chat", "ChatHistory", "FunctionCallLog", "App",
    "DatabaseConnection", "Function", "Integration", "MCPIntegration",
    "OpenAPIIntegration", "Permission", "Plan", "Proxy", "Role",
    "Session", "Strategy", "TokenUsage", "Subscription",
    "OAuthAccount", "FunctionGroup", "EventDefinition", "Trigger", "EventTrigger", "LLMRun"
]

def init_model_relationships():
    """
    Fuerza la configuración de todos los mappers para resolver
    relaciones definidas con strings tras importar todas las clases.
    """
    configure_mappers()
