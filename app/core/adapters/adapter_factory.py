"""
🔧 Adapter Factory - Gestión centralizada de adapters
──────────────────────────────────────────────────────
Implementa la Fase 9 del plan de refactorización:
- Factory pattern para todos los adapters
- Configuración centralizada por ENV
- Health checks y métricas unificadas
- Fallbacks automáticos entre proveedores
"""

import os
import logging
from typing import Dict, Any, Optional, Type
from enum import Enum

from .base_adapter import BaseAdapter, AdapterType, AdapterConfig
from .embedding_adapter import EmbeddingAdapter
from .vector_store_adapter import VectorStoreAdapter
from .cache_adapter import CacheAdapter
from .llm_adapter import LLMAdapter


class AdapterFactory:
    """
    🔧 Factory centralizado para todos los adapters
    
    Responsabilidades:
    - Creación y gestión de adapters
    - Configuración centralizada por ENV
    - Health checks unificados
    - Fallbacks automáticos
    - Métricas agregadas
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._adapters: Dict[AdapterType, BaseAdapter] = {}
        self._configs: Dict[AdapterType, AdapterConfig] = {}
        
        # Cargar configuraciones desde ENV
        self._load_configurations()
        
        self.logger.info("[AdapterFactory] Inicializado con configuraciones cargadas")
    
    def _load_configurations(self):
        """Cargar todas las configuraciones desde variables de entorno"""
        # Embedding Adapter
        self._configs[AdapterType.EMBEDDING] = AdapterConfig(
            provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            url=os.getenv("EMBEDDING_URL"),
            api_key=os.getenv("EMBEDDING_API_KEY"),
            timeout=int(os.getenv("EMBEDDING_TIMEOUT", "30")),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("BATCH_SIZE_EMBEDDINGS", "100")),
            namespace_strategy=os.getenv("VECTOR_NAMESPACE_STRATEGY", "tenant_app_db_snapshot")
        )
        
        # Vector Store Adapter
        self._configs[AdapterType.VECTOR_STORE] = AdapterConfig(
            provider=os.getenv("VECTOR_PROVIDER", "pgvector"),
            url=os.getenv("VECTOR_URL"),
            api_key=os.getenv("VECTOR_API_KEY"),
            timeout=int(os.getenv("VECTOR_TIMEOUT", "30")),
            max_retries=int(os.getenv("VECTOR_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("VECTOR_BATCH_SIZE", "100")),
            namespace_strategy=os.getenv("VECTOR_NAMESPACE_STRATEGY", "tenant_app_db_snapshot")
        )
        
        # Cache Adapter
        self._configs[AdapterType.CACHE] = AdapterConfig(
            provider=os.getenv("CACHE_PROVIDER", "redis"),
            url=os.getenv("CACHE_URL", "redis://localhost:6379/0"),
            api_key=os.getenv("CACHE_API_KEY"),
            timeout=int(os.getenv("CACHE_TIMEOUT", "10")),
            max_retries=int(os.getenv("CACHE_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("CACHE_BATCH_SIZE", "100")),
            namespace_strategy="default"
        )
        
        # LLM Adapter
        self._configs[AdapterType.LLM] = AdapterConfig(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            url=os.getenv("LLM_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("LLM_BATCH_SIZE", "1")),
            namespace_strategy="default"
        )
    
    def get_embedding_adapter(self) -> EmbeddingAdapter:
        """Obtener el adapter de embeddings"""
        if AdapterType.EMBEDDING not in self._adapters:
            try:
                self._adapters[AdapterType.EMBEDDING] = EmbeddingAdapter(
                    self._configs[AdapterType.EMBEDDING]
                )
                self.logger.info(f"[AdapterFactory] EmbeddingAdapter creado con {self._configs[AdapterType.EMBEDDING].provider}")
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Error creando EmbeddingAdapter: {e}")
                raise
        
        return self._adapters[AdapterType.EMBEDDING]
    
    def get_vector_store_adapter(self) -> VectorStoreAdapter:
        """Obtener el adapter de vector store"""
        if AdapterType.VECTOR_STORE not in self._adapters:
            try:
                self._adapters[AdapterType.VECTOR_STORE] = VectorStoreAdapter(
                    self._configs[AdapterType.VECTOR_STORE]
                )
                self.logger.info(f"[AdapterFactory] VectorStoreAdapter creado con {self._configs[AdapterType.VECTOR_STORE].provider}")
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Error creando VectorStoreAdapter: {e}")
                raise
        
        return self._adapters[AdapterType.VECTOR_STORE]
    
    def get_cache_adapter(self) -> CacheAdapter:
        """Obtener el adapter de cache"""
        if AdapterType.CACHE not in self._adapters:
            try:
                self._adapters[AdapterType.CACHE] = CacheAdapter(
                    self._configs[AdapterType.CACHE]
                )
                self.logger.info(f"[AdapterFactory] CacheAdapter creado con {self._configs[AdapterType.CACHE].provider}")
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Error creando CacheAdapter: {e}")
                raise
        
        return self._adapters[AdapterType.CACHE]
    
    def get_llm_adapter(self) -> LLMAdapter:
        """Obtener el adapter de LLM"""
        if AdapterType.LLM not in self._adapters:
            try:
                self._adapters[AdapterType.LLM] = LLMAdapter(
                    self._configs[AdapterType.LLM]
                )
                self.logger.info(f"[AdapterFactory] LLMAdapter creado con {self._configs[AdapterType.LLM].provider}")
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Error creando LLMAdapter: {e}")
                raise
        
        return self._adapters[AdapterType.LLM]
    
    def get_adapter(self, adapter_type: AdapterType) -> BaseAdapter:
        """Obtener cualquier adapter por tipo"""
        if adapter_type == AdapterType.EMBEDDING:
            return self.get_embedding_adapter()
        elif adapter_type == AdapterType.VECTOR_STORE:
            return self.get_vector_store_adapter()
        elif adapter_type == AdapterType.CACHE:
            return self.get_cache_adapter()
        elif adapter_type == AdapterType.LLM:
            return self.get_llm_adapter()
        else:
            raise ValueError(f"Tipo de adapter no soportado: {adapter_type}")
    
    def health_check_all(self) -> Dict[str, bool]:
        """Health check de todos los adapters"""
        health_status = {}
        
        for adapter_type in AdapterType:
            try:
                if adapter_type in self._adapters:
                    adapter = self._adapters[adapter_type]
                    if hasattr(adapter, 'health_check'):
                        health_status[adapter_type.value] = adapter.health_check()
                    else:
                        health_status[adapter_type.value] = True  # Sin health check
                else:
                    health_status[adapter_type.value] = False  # No inicializado
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Health check falló para {adapter_type.value}: {e}")
                health_status[adapter_type.value] = False
        
        return health_status
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Obtener métricas de todos los adapters"""
        metrics = {}
        
        for adapter_type, adapter in self._adapters.items():
            try:
                if hasattr(adapter, 'metrics'):
                    metrics[adapter_type.value] = adapter.metrics.copy()
                else:
                    metrics[adapter_type.value] = {}
            except Exception as e:
                self.logger.error(f"[AdapterFactory] Error obteniendo métricas de {adapter_type.value}: {e}")
                metrics[adapter_type.value] = {}
        
        return metrics
    
    def get_adapter_info(self) -> Dict[str, Dict[str, Any]]:
        """Obtener información de todos los adapters"""
        info = {}
        
        for adapter_type, config in self._configs.items():
            info[adapter_type.value] = {
                "provider": config.provider,
                "url": config.url,
                "timeout": config.timeout,
                "max_retries": config.max_retries,
                "batch_size": config.batch_size,
                "initialized": adapter_type in self._adapters
            }
        
        return info
    
    def reload_configurations(self):
        """Recargar configuraciones desde ENV"""
        self.logger.info("[AdapterFactory] Recargando configuraciones desde ENV")
        
        # Limpiar adapters existentes
        self._adapters.clear()
        
        # Recargar configuraciones
        self._load_configurations()
        
        self.logger.info("[AdapterFactory] Configuraciones recargadas")
    
    def get_factory_summary(self) -> Dict[str, Any]:
        """Obtener resumen completo del factory"""
        return {
            "factory_type": "AdapterFactory",
            "total_adapters": len(AdapterType),
            "initialized_adapters": len(self._adapters),
            "health_status": self.health_check_all(),
            "adapter_info": self.get_adapter_info(),
            "metrics": self.get_all_metrics(),
            "configurations": {
                adapter_type.value: {
                    "provider": config.provider,
                    "url": config.url,
                    "timeout": config.timeout,
                    "max_retries": config.max_retries,
                    "batch_size": config.batch_size
                }
                for adapter_type, config in self._configs.items()
            }
        }


# Instancia global del factory
adapter_factory = AdapterFactory()
