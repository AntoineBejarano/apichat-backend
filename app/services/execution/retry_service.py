"""
Servicio de reintentos con backoff exponencial para la Fase 15 - Hardening.
Maneja reintentos automáticos para operaciones que pueden fallar temporalmente.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, TypeVar, Union
from functools import wraps

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryService:
    """Servicio para manejar reintentos con backoff exponencial."""
    
    def __init__(self):
        self.max_retries = settings.MAX_RETRIES
        self.backoff_factor = settings.RETRY_BACKOFF_FACTOR
        self.initial_delay = settings.RETRY_DELAY_SECONDS
    
    def retry_with_backoff(
        self,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        initial_delay: Optional[float] = None,
        exceptions: tuple = (Exception,),
        timeout: Optional[float] = None
    ):
        """
        Decorador para reintentos con backoff exponencial.
        
        Args:
            max_retries: Máximo número de reintentos
            backoff_factor: Factor de multiplicación para el delay
            initial_delay: Delay inicial en segundos
            exceptions: Tupla de excepciones que deben causar reintento
            timeout: Timeout total para toda la operación
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                return self._retry_sync(
                    func, *args, **kwargs,
                    max_retries=max_retries,
                    backoff_factor=backoff_factor,
                    initial_delay=initial_delay,
                    exceptions=exceptions,
                    timeout=timeout
                )
            return wrapper
        return decorator
    
    def retry_with_backoff_async(
        self,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        initial_delay: Optional[float] = None,
        exceptions: tuple = (Exception,),
        timeout: Optional[float] = None
    ):
        """
        Decorador para reintentos asíncronos con backoff exponencial.
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def wrapper(*args, **kwargs) -> T:
                return await self._retry_async(
                    func, *args, **kwargs,
                    max_retries=max_retries,
                    backoff_factor=backoff_factor,
                    initial_delay=initial_delay,
                    exceptions=exceptions,
                    timeout=timeout
                )
            return wrapper
        return decorator
    
    def _retry_sync(
        self,
        func: Callable[..., T],
        *args,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        initial_delay: Optional[float] = None,
        exceptions: tuple = (Exception,),
        timeout: Optional[float] = None,
        **kwargs
    ) -> T:
        """Implementación síncrona de reintentos."""
        max_retries = max_retries or self.max_retries
        backoff_factor = backoff_factor or self.backoff_factor
        initial_delay = initial_delay or self.initial_delay
        
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                
                # Verificar timeout total
                if timeout and (time.time() - start_time) > timeout:
                    raise TimeoutError(f"Operación excedió timeout total de {timeout}s")
                
                if attempt > 0:
                    logger.info(f"✅ Operación exitosa en intento {attempt + 1}")
                
                return result
                
            except exceptions as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"❌ Operación falló después de {max_retries + 1} intentos: {e}")
                    raise e
                
                logger.warning(f"⚠️ Intento {attempt + 1} falló: {e}. Reintentando en {delay:.2f}s...")
                
                # Esperar antes del siguiente intento
                time.sleep(delay)
                
                # Calcular delay para el siguiente intento
                delay = min(delay * backoff_factor, 60)  # Máximo 60 segundos
        
        # Nunca debería llegar aquí
        raise last_exception
    
    async def _retry_async(
        self,
        func: Callable[..., T],
        *args,
        max_retries: Optional[int] = None,
        backoff_factor: Optional[float] = None,
        initial_delay: Optional[float] = None,
        exceptions: tuple = (Exception,),
        timeout: Optional[float] = None,
        **kwargs
    ) -> T:
        """Implementación asíncrona de reintentos."""
        max_retries = max_retries or self.max_retries
        backoff_factor = backoff_factor or self.backoff_factor
        initial_delay = initial_delay or self.initial_delay
        
        last_exception = None
        delay = initial_delay
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                result = await func(*args, **kwargs)
                
                # Verificar timeout total
                if timeout and (time.time() - start_time) > timeout:
                    raise TimeoutError(f"Operación excedió timeout total de {timeout}s")
                
                if attempt > 0:
                    logger.info(f"✅ Operación asíncrona exitosa en intento {attempt + 1}")
                
                return result
                
            except exceptions as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"❌ Operación asíncrona falló después de {max_retries + 1} intentos: {e}")
                    raise e
                
                logger.warning(f"⚠️ Intento asíncrono {attempt + 1} falló: {e}. Reintentando en {delay:.2f}s...")
                
                # Esperar antes del siguiente intento
                await asyncio.sleep(delay)
                
                # Calcular delay para el siguiente intento
                delay = min(delay * backoff_factor, 60)  # Máximo 60 segundos
        
        # Nunca debería llegar aquí
        raise last_exception
    
    def should_retry(self, exception: Exception) -> bool:
        """
        Determina si una excepción debe causar reintento.
        
        Args:
            exception: Excepción a evaluar
            
        Returns:
            True si se debe reintentar, False en caso contrario
        """
        # Errores transitorios que se benefician de reintentos
        retryable_errors = (
            ConnectionError,
            TimeoutError,
            OSError,  # Errores de red
        )
        
        # Errores específicos que indican problemas temporales
        retryable_messages = [
            "timeout",
            "timed out",
            "connection refused",
            "connection reset",
            "network is unreachable",
            "temporary failure",
            "service unavailable",
            "too many requests",
            "rate limit",
            "quota exceeded"
        ]
        
        # Verificar tipo de excepción
        if isinstance(exception, retryable_errors):
            return True
        
        # Verificar mensaje de error
        error_message = str(exception).lower()
        if any(msg in error_message for msg in retryable_messages):
            return True
        
        return False
    
    def get_retry_delay(self, attempt: int, base_delay: float = None) -> float:
        """
        Calcula el delay para un intento específico usando backoff exponencial.
        
        Args:
            attempt: Número de intento (0-based)
            base_delay: Delay base en segundos
            
        Returns:
            Delay en segundos para el intento
        """
        base_delay = base_delay or self.initial_delay
        delay = base_delay * (self.backoff_factor ** attempt)
        
        # Aplicar jitter para evitar thundering herd
        jitter = delay * 0.1 * (hash(str(attempt)) % 100) / 100
        delay += jitter
        
        # Limitar delay máximo
        return min(delay, 60)


# Instancia global del servicio
retry_service = RetryService()
