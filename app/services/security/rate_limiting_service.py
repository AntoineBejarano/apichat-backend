from typing import Dict, Any, Optional, List, Union
import time
import logging
import asyncio
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

class RateLimitStrategy(Enum):
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"

class RateLimitScope(Enum):
    USER = "user"
    IP = "ip"
    ENDPOINT = "endpoint"
    GLOBAL = "global"
    CUSTOM = "custom"

@dataclass
class RateLimitConfig:
    """Configuración para rate limiting"""
    max_requests: int = 100
    window_seconds: int = 60
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: int = 10  # Para token bucket
    refill_rate: float = 1.0  # tokens por segundo para token bucket

@dataclass
class RateLimitResult:
    """Resultado de verificación de rate limit"""
    allowed: bool
    remaining: int
    reset_time: float
    retry_after: Optional[float] = None
    limit_exceeded: bool = False

class RateLimitingService:
    """
    Servicio de rate limiting con múltiples estrategias y backends
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.limiters: Dict[str, Dict[str, Any]] = {}
        self.configs: Dict[str, RateLimitConfig] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Configura configuraciones por defecto"""
        self.default_configs = {
            RateLimitScope.USER: RateLimitConfig(
                max_requests=100,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),
            RateLimitScope.IP: RateLimitConfig(
                max_requests=200,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),
            RateLimitScope.ENDPOINT: RateLimitConfig(
                max_requests=50,
                window_seconds=60,
                strategy=RateLimitStrategy.FIXED_WINDOW
            ),
            RateLimitScope.GLOBAL: RateLimitConfig(
                max_requests=1000,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            )
        }
    
    async def check_rate_limit(
        self,
        scope: RateLimitScope,
        identifier: str,
        custom_config: RateLimitConfig = None
    ) -> RateLimitResult:
        """
        Verifica si se permite una request según el rate limit
        """
        config = custom_config or self.default_configs[scope]
        limiter_key = f"{scope.value}:{identifier}"
        
        try:
            if config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return await self._check_fixed_window(limiter_key, config)
            elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return await self._check_sliding_window(limiter_key, config)
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return await self._check_token_bucket(limiter_key, config)
            elif config.strategy == RateLimitStrategy.LEAKY_BUCKET:
                return await self._check_leaky_bucket(limiter_key, config)
            else:
                raise ValueError(f"Estrategia de rate limiting no soportada: {config.strategy}")
                
        except Exception as e:
            logger.error(f"Error verificando rate limit para {limiter_key}: {e}")
            # En caso de error, permitir la request
            return RateLimitResult(
                allowed=True,
                remaining=999,
                reset_time=time.time() + 60,
                limit_exceeded=False
            )
    
    async def _check_fixed_window(self, limiter_key: str, config: RateLimitConfig) -> RateLimitResult:
        """Implementa rate limiting de ventana fija"""
        current_time = time.time()
        window_start = int(current_time / config.window_seconds) * config.window_seconds
        
        if limiter_key not in self.limiters:
            self.limiters[limiter_key] = {
                "window_start": window_start,
                "request_count": 0
            }
        
        limiter = self.limiters[limiter_key]
        
        # Si estamos en una nueva ventana, resetear contador
        if current_time >= limiter["window_start"] + config.window_seconds:
            limiter["window_start"] = window_start
            limiter["request_count"] = 0
        
        # Verificar límite
        if limiter["request_count"] >= config.max_requests:
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=limiter["window_start"] + config.window_seconds,
                retry_after=limiter["window_start"] + config.window_seconds - current_time,
                limit_exceeded=True
            )
        
        # Incrementar contador
        limiter["request_count"] += 1
        
        return RateLimitResult(
            allowed=True,
            remaining=config.max_requests - limiter["request_count"],
            reset_time=limiter["window_start"] + config.window_seconds,
            limit_exceeded=False
        )
    
    async def _check_sliding_window(self, limiter_key: str, config: RateLimitConfig) -> RateLimitResult:
        """Implementa rate limiting de ventana deslizante"""
        current_time = time.time()
        window_start = current_time - config.window_seconds
        
        if limiter_key not in self.limiters:
            self.limiters[limiter_key] = {
                "requests": []
            }
        
        limiter = self.limiters[limiter_key]
        
        # Limpiar requests antiguos
        limiter["requests"] = [
            req_time for req_time in limiter["requests"]
            if req_time > window_start
        ]
        
        # Verificar límite
        if len(limiter["requests"]) >= config.max_requests:
            # Calcular tiempo de espera
            oldest_request = min(limiter["requests"])
            retry_after = oldest_request + config.window_seconds - current_time
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=oldest_request + config.window_seconds,
                retry_after=max(0, retry_after),
                limit_exceeded=True
            )
        
        # Añadir request actual
        limiter["requests"].append(current_time)
        
        return RateLimitResult(
            allowed=True,
            remaining=config.max_requests - len(limiter["requests"]),
            reset_time=current_time + config.window_seconds,
            limit_exceeded=False
        )
    
    async def _check_token_bucket(self, limiter_key: str, config: RateLimitConfig) -> RateLimitResult:
        """Implementa rate limiting con token bucket"""
        current_time = time.time()
        
        if limiter_key not in self.limiters:
            self.limiters[limiter_key] = {
                "tokens": config.burst_size,
                "last_refill": current_time
            }
        
        limiter = self.limiters[limiter_key]
        
        # Refill tokens
        time_passed = current_time - limiter["last_refill"]
        tokens_to_add = time_passed * config.refill_rate
        limiter["tokens"] = min(config.burst_size, limiter["tokens"] + tokens_to_add)
        limiter["last_refill"] = current_time
        
        # Verificar si hay tokens disponibles
        if limiter["tokens"] < 1:
            # Calcular tiempo hasta el próximo token
            tokens_needed = 1 - limiter["tokens"]
            retry_after = tokens_needed / config.refill_rate
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=current_time + retry_after,
                retry_after=retry_after,
                limit_exceeded=True
            )
        
        # Consumir token
        limiter["tokens"] -= 1
        
        return RateLimitResult(
            allowed=True,
            remaining=int(limiter["tokens"]),
            reset_time=current_time + (1 / config.refill_rate),
            limit_exceeded=False
        )
    
    async def _check_leaky_bucket(self, limiter_key: str, config: RateLimitConfig) -> RateLimitResult:
        """Implementa rate limiting con leaky bucket"""
        current_time = time.time()
        
        if limiter_key not in self.limiters:
            self.limiters[limiter_key] = {
                "bucket_level": 0,
                "last_leak": current_time
            }
        
        limiter = self.limiters[limiter_key]
        
        # Leak tokens
        time_passed = current_time - limiter["last_leak"]
        tokens_leaked = time_passed * config.refill_rate
        limiter["bucket_level"] = max(0, limiter["bucket_level"] - tokens_leaked)
        limiter["last_leak"] = current_time
        
        # Verificar si hay espacio en el bucket
        if limiter["bucket_level"] >= config.max_requests:
            # Calcular tiempo hasta que se libere espacio
            tokens_to_leak = limiter["bucket_level"] - config.max_requests + 1
            retry_after = tokens_to_leak / config.refill_rate
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=current_time + retry_after,
                retry_after=retry_after,
                limit_exceeded=True
            )
        
        # Añadir request al bucket
        limiter["bucket_level"] += 1
        
        return RateLimitResult(
            allowed=True,
            remaining=config.max_requests - int(limiter["bucket_level"]),
            reset_time=current_time + (1 / config.refill_rate),
            limit_exceeded=False
        )
    
    async def get_rate_limit_status(self, scope: RateLimitScope = None, identifier: str = None) -> Dict[str, Any]:
        """Obtiene estado de los rate limiters"""
        if scope and identifier:
            limiter_key = f"{scope.value}:{identifier}"
            if limiter_key in self.limiters:
                limiter = self.limiters[limiter_key]
                config = self.default_configs[scope]
                
                return {
                    "limiter_key": limiter_key,
                    "scope": scope.value,
                    "identifier": identifier,
                    "current_usage": self._get_current_usage(limiter, config),
                    "config": {
                        "max_requests": config.max_requests,
                        "window_seconds": config.window_seconds,
                        "strategy": config.strategy.value
                    },
                    "last_updated": time.time()
                }
            else:
                return {"limiter_key": limiter_key, "not_found": True}
        
        # Retornar todos los limiters
        return {
            "limiters": {
                key: {
                    "scope": key.split(":")[0],
                    "identifier": key.split(":")[1] if ":" in key else "unknown",
                    "current_usage": self._get_current_usage(limiter, self._get_config_for_key(key))
                }
                for key, limiter in self.limiters.items()
            },
            "total_limiters": len(self.limiters)
        }
    
    def _get_current_usage(self, limiter: Dict[str, Any], config: RateLimitConfig) -> Dict[str, Any]:
        """Obtiene uso actual de un limiter"""
        if config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return {
                "request_count": limiter.get("request_count", 0),
                "window_start": limiter.get("window_start", 0)
            }
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return {
                "request_count": len(limiter.get("requests", [])),
                "requests": limiter.get("requests", [])
            }
        elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return {
                "tokens": limiter.get("tokens", 0),
                "last_refill": limiter.get("last_refill", 0)
            }
        elif config.strategy == RateLimitStrategy.LEAKY_BUCKET:
            return {
                "bucket_level": limiter.get("bucket_level", 0),
                "last_leak": limiter.get("last_leak", 0)
            }
        else:
            return {"unknown": True}
    
    def _get_config_for_key(self, key: str) -> RateLimitConfig:
        """Obtiene configuración para una key de limiter"""
        scope_str = key.split(":")[0]
        for scope in RateLimitScope:
            if scope.value == scope_str:
                return self.default_configs[scope]
        return RateLimitConfig()  # Configuración por defecto
    
    async def update_rate_limit_config(
        self,
        scope: RateLimitScope,
        new_config: RateLimitConfig
    ) -> Dict[str, Any]:
        """Actualiza configuración de rate limiting para un scope"""
        try:
            self.default_configs[scope] = new_config
            logger.info(f"Configuración de rate limiting actualizada para scope {scope.value}")
            
            return {
                "success": True,
                "message": f"Configuración actualizada para scope {scope.value}",
                "new_config": {
                    "max_requests": new_config.max_requests,
                    "window_seconds": new_config.window_seconds,
                    "strategy": new_config.strategy.value,
                    "burst_size": new_config.burst_size,
                    "refill_rate": new_config.refill_rate
                }
            }
            
        except Exception as e:
            logger.error(f"Error actualizando configuración de rate limiting: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def reset_rate_limits(self, scope: RateLimitScope = None, identifier: str = None):
        """Resetea rate limits"""
        if scope and identifier:
            limiter_key = f"{scope.value}:{identifier}"
            if limiter_key in self.limiters:
                del self.limiters[limiter_key]
                logger.info(f"Rate limit reseteado para {limiter_key}")
        elif scope:
            # Resetear todos los limiters de un scope
            keys_to_remove = [k for k in self.limiters.keys() if k.startswith(f"{scope.value}:")]
            for key in keys_to_remove:
                del self.limiters[key]
            logger.info(f"Rate limits reseteados para scope {scope.value}")
        else:
            # Resetear todos
            self.limiters.clear()
            logger.info("Todos los rate limits reseteados")
    
    async def get_rate_limit_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de rate limiting"""
        total_limiters = len(self.limiters)
        limiters_by_scope = {}
        
        for key in self.limiters.keys():
            scope = key.split(":")[0]
            if scope not in limiters_by_scope:
                limiters_by_scope[scope] = 0
            limiters_by_scope[scope] += 1
        
        return {
            "total_limiters": total_limiters,
            "limiters_by_scope": limiters_by_scope,
            "configs": {
                scope.value: {
                    "max_requests": config.max_requests,
                    "window_seconds": config.window_seconds,
                    "strategy": config.strategy.value
                }
                for scope, config in self.default_configs.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Decorador para aplicar rate limiting automáticamente
def apply_rate_limiting(scope: RateLimitScope, identifier_func: Callable = None):
    """Decorador para aplicar rate limiting automáticamente"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Por ahora retornamos la función original
            # TODO: Integrar con RateLimitingService
            return await func(*args, **kwargs)
        return wrapper
    return decorator
