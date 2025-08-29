#!/usr/bin/env python3
"""
Embedding Adapter - Adapter provider-agnóstico para embeddings
────────────────────────────────────────────────────────────────
Implementa la Fase 4 del plan de refactorización:
- Soporte para múltiples proveedores (OpenAI, Cohere, HuggingFace, etc.)
- Configuración por ENV
- Batching controlado
- Métricas de performance
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from .base_adapter import BaseAdapter, AdapterType, AdapterConfig


@dataclass
class EmbeddingConfig(AdapterConfig):
    """Configuración específica para embeddings"""
    model: str = "text-embedding-ada-002"
    dimensions: int = 1536
    max_tokens_per_batch: int = 8000
    temperature: float = 0.0


class EmbeddingAdapter(BaseAdapter):
    """
    🔧 Embedding Adapter provider-agnóstico
    
    Responsabilidades:
    - Generar embeddings para texto
    - Soporte para múltiples proveedores
    - Batching automático
    - Cache de embeddings
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        # 🔧 FASE 4: Configuración por ENV
        if config is None:
            config = self._load_config_from_env()
        
        super().__init__(AdapterType.EMBEDDING, config)
        self.embedding_config = config
        
        # 🔧 FASE 4: Batching controlado
        self.batch_size = int(self._get_env_config("BATCH_SIZE", config.batch_size))
        self.max_tokens_per_batch = int(self._get_env_config("MAX_TOKENS_PER_BATCH", config.max_tokens_per_batch))
        
        # Inicializar provider específico
        self.provider = self._initialize_provider()
        
        self._log_operation("EmbeddingAdapter inicializado", 
                           provider=config.provider, 
                           model=config.model,
                           dimensions=config.dimensions)
    
    def _load_config_from_env(self) -> EmbeddingConfig:
        """Cargar configuración desde variables de entorno"""
        return EmbeddingConfig(
            provider=os.getenv("EMBEDDING_PROVIDER", "openai"),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
            url=os.getenv("EMBEDDING_URL"),
            api_key=os.getenv("EMBEDDING_API_KEY"),
            timeout=int(os.getenv("EMBEDDING_TIMEOUT", "30")),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("BATCH_SIZE_EMBEDDINGS", "100")),
            dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "1536")),
            max_tokens_per_batch=int(os.getenv("EMBEDDING_MAX_TOKENS_PER_BATCH", "8000")),
            temperature=float(os.getenv("EMBEDDING_TEMPERATURE", "0.0"))
        )
    
    def _initialize_provider(self):
        """Inicializar el provider específico de embeddings"""
        provider_name = self.embedding_config.provider.lower()
        
        try:
            if provider_name == "openai":
                return self._init_openai_provider()
            elif provider_name == "cohere":
                return self._init_cohere_provider()
            elif provider_name == "huggingface":
                return self._init_huggingface_provider()
            elif provider_name == "sentence_transformers":
                return self._init_sentence_transformers_provider()
            else:
                raise ValueError(f"Provider de embeddings no soportado: {provider_name}")
        except Exception as e:
            self._log_error("Inicialización de provider", e, provider=provider_name)
            raise
    
    def _init_openai_provider(self):
        """Inicializar provider OpenAI"""
        try:
            import openai
            openai.api_key = self.embedding_config.api_key
            if self.embedding_config.url:
                openai.api_base = self.embedding_config.url
            
            # Verificar conectividad
            response = openai.Embedding.create(
                input="test",
                model=self.embedding_config.model
            )
            
            self._log_operation("Provider OpenAI inicializado correctamente")
            return openai
            
        except ImportError:
            raise ImportError("openai package no instalado. Instalar con: pip install openai")
        except Exception as e:
            raise Exception(f"Error inicializando OpenAI: {e}")
    
    def _init_cohere_provider(self):
        """Inicializar provider Cohere"""
        try:
            import cohere
            client = cohere.Client(self.embedding_config.api_key)
            
            # Verificar conectividad
            response = client.embed(
                texts=["test"],
                model=self.embedding_config.model
            )
            
            self._log_operation("Provider Cohere inicializado correctamente")
            return client
            
        except ImportError:
            raise ImportError("cohere package no instalado. Instalar con: pip install cohere")
        except Exception as e:
            raise Exception(f"Error inicializando Cohere: {e}")
    
    def _init_huggingface_provider(self):
        """Inicializar provider HuggingFace"""
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            
            tokenizer = AutoTokenizer.from_pretrained(self.embedding_config.model)
            model = AutoModel.from_pretrained(self.embedding_config.model)
            
            self._log_operation("Provider HuggingFace inicializado correctamente")
            return {"tokenizer": tokenizer, "model": model}
            
        except ImportError:
            raise ImportError("transformers package no instalado. Instalar con: pip install transformers torch")
        except Exception as e:
            raise Exception(f"Error inicializando HuggingFace: {e}")
    
    def _init_sentence_transformers_provider(self):
        """Inicializar provider Sentence Transformers"""
        try:
            from sentence_transformers import SentenceTransformer
            
            model = SentenceTransformer(self.embedding_config.model)
            
            self._log_operation("Provider Sentence Transformers inicializado correctamente")
            return model
            
        except ImportError:
            raise ImportError("sentence-transformers package no instalado. Instalar con: pip install sentence-transformers")
        except Exception as e:
            raise Exception(f"Error inicializando Sentence Transformers: {e}")
    
    def generate_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """
        🔧 FASE 4: Generar embeddings para una lista de textos
        
        Args:
            texts: Lista de textos a procesar
            **kwargs: Parámetros adicionales del provider
            
        Returns:
            Lista de embeddings (cada uno es una lista de floats)
        """
        if not texts:
            return []
        
        # 🔧 FASE 4: Batching automático
        batches = self._create_batches(texts)
        all_embeddings = []
        
        for batch in batches:
            batch_embeddings = self._generate_batch_embeddings(batch, **kwargs)
            all_embeddings.extend(batch_embeddings)
        
        self._log_operation("Embeddings generados", 
                           total_texts=len(texts), 
                           total_batches=len(batches),
                           embedding_dimensions=len(all_embeddings[0]) if all_embeddings else 0)
        
        return all_embeddings
    
    def _create_batches(self, texts: List[str]) -> List[List[str]]:
        """Crear batches basados en tokens y configuración"""
        batches = []
        current_batch = []
        current_tokens = 0
        
        for text in texts:
            # Estimación simple de tokens (4 caracteres ≈ 1 token)
            estimated_tokens = len(text) // 4
            
            if current_tokens + estimated_tokens > self.max_tokens_per_batch or len(current_batch) >= self.batch_size:
                if current_batch:
                    batches.append(current_batch)
                current_batch = [text]
                current_tokens = estimated_tokens
            else:
                current_batch.append(text)
                current_tokens += estimated_tokens
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    def _generate_batch_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generar embeddings para un batch específico"""
        provider_name = self.embedding_config.provider.lower()
        
        try:
            if provider_name == "openai":
                return self._generate_openai_embeddings(texts, **kwargs)
            elif provider_name == "cohere":
                return self._generate_cohere_embeddings(texts, **kwargs)
            elif provider_name == "huggingface":
                return self._generate_huggingface_embeddings(texts, **kwargs)
            elif provider_name == "sentence_transformers":
                return self._generate_sentence_transformers_embeddings(texts, **kwargs)
            else:
                raise ValueError(f"Provider no soportado: {provider_name}")
        except Exception as e:
            self._log_error("Generación de batch embeddings", e, batch_size=len(texts))
            raise
    
    def _generate_openai_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generar embeddings usando OpenAI"""
        response = self.provider.Embedding.create(
            input=texts,
            model=self.embedding_config.model,
            **kwargs
        )
        
        return [embedding.embedding for embedding in response.data]
    
    def _generate_cohere_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generar embeddings usando Cohere"""
        response = self.provider.embed(
            texts=texts,
            model=self.embedding_config.model,
            **kwargs
        )
        
        return response.embeddings
    
    def _generate_huggingface_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generar embeddings usando HuggingFace"""
        tokenizer = self.provider["tokenizer"]
        model = self.provider["model"]
        
        # Tokenizar y generar embeddings
        inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model(**inputs)
            # Usar el último hidden state como embedding
            embeddings = outputs.last_hidden_state.mean(dim=1)
        
        return embeddings.tolist()
    
    def _generate_sentence_transformers_embeddings(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Generar embeddings usando Sentence Transformers"""
        embeddings = self.provider.encode(texts, **kwargs)
        return embeddings.tolist()
    
    def get_embedding_dimensions(self) -> int:
        """Obtener dimensiones de los embeddings"""
        return self.embedding_config.dimensions
    
    def get_model_info(self) -> Dict[str, Any]:
        """Obtener información del modelo de embeddings"""
        return {
            "provider": self.embedding_config.provider,
            "model": self.embedding_config.model,
            "dimensions": self.embedding_config.dimensions,
            "batch_size": self.batch_size,
            "max_tokens_per_batch": self.max_tokens_per_batch
        }
    
    def _health_check(self) -> bool:
        """Verificar salud del adapter de embeddings"""
        try:
            # Generar embedding de prueba
            test_embedding = self.generate_embeddings(["test"])
            return len(test_embedding) == 1 and len(test_embedding[0]) == self.embedding_config.dimensions
        except Exception as e:
            self._log_error("Health check", e)
            return False
    
    def initialize(self) -> bool:
        """Inicializar el adapter de embeddings"""
        try:
            health_status = self._health_check()
            if health_status:
                self._log_operation("Adapter de embeddings inicializado correctamente")
            return health_status
        except Exception as e:
            self._log_error("Inicialización", e)
            return False
