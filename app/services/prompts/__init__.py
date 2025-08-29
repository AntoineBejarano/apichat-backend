"""
📝 FASE 8: Módulo de Prompts Configurables
────────────────────────────────────────────
Implementa:
- Sistema de prompts centralizado y configurable
- Gestión de versiones y caché
- Integración con todas las fases del sistema
- Personalización por entorno y tenant
"""

from .prompt_registry import (
    PromptKey,
    PromptCategory,
    PromptRegistry,
    prompt_registry
)

from .prompt_template_service import (
    PromptTemplateService,
    PromptTemplate,
    PromptContext
)

__all__ = [
    # Prompt Registry
    "PromptKey",
    "PromptCategory", 
    "PromptRegistry",
    "prompt_registry",
    
    # Prompt Template Service
    "PromptTemplateService",
    "PromptTemplate",
    "PromptContext"
]
