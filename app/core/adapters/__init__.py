"""
🔧 Core Adapters Module
────────────────────────
Implementa la Fase 9 del plan de refactorización:
- EmbeddingAdapter (provider-agnóstico)
- VectorStoreAdapter (multi-driver)
- CacheAdapter (Redis/Upstash)
- LLMAdapter (OpenAI/Claude/Gemini/Cohere)
- Namespace management
- Batching controlado
"""

from .embedding_adapter import EmbeddingAdapter
from .vector_store_adapter import VectorStoreAdapter
from .cache_adapter import CacheAdapter
from .llm_adapter import LLMAdapter, LLMRequest, LLMResponse
from .base_adapter import BaseAdapter, AdapterType, AdapterConfig
from .adapter_factory import AdapterFactory, adapter_factory

__all__ = [
    "EmbeddingAdapter",
    "VectorStoreAdapter",
    "CacheAdapter",
    "LLMAdapter",
    "LLMRequest",
    "LLMResponse",
    "BaseAdapter",
    "AdapterType",
    "AdapterConfig",
    "AdapterFactory",
    "adapter_factory"
]
