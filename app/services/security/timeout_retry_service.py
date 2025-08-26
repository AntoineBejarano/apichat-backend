from typing import Dict, Any, Optional, Callable, List
import asyncio
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"

class CircuitState(Enum):
    CLOSED = "closed"      # Funcionando normalmente
    OPEN = "open"          # Fallando, no permitir requests
    HALF_OPEN = "half_open"  # Probando si se recuperó

@dataclass
class RetryConfig:
    """Configuración para reintentos"""
    max_retries: int = 3
    base_delay: float = 1.0  # segundos
    max_delay: float = 60.0  # segundos
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True  # Añadir variabilidad aleatoria

@dataclass
class TimeoutConfig:
    """Configuración para timeouts"""
    operation_timeout: float = 30.0  # segundos
    total_timeout: float = 300.0     # segundos (timeout total incluyendo reintentos)
    connection_timeout: float = 10.0  # segundos

@dataclass
class CircuitBreakerConfig:
    """Configuración para circuit breaker"""
    failure_threshold: int = 5        # Fallos antes de abrir
    recovery_timeout: float = 60.0    # segundos antes de probar recuperación
    expected_exception: type = Exception  # Excepción que se considera fallo

class TimeoutRetryService:
    """
    Servicio especializado en manejo de timeouts y reintentos
    con patrones de circuit breaker
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        self.retry_stats: Dict[str, Dict[str, Any]] = {}
        self._setup_default_configs()
    
    def _setup_default_configs(self):
        """Configura configuraciones por defecto"""
        self.default_retry_config = RetryConfig()
        self.default_timeout_config = TimeoutConfig()
        self.default_circuit_config = CircuitBreakerConfig()
    
    async def execute_with_timeout_retry(
        self,
        operation: Callable,
        operation_name: str = None,
        retry_config: RetryConfig = None,
        timeout_config: TimeoutConfig = None,
        circuit_breaker_key: str = None,
        **kwargs
    ) -> Any:
        """
        Ejecuta una operación con timeout y reintentos, opcionalmente con circuit breaker
        """
        if operation_name is None:
            operation_name = operation.__name__
        
        if retry_config is None:
            retry_config = self.default_retry_config
        
        if timeout_config is None:
            timeout_config = self.default_timeout_config
        
        # Verificar circuit breaker si se especifica
        if circuit_breaker_key:
            if not await self._can_execute_circuit_breaker(circuit_breaker_key):
                raise Exception(f"Circuit breaker abierto para {circuit_breaker_key}")
        
        start_time = time.time()
        last_exception = None
        
        for attempt in range(retry_config.max_retries + 1):
            try:
                # Ejecutar con timeout de operación
                result = await asyncio.wait_for(
                    operation(**kwargs),
                    timeout=timeout_config.operation_timeout
                )
                
                # Éxito - registrar y retornar
                await self._record_success(operation_name, attempt + 1, start_time)
                
                if circuit_breaker_key:
                    await self._record_circuit_breaker_success(circuit_breaker_key)
                
                return result
                
            except asyncio.TimeoutError:
                last_exception = Exception(f"Timeout después de {timeout_config.operation_timeout}s")
                logger.warning(f"Timeout en {operation_name}, intento {attempt + 1}/{retry_config.max_retries + 1}")
                
            except Exception as e:
                last_exception = e
                logger.warning(f"Error en {operation_name}, intento {attempt + 1}/{retry_config.max_retries + 1}: {e}")
                
                # Verificar si es el último intento
                if attempt == retry_config.max_retries:
                    break
                
                # Verificar timeout total
                if time.time() - start_time > timeout_config.total_timeout:
                    raise Exception(f"Timeout total excedido después de {attempt + 1} intentos")
                
                # Calcular delay para el siguiente intento
                delay = self._calculate_retry_delay(attempt, retry_config)
                logger.info(f"Esperando {delay:.2f}s antes del siguiente intento")
                await asyncio.sleep(delay)
        
        # Si llegamos aquí, todos los intentos fallaron
        await self._record_failure(operation_name, retry_config.max_retries + 1, start_time, str(last_exception))
        
        if circuit_breaker_key:
            await self._record_circuit_breaker_failure(circuit_breaker_key)
        
        raise last_exception or Exception(f"Operación {operation_name} falló después de todos los reintentos")
    
    def _calculate_retry_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calcula delay para el siguiente reintento"""
        if config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * (attempt + 1)
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (2 ** attempt)
        elif config.strategy == RetryStrategy.FIBONACCI:
            delay = config.base_delay * self._fibonacci(attempt + 1)
        else:
            delay = config.base_delay
        
        # Aplicar jitter si está habilitado
        if config.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        # Limitar delay máximo
        return min(delay, config.max_delay)
    
    def _fibonacci(self, n: int) -> int:
        """Calcula número de Fibonacci"""
        if n <= 1:
            return n
        return self._fibonacci(n - 1) + self._fibonacci(n - 2)
    
    async def _record_success(self, operation_name: str, attempts: int, start_time: float):
        """Registra éxito de operación"""
        if operation_name not in self.retry_stats:
            self.retry_stats[operation_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_attempts": 0,
                "total_time": 0.0,
                "last_success": None,
                "last_failure": None
            }
        
        stats = self.retry_stats[operation_name]
        stats["total_calls"] += 1
        stats["successful_calls"] += 1
        stats["total_attempts"] += attempts
        stats["total_time"] += time.time() - start_time
        stats["last_success"] = datetime.now(timezone.utc).isoformat()
    
    async def _record_failure(self, operation_name: str, attempts: int, start_time: float, error: str):
        """Registra fallo de operación"""
        if operation_name not in self.retry_stats:
            self.retry_stats[operation_name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_attempts": 0,
                "total_time": 0.0,
                "last_success": None,
                "last_failure": None
            }
        
        stats = self.retry_stats[operation_name]
        stats["total_calls"] += 1
        stats["failed_calls"] += 1
        stats["total_attempts"] += attempts
        stats["total_time"] += time.time() - start_time
        stats["last_failure"] = datetime.now(timezone.utc).isoformat()
    
    async def _can_execute_circuit_breaker(self, key: str) -> bool:
        """Verifica si se puede ejecutar según el circuit breaker"""
        if key not in self.circuit_breakers:
            # Crear circuit breaker si no existe
            self.circuit_breakers[key] = {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "last_failure_time": None,
                "last_state_change": time.time()
            }
            return True
        
        cb = self.circuit_breakers[key]
        
        if cb["state"] == CircuitState.CLOSED:
            return True
        
        elif cb["state"] == CircuitState.OPEN:
            # Verificar si ha pasado suficiente tiempo para probar recuperación
            if time.time() - cb["last_state_change"] > self.default_circuit_config.recovery_timeout:
                cb["state"] = CircuitState.HALF_OPEN
                cb["last_state_change"] = time.time()
                logger.info(f"Circuit breaker {key} cambiando a HALF_OPEN")
                return True
            return False
        
        elif cb["state"] == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    async def _record_circuit_breaker_success(self, key: str):
        """Registra éxito en circuit breaker"""
        if key in self.circuit_breakers:
            cb = self.circuit_breakers[key]
            if cb["state"] == CircuitState.HALF_OPEN:
                # Recuperación exitosa
                cb["state"] = CircuitState.CLOSED
                cb["failure_count"] = 0
                cb["last_state_change"] = time.time()
                logger.info(f"Circuit breaker {key} recuperado, cambiando a CLOSED")
    
    async def _record_circuit_breaker_failure(self, key: str):
        """Registra fallo en circuit breaker"""
        if key in self.circuit_breakers:
            cb = self.circuit_breakers[key]
            cb["failure_count"] += 1
            cb["last_failure_time"] = time.time()
            
            # Verificar si se debe abrir el circuit breaker
            if cb["failure_count"] >= self.default_circuit_config.failure_threshold:
                cb["state"] = CircuitState.OPEN
                cb["last_state_change"] = time.time()
                logger.warning(f"Circuit breaker {key} abierto después de {cb['failure_count']} fallos")
    
    async def get_circuit_breaker_status(self, key: str = None) -> Dict[str, Any]:
        """Obtiene estado del circuit breaker"""
        if key:
            if key in self.circuit_breakers:
                cb = self.circuit_breakers[key]
                return {
                    "key": key,
                    "state": cb["state"].value,
                    "failure_count": cb["failure_count"],
                    "last_failure_time": cb["last_failure_time"],
                    "last_state_change": cb["last_state_change"],
                    "uptime": time.time() - cb["last_state_change"]
                }
            else:
                return {"key": key, "state": "not_found"}
        
        # Retornar todos los circuit breakers
        return {
            "circuit_breakers": {
                k: {
                    "state": v["state"].value,
                    "failure_count": v["failure_count"],
                    "last_failure_time": v["last_failure_time"],
                    "last_state_change": v["last_state_change"]
                }
                for k, v in self.circuit_breakers.items()
            },
            "total_circuit_breakers": len(self.circuit_breakers)
        }
    
    async def reset_circuit_breaker(self, key: str):
        """Resetea un circuit breaker específico"""
        if key in self.circuit_breakers:
            cb = self.circuit_breakers[key]
            cb["state"] = CircuitState.CLOSED
            cb["failure_count"] = 0
            cb["last_failure_time"] = None
            cb["last_state_change"] = time.time()
            logger.info(f"Circuit breaker {key} reseteado")
    
    async def get_retry_statistics(self, operation_name: str = None) -> Dict[str, Any]:
        """Obtiene estadísticas de reintentos"""
        if operation_name:
            if operation_name in self.retry_stats:
                stats = self.retry_stats[operation_name]
                return {
                    "operation_name": operation_name,
                    "total_calls": stats["total_calls"],
                    "successful_calls": stats["successful_calls"],
                    "failed_calls": stats["failed_calls"],
                    "success_rate": (stats["successful_calls"] / stats["total_calls"] * 100) if stats["total_calls"] > 0 else 0,
                    "average_attempts": stats["total_attempts"] / stats["total_calls"] if stats["total_calls"] > 0 else 0,
                    "average_time": stats["total_time"] / stats["total_calls"] if stats["total_calls"] > 0 else 0,
                    "last_success": stats["last_success"],
                    "last_failure": stats["last_failure"]
                }
            else:
                return {"operation_name": operation_name, "not_found": True}
        
        # Retornar estadísticas de todas las operaciones
        return {
            "operations": {
                name: {
                    "total_calls": stats["total_calls"],
                    "successful_calls": stats["successful_calls"],
                    "failed_calls": stats["failed_calls"],
                    "success_rate": (stats["successful_calls"] / stats["total_calls"] * 100) if stats["total_calls"] > 0 else 0
                }
                for name, stats in self.retry_stats.items()
            },
            "total_operations": len(self.retry_stats)
        }
    
    async def update_config(
        self,
        retry_config: RetryConfig = None,
        timeout_config: TimeoutConfig = None,
        circuit_config: CircuitBreakerConfig = None
    ) -> Dict[str, Any]:
        """Actualiza configuraciones del servicio"""
        try:
            if retry_config:
                self.default_retry_config = retry_config
            
            if timeout_config:
                self.default_timeout_config = timeout_config
            
            if circuit_config:
                self.default_circuit_config = circuit_config
            
            logger.info("Configuraciones de TimeoutRetryService actualizadas")
            
            return {
                "success": True,
                "message": "Configuraciones actualizadas correctamente",
                "new_configs": {
                    "retry": {
                        "max_retries": self.default_retry_config.max_retries,
                        "base_delay": self.default_retry_config.base_delay,
                        "strategy": self.default_retry_config.strategy.value
                    },
                    "timeout": {
                        "operation_timeout": self.default_timeout_config.operation_timeout,
                        "total_timeout": self.default_timeout_config.total_timeout
                    },
                    "circuit_breaker": {
                        "failure_threshold": self.default_circuit_config.failure_threshold,
                        "recovery_timeout": self.default_circuit_config.recovery_timeout
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error actualizando configuraciones: {e}")
            return {
                "success": False,
                "error": str(e)
            }
