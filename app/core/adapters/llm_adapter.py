"""
🔧 LLM Adapter - Provider-agnóstico para Language Models
──────────────────────────────────────────────────────────
Implementa la Fase 9 del plan de refactorización:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Cohere
- Configuración por ENV
- Fallbacks automáticos
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .base_adapter import BaseAdapter, AdapterType, AdapterConfig


@dataclass
class LLMResponse:
    """Respuesta estandarizada del LLM"""
    content: str
    model: str
    usage: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None
    latency_ms: Optional[float] = None


@dataclass
class LLMRequest:
    """Request estandarizado para el LLM"""
    messages: List[Dict[str, str]]
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False


class LLMProvider(ABC):
    """Interfaz abstracta para proveedores de LLM"""
    
    @abstractmethod
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        pass
    
    @abstractmethod
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        pass


class OpenAIProvider(LLMProvider):
    """Proveedor OpenAI"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.openai")
        
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=config.api_key,
                base_url=config.url or "https://api.openai.com/v1"
            )
            self.logger.info(f"[OpenAIProvider] Conectado a {config.url or 'https://api.openai.com/v1'}")
        except ImportError:
            raise ImportError("OpenAI no está instalado. Ejecuta: pip install openai")
        except Exception as e:
            self.logger.error(f"[OpenAIProvider] Error conectando a OpenAI: {e}")
            raise
    
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        try:
            response = self.client.chat.completions.create(
                model=request.model or "gpt-4",
                messages=request.messages,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens,
                stream=request.stream
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage=response.usage.model_dump() if response.usage else None,
                finish_reason=response.choices[0].finish_reason
            )
        except Exception as e:
            self.logger.error(f"[OpenAIProvider] Error en chat_completion: {e}")
            raise
    
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        try:
            models = self.client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            self.logger.error(f"[OpenAIProvider] Error obteniendo modelos: {e}")
            return ["gpt-4", "gpt-3.5-turbo"]
    
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        try:
            self.client.models.list(limit=1)
            return True
        except Exception as e:
            self.logger.error(f"[OpenAIProvider] Health check falló: {e}")
            return False


class AnthropicProvider(LLMProvider):
    """Proveedor Anthropic (Claude)"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.anthropic")
        
        try:
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=config.api_key,
                base_url=config.url
            )
            self.logger.info(f"[AnthropicProvider] Conectado a Anthropic")
        except ImportError:
            raise ImportError("Anthropic no está instalado. Ejecuta: pip install anthropic")
        except Exception as e:
            self.logger.error(f"[AnthropicProvider] Error conectando a Anthropic: {e}")
            raise
    
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        try:
            # Convertir formato OpenAI a Anthropic
            system_message = ""
            user_messages = []
            
            for msg in request.messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                elif msg["role"] == "user":
                    user_messages.append(msg["content"])
                elif msg["role"] == "assistant":
                    user_messages.append(f"Assistant: {msg['content']}")
            
            # Construir prompt para Claude
            prompt = f"{system_message}\n\n" + "\n\n".join(user_messages)
            
            response = self.client.messages.create(
                model=request.model or "claude-3-sonnet-20240229",
                max_tokens=request.max_tokens or 1000,
                temperature=request.temperature or 0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                usage={"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
                finish_reason=response.stop_reason
            )
        except Exception as e:
            self.logger.error(f"[AnthropicProvider] Error en chat_completion: {e}")
            raise
    
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        return ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
    
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        try:
            self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception as e:
            self.logger.error(f"[AnthropicProvider] Health check falló: {e}")
            return False


class GoogleProvider(LLMProvider):
    """Proveedor Google (Gemini)"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.google")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
            self.logger.info("[GoogleProvider] Conectado a Google Gemini")
        except ImportError:
            raise ImportError("Google Generative AI no está instalado. Ejecuta: pip install google-generativeai")
        except Exception as e:
            self.logger.error(f"[GoogleProvider] Error conectando a Google: {e}")
            raise
    
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        try:
            # Convertir formato OpenAI a Gemini
            prompt = ""
            for msg in request.messages:
                if msg["role"] == "user":
                    prompt += f"{msg['content']}\n"
                elif msg["role"] == "assistant":
                    prompt += f"Assistant: {msg['content']}\n"
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": request.temperature or 0.7,
                    "max_output_tokens": request.max_tokens or 1000
                }
            )
            
            return LLMResponse(
                content=response.text,
                model="gemini-pro",
                usage={"input_tokens": len(prompt), "output_tokens": len(response.text)},
                finish_reason="stop"
            )
        except Exception as e:
            self.logger.error(f"[GoogleProvider] Error en chat_completion: {e}")
            raise
    
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        return ["gemini-pro", "gemini-pro-vision"]
    
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        try:
            response = self.model.generate_content("test", max_tokens=1)
            return True
        except Exception as e:
            self.logger.error(f"[GoogleProvider] Health check falló: {e}")
            return False


