from typing import Dict, Any, Optional, Callable, List
import asyncio
import time
import logging
from datetime import datetime, timezone
from functools import wraps
import hashlib
import secrets
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RateLimitType(Enum):
    USER = "user"
    IP = "ip"
    ENDPOINT = "endpoint"
    GLOBAL = "global"

@dataclass
class SecurityConfig:
    """Configuración de seguridad para diferentes niveles"""
    max_retries: int = 3
    timeout_seconds: float = 30.0
    backoff_factor: float = 2.0
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # segundos
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    enable_validation: bool = True
    log_security_events: bool = True

class SystemHardeningService:
    """
    Servicio central para hardening del sistema y seguridad
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.rate_limiters = {}
        self.security_events = []
        self.config = SecurityConfig()
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Configura configuraciones por defecto para diferentes niveles"""
        self.level_configs = {
            SecurityLevel.LOW: SecurityConfig(
                max_retries=1,
                timeout_seconds=10.0,
                rate_limit_requests=200,
                rate_limit_window=60
            ),
            SecurityLevel.MEDIUM: SecurityConfig(
                max_retries=2,
                timeout_seconds=20.0,
                rate_limit_requests=100,
                rate_limit_window=60
            ),
            SecurityLevel.HIGH: SecurityConfig(
                max_retries=3,
                timeout_seconds=30.0,
                rate_limit_requests=50,
                rate_limit_window=60
            ),
            SecurityLevel.CRITICAL: SecurityConfig(
                max_retries=5,
                timeout_seconds=60.0,
                rate_limit_requests=20,
                rate_limit_window=60
            )
        }
    
    async def secure_operation(
        self,
        operation: Callable,
        security_level: SecurityLevel = SecurityLevel.MEDIUM,
        **kwargs
    ) -> Any:
        """
        Ejecuta una operación con todas las protecciones de seguridad aplicadas
        """
        config = self.level_configs[security_level]
        
        try:
            # 1. Validación de entrada
            if config.enable_validation:
                await self._validate_inputs(kwargs, security_level)
            
            # 2. Rate limiting
            await self._check_rate_limit(security_level)
            
            # 3. Ejecución con timeout y reintentos
            result = await self._execute_with_retries(
                operation, config, **kwargs
            )
            
            # 4. Log de éxito
            self._log_security_event("success", security_level, operation.__name__)
            
            return result
            
        except Exception as e:
            # 5. Log de error y manejo de excepciones
            self._log_security_event("error", security_level, operation.__name__, str(e))
            raise
    
    async def _validate_inputs(self, inputs: Dict[str, Any], security_level: SecurityLevel):
        """Valida entradas según el nivel de seguridad"""
        try:
            # Validación de tamaño de datos
            if 'data' in inputs:
                data_size = len(str(inputs['data']).encode('utf-8'))
                max_size = self.level_configs[security_level].max_request_size
                
                if data_size > max_size:
                    raise ValueError(f"Datos demasiado grandes: {data_size} bytes > {max_size} bytes")
            
            # Validación de tipos
            if 'user_id' in inputs and not isinstance(inputs['user_id'], str):
                raise ValueError("user_id debe ser string")
            
            # Validación de contenido malicioso
            if 'content' in inputs:
                await self._validate_content_security(inputs['content'], security_level)
                
        except Exception as e:
            logger.warning(f"Error en validación de entradas: {e}")
            if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                raise
    
    async def _validate_content_security(self, content: str, security_level: SecurityLevel):
        """Valida contenido por seguridad"""
        # Lista de patrones sospechosos
        suspicious_patterns = [
            "javascript:", "data:text/html", "vbscript:", "onload=",
            "onerror=", "onclick=", "eval(", "document.cookie"
        ]
        
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if pattern in content_lower:
                if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                    raise ValueError(f"Contenido sospechoso detectado: {pattern}")
                else:
                    logger.warning(f"Contenido sospechoso detectado: {pattern}")
    
    async def _check_rate_limit(self, security_level: SecurityLevel):
        """Verifica rate limiting"""
        config = self.level_configs[security_level]
        current_time = time.time()
        
        # Limpiar registros antiguos
        self._cleanup_rate_limiters(current_time)
        
        # Verificar límite
        if len(self.rate_limiters.get(security_level.value, [])) >= config.rate_limit_requests:
            raise Exception(f"Rate limit excedido para nivel {security_level.value}")
        
        # Registrar request
        if security_level.value not in self.rate_limiters:
            self.rate_limiters[security_level.value] = []
        
        self.rate_limiters[security_level.value].append(current_time)
    
    def _cleanup_rate_limiters(self, current_time: float):
        """Limpia registros antiguos de rate limiting"""
        for level, timestamps in self.rate_limiters.items():
            config = self.level_configs[SecurityLevel(level)]
            window_start = current_time - config.rate_limit_window
            
            # Mantener solo timestamps dentro de la ventana
            self.rate_limiters[level] = [
                ts for ts in timestamps if ts > window_start
            ]
    
    async def _execute_with_retries(
        self,
        operation: Callable,
        config: SecurityConfig,
        **kwargs
    ) -> Any:
        """Ejecuta operación con reintentos y timeout"""
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                # Ejecutar con timeout
                result = await asyncio.wait_for(
                    operation(**kwargs),
                    timeout=config.timeout_seconds
                )
                return result
                
            except asyncio.TimeoutError:
                last_exception = Exception(f"Timeout después de {config.timeout_seconds}s")
                logger.warning(f"Timeout en intento {attempt + 1}/{config.max_retries + 1}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Error en intento {attempt + 1}/{config.max_retries + 1}: {e}")
                
                # Si es el último intento, no esperar
                if attempt == config.max_retries:
                    break
                
                # Esperar antes del siguiente intento
                wait_time = config.retry_delay_seconds * (config.backoff_factor ** attempt)
                await asyncio.sleep(wait_time)
        
        # Si llegamos aquí, todos los intentos fallaron
        raise last_exception or Exception("Operación falló después de todos los reintentos")
    
    def _log_security_event(
        self,
        event_type: str,
        security_level: SecurityLevel,
        operation: str,
        details: str = None
    ):
        """Registra eventos de seguridad"""
        if not self.config.log_security_events:
            return
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "security_level": security_level.value,
            "operation": operation,
            "details": details
        }
        
        self.security_events.append(event)
        
        # Log según nivel
        if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            logger.warning(f"Evento de seguridad: {event}")
        else:
            logger.info(f"Evento de seguridad: {event}")
    
    async def get_security_status(self) -> Dict[str, Any]:
        """Obtiene estado de seguridad del sistema"""
        return {
            "security_levels": {
                level.value: {
                    "max_retries": config.max_retries,
                    "timeout_seconds": config.timeout_seconds,
                    "rate_limit_requests": config.rate_limit_requests,
                    "rate_limit_window": config.rate_limit_window
                }
                for level, config in self.level_configs.items()
            },
            "rate_limiters": {
                level: len(timestamps) for level, timestamps in self.rate_limiters.items()
            },
            "security_events_count": len(self.security_events),
            "last_events": self.security_events[-10:] if self.security_events else [],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def update_security_config(
        self,
        security_level: SecurityLevel,
        **config_updates
    ) -> Dict[str, Any]:
        """Actualiza configuración de seguridad para un nivel"""
        try:
            current_config = self.level_configs[security_level]
            
            # Actualizar configuración
            for key, value in config_updates.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)
            
            # Validar configuración
            if current_config.max_retries < 0:
                raise ValueError("max_retries no puede ser negativo")
            
            if current_config.timeout_seconds <= 0:
                raise ValueError("timeout_seconds debe ser positivo")
            
            logger.info(f"Configuración de seguridad actualizada para nivel {security_level.value}")
            
            return {
                "success": True,
                "message": f"Configuración actualizada para nivel {security_level.value}",
                "new_config": {
                    "max_retries": current_config.max_retries,
                    "timeout_seconds": current_config.timeout_seconds,
                    "rate_limit_requests": current_config.rate_limit_requests,
                    "rate_limit_window": current_config.rate_limit_window
                }
            }
            
        except Exception as e:
            logger.error(f"Error actualizando configuración de seguridad: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def reset_rate_limits(self, security_level: SecurityLevel = None):
        """Resetea rate limits para un nivel específico o todos"""
        if security_level:
            if security_level.value in self.rate_limiters:
                self.rate_limiters[security_level.value] = []
                logger.info(f"Rate limits reseteados para nivel {security_level.value}")
        else:
            self.rate_limiters = {}
            logger.info("Todos los rate limits reseteados")
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de seguridad"""
        total_events = len(self.security_events)
        error_events = len([e for e in self.security_events if e["event_type"] == "error"])
        success_events = len([e for e in self.security_events if e["event_type"] == "success"])
        
        return {
            "total_security_events": total_events,
            "error_events": error_events,
            "success_events": success_events,
            "error_rate": (error_events / total_events * 100) if total_events > 0 else 0,
            "rate_limiters_status": {
                level: len(timestamps) for level, timestamps in self.rate_limiters.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# Decorador para aplicar hardening automáticamente
def apply_hardening(security_level: SecurityLevel = SecurityLevel.MEDIUM):
    """Decorador para aplicar hardening automáticamente a funciones"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Buscar instancia de SystemHardeningService
            # Por ahora retornamos la función original
            # TODO: Integrar con ServiceFactory
            return await func(*args, **kwargs)
        return wrapper
    return decorator
