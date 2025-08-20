"""
🔧 FASE 6: Configuración de Langsmith
──────────────────────────────────────
Configuración centralizada para Langsmith tracing y observabilidad.
"""

import os
import logging
from typing import Optional
from langsmith import Client
from langsmith import traceable

logger = logging.getLogger(__name__)

class LangsmithConfig:
    """Configuración centralizada para Langsmith."""
    
    def __init__(self):
        self.api_key = os.getenv("LANGSMITH_API_KEY", "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")
        self.project_name = os.getenv("LANGSMITH_PROJECT", "apichat-backend")
        self.endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
        
        # Inicializar cliente de Langsmith
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Inicializa el cliente de Langsmith."""
        try:
            if self.api_key:
                self.client = Client(
                    api_key=self.api_key,
                    api_url=self.endpoint
                )
                logger.info(f"[LangsmithConfig] ✅ Cliente inicializado para proyecto: {self.project_name}")
            else:
                logger.warning("[LangsmithConfig] ⚠️ No se encontró API key de Langsmith")
                self.client = None
        except Exception as e:
            logger.error(f"[LangsmithConfig] ❌ Error inicializando cliente: {e}")
            self.client = None
    
    def is_enabled(self) -> bool:
        """Verifica si Langsmith está habilitado."""
        return self.client is not None
    
    def get_client(self) -> Optional[Client]:
        """Obtiene el cliente de Langsmith."""
        return self.client
    
    def get_project_name(self) -> str:
        """Obtiene el nombre del proyecto."""
        return self.project_name

# Instancia global de configuración
langsmith_config = LangsmithConfig()

# Decorador personalizado que verifica si Langsmith está habilitado
def traceable_if_enabled(*args, **kwargs):
    """
    Decorador que aplica @traceable solo si Langsmith está habilitado.
    Si no está habilitado, retorna la función original sin modificar.
    """
    if langsmith_config.is_enabled():
        return traceable(*args, **kwargs)
    else:
        # Si Langsmith no está habilitado, retornar decorador que no hace nada
        def no_op_decorator(func):
            return func
        return no_op_decorator