class CohereProvider(LLMProvider):
    """Proveedor Cohere"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.cohere")
        
        try:
            import cohere
            self.client = cohere.Client(api_key=config.api_key)
            self.logger.info("[CohereProvider] Conectado a Cohere")
        except ImportError:
            raise ImportError("Cohere no está instalado. Ejecuta: pip install cohere")
        except Exception as e:
            self.logger.error(f"[CohereProvider] Error conectando a Cohere: {e}")
            raise
    
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        try:
            # Convertir formato OpenAI a Cohere
            prompt = ""
            for msg in request.messages:
                if msg["role"] == "user":
                    prompt += f"User: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    prompt += f"Assistant: {msg['content']}\n"
            
            response = self.client.generate(
                model=request.model or "command",
                prompt=prompt,
                temperature=request.temperature or 0.7,
                max_tokens=request.max_tokens or 1000
            )
            
            return LLMResponse(
                content=response.generations[0].text,
                model=response.model,
                usage={"input_tokens": len(prompt), "output_tokens": len(response.generations[0].text)},
                finish_reason="stop"
            )
        except Exception as e:
            self.logger.error(f"[CohereProvider] Error en chat_completion: {e}")
            raise
    
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        return ["command", "command-light", "command-nightly"]
    
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        try:
            response = self.client.generate(
                model="command",
                prompt="test",
                max_tokens=1
            )
            return True
        except Exception as e:
            self.logger.error(f"[CohereProvider] Health check falló: {e}")
            return False


class LLMAdapter(BaseAdapter):
    """
    🔧 LLM Adapter para la Fase 9
    
    Implementa:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Google (Gemini)
    - Cohere
    - Configuración por ENV
    - Fallbacks automáticos
    """
    
    def __init__(self, config: Optional[AdapterConfig] = None):
        if config is None:
            config = self._load_config_from_env()
        
        super().__init__(AdapterType.LLM, config)
        self.provider = self._create_provider()
        
        self.logger.info(f"[LLMAdapter] Inicializado con {config.provider}")
    
    def _load_config_from_env(self) -> AdapterConfig:
        """Cargar configuración desde variables de entorno"""
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        url = os.getenv("LLM_URL")
        api_key = os.getenv("LLM_API_KEY")
        timeout = int(os.getenv("LLM_TIMEOUT", "60"))
        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        batch_size = int(os.getenv("LLM_BATCH_SIZE", "1"))
        
        return AdapterConfig(
            provider=provider,
            url=url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            batch_size=batch_size
        )
    
    def _create_provider(self) -> LLMProvider:
        """Crear proveedor de LLM según configuración"""
        if self.config.provider == "openai":
            return OpenAIProvider(self.config)
        elif self.config.provider == "anthropic":
            return AnthropicProvider(self.config)
        elif self.config.provider == "google":
            return GoogleProvider(self.config)
        elif self.config.provider == "cohere":
            return CohereProvider(self.config)
        else:
            raise ValueError(f"Proveedor de LLM no soportado: {self.config.provider}")
    
    def chat_completion(self, request: LLMRequest) -> LLMResponse:
        """Generar completación de chat"""
        start_time = time.time()
        
        try:
            response = self.provider.chat_completion(request)
            response.latency_ms = (time.time() - start_time) * 1000
            
            self._update_metrics(True, response.latency_ms / 1000)
            self._log_operation("chat_completion", 
                              model=response.model, 
                              latency_ms=response.latency_ms,
                              success=True)
            
            return response
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_metrics(False, latency_ms / 1000)
            self._log_error("chat_completion", e, 
                          model=request.model,
                          latency_ms=latency_ms)
            raise
    
    def get_models(self) -> List[str]:
        """Obtener modelos disponibles"""
        try:
            models = self.provider.get_models()
            self._log_operation("get_models", models_count=len(models))
            return models
        except Exception as e:
            self._log_error("get_models", e)
            return []
    
    def health_check(self) -> bool:
        """Verificar salud del proveedor"""
        try:
            health = self.provider.health_check()
            self._log_operation("health_check", healthy=health)
            return health
        except Exception as e:
            self._log_error("health_check", e)
            return False
    
    def _health_check(self) -> bool:
        """Verificación de salud del adapter"""
        try:
            # Usar el método health_check del provider
            return self.provider.health_check()
        except Exception as e:
            self.logger.error(f"[LLMAdapter] Health check falló: {e}")
            return False
    
    def initialize(self) -> bool:
        """Inicializar el adapter"""
        try:
            # Verificar conectividad básica
            health = self._health_check()
            if health:
                self.logger.info(f"[LLMAdapter] Inicializado correctamente con {self.config.provider}")
            return health
        except Exception as e:
            self.logger.error(f"[LLMAdapter] Error en inicialización: {e}")
            return False
    
    def get_llm_info(self) -> Dict[str, Any]:
        """Obtener información del LLM"""
        return {
            "provider": self.config.provider,
            "url": self.config.url,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "batch_size": self.config.batch_size,
            "models": self.get_models(),
            "health": self.health_check(),
            "metrics": self.metrics.copy()
        }
