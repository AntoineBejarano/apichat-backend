"""
Módulos del Orchestrator Refactorizado
──────────────────────────────────────
Este paquete contiene todos los módulos especializados del OrchestratorService:

Módulos Principales:
- TokenBudgetManager: Control de presupuesto de tokens
- ContextLoader: Carga de contexto paralelo
- ResponseProcessor: Procesamiento de respuestas
- ContextOptimizer: Optimización de contexto
- GraphRunner: Ejecución de grafos
- MessageHandler: Manejo de mensajes
- IterativeRAGHandler: Manejo de RAG iterativo
- SchemaValidator: Validación de esquemas
- ResponseFormatter: Formateo de respuestas

Módulos de Gestión:
- SchemaManager: Manejo de esquemas de base de datos
- ChatHistoryManager: Manejo de historial de chat
- AppFunctionManager: Manejo de aplicaciones y funciones

Módulos de Planificación:
- PlanStrategyManager: Gestión de estrategias de planificación
- AgentManager: Gestión de agentes
"""

# Módulos principales del orchestrator
from .token_budget import TokenBudgetManager
from .context_loader import ContextLoader
from .response_processor import ResponseProcessor
from .context_optimizer import ContextOptimizer
from .graph_runner import GraphRunner
from .message_handler import MessageHandler
from .iterative_rag_handler import IterativeRAGHandler
from .schema_validator import SchemaValidator
from .response_formatter import ResponseFormatter
from .decision_manager import DecisionManager

# Módulos de gestión
from .schema_manager import SchemaManager
from .chat_history_manager import ChatHistoryManager
from .app_function_manager import AppFunctionManager

# Módulos de planificación
from .plan_strategy_manager import PlanStrategyManager
from .agent_manager import AgentManager

__all__ = [
    # Módulos principales
    "TokenBudgetManager",
    "ContextLoader", 
    "ResponseProcessor",
    "ContextOptimizer",
    "GraphRunner",
    "MessageHandler",
    "IterativeRAGHandler",
    "SchemaValidator",
    "ResponseFormatter",
    "DecisionManager",
    
    # Módulos de gestión
    "SchemaManager",
    "ChatHistoryManager", 
    "AppFunctionManager",
    
    # Módulos de planificación
    "PlanStrategyManager",
    "AgentManager",
]

# Versión del módulo
__version__ = "2.0.0"

# Información del módulo
__author__ = "API Chat Backend Team"
__description__ = "Módulo de servicios especializados para el orchestrator"
