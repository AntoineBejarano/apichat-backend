"""
Módulo principal de servicios.
Organiza todos los servicios en módulos especializados por responsabilidad.
"""

# Importar todos los módulos organizados
from . import context
from . import execution
from . import data
from . import ai
from . import integration
from . import management
from . import orchestrator

# Importar servicios que permanecen en la carpeta principal
from .base_service import BaseService
from .orchestrator.orchestrator_service import OrchestratorService

__all__ = [
    "context",
    "execution", 
    "data",
    "ai",
    "integration",
    "management",
    "orchestrator",
    "BaseService",
    "OrchestratorService"
]
