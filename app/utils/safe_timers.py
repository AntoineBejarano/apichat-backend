# app/utils/safe_timers.py
"""
🔧 FASE 10: Utilidades para timers seguros y logging condicional
"""

import time
import logging
from typing import Optional, Any, Dict
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger(__name__)


class SafeTimer:
    """
    🔧 FASE 10: Timer seguro que no falla si no se puede medir el tiempo.
    """
    
    def __init__(self, name: str = "operation", log_level: str = "info"):
        self.name = name
        self.log_level = log_level.upper()
        self.start_time = None
        self.end_time = None
        self.duration = None
        self._is_running = False
    
    def start(self) -> bool:
        """
        🔧 FASE 10: Iniciar timer de forma segura.
        
        Returns:
            True si se inició correctamente, False en caso contrario
        """
        try:
            self.start_time = time.time()
            self._is_running = True
            return True
        except Exception as e:
            logger.warning(f"[SafeTimer] No se pudo iniciar timer '{self.name}': {e}")
            self.start_time = None
            self._is_running = False
            return False
    
    def stop(self) -> Optional[float]:
        """
        🔧 FASE 10: Detener timer de forma segura.
        
        Returns:
            Duración en segundos si se pudo medir, None en caso contrario
        """
        try:
            if not self._is_running or self.start_time is None:
                logger.warning(f"[SafeTimer] Timer '{self.name}' no estaba ejecutándose")
                return None
            
            self.end_time = time.time()
            self.duration = self.end_time - self.start_time
            self._is_running = False
            return self.duration
            
        except Exception as e:
            logger.warning(f"[SafeTimer] No se pudo detener timer '{self.name}': {e}")
            self.duration = None
            self._is_running = False
            return None
    
    def log_duration(self, message: Optional[str] = None) -> bool:
        """
        🔧 FASE 10: Loggear duración solo si se pudo medir.
        
        Args:
            message: Mensaje personalizado para el log
            
        Returns:
            True si se loggeó correctamente, False en caso contrario
        """
        try:
            if self.duration is None:
                logger.debug(f"[SafeTimer] Timer '{self.name}' no tiene duración válida, saltando log")
                return False
            
            # Crear mensaje por defecto si no se proporciona
            if message is None:
                message = f"Timer '{self.name}' completado"
            
            # Formatear duración de forma legible
            if self.duration < 1.0:
                duration_str = f"{self.duration * 1000:.1f}ms"
            elif self.duration < 60.0:
                duration_str = f"{self.duration:.2f}s"
            else:
                minutes = int(self.duration // 60)
                seconds = self.duration % 60
                duration_str = f"{minutes}m {seconds:.1f}s"
            
            # Loggear según el nivel especificado
            log_message = f"{message} en {duration_str}"
            
            if self.log_level == "DEBUG":
                logger.debug(f"[SafeTimer] {log_message}")
            elif self.log_level == "INFO":
                logger.info(f"[SafeTimer] {log_message}")
            elif self.log_level == "WARNING":
                logger.warning(f"[SafeTimer] {log_message}")
            elif self.log_level == "ERROR":
                logger.error(f"[SafeTimer] {log_message}")
            else:
                logger.info(f"[SafeTimer] {log_message}")
            
            return True
            
        except Exception as e:
            logger.warning(f"[SafeTimer] Error loggeando duración de '{self.name}': {e}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop()
        if exc_type is None:  # Solo loggear si no hubo excepción
            self.log_duration()


@contextmanager
def safe_timer(name: str, log_level: str = "info", log_on_exception: bool = False):
    """
    🔧 FASE 10: Context manager para timer seguro.
    
    Args:
        name: Nombre del timer
        log_level: Nivel de logging para la duración
        log_on_exception: Si loggear duración incluso si hay excepción
    """
    timer = SafeTimer(name, log_level)
    try:
        timer.start()
        yield timer
    except Exception as e:
        if log_on_exception:
            timer.stop()
            timer.log_duration(f"Timer '{name}' falló con excepción")
        raise
    finally:
        timer.stop()
        timer.log_duration()


def timed_operation(name: str = None, log_level: str = "info"):
    """
    🔧 FASE 10: Decorator para operaciones cronometradas de forma segura.
    
    Args:
        name: Nombre de la operación (si no se proporciona, usa el nombre de la función)
        log_level: Nivel de logging para la duración
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = name or func.__name__
            
            with safe_timer(operation_name, log_level) as timer:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    # Loggear duración incluso si falla
                    timer.log_duration(f"Operación '{operation_name}' falló")
                    raise
        
        return wrapper
    return decorator


def measure_execution_time(func_name: str = None, log_level: str = "info"):
    """
    🔧 FASE 10: Decorator alternativo para medir tiempo de ejecución.
    
    Args:
        func_name: Nombre de la función (si no se proporciona, usa el nombre de la función)
        log_level: Nivel de logging para la duración
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            operation_name = func_name or func.__name__
            
            # Intentar medir tiempo de forma segura
            start_time = None
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                return result
            finally:
                # Solo loggear si se pudo medir el tiempo
                if start_time is not None:
                    try:
                        duration = time.time() - start_time
                        
                        # Formatear duración
                        if duration < 1.0:
                            duration_str = f"{duration * 1000:.1f}ms"
                        elif duration < 60.0:
                            duration_str = f"{duration:.2f}s"
                        else:
                            minutes = int(duration // 60)
                            seconds = duration % 60
                            duration_str = f"{minutes}m {seconds:.1f}s"
                        
                        # Loggear según nivel
                        log_message = f"Operación '{operation_name}' completada en {duration_str}"
                        
                        if log_level.upper() == "DEBUG":
                            logger.debug(f"[SafeTimer] {log_message}")
                        elif log_level.upper() == "INFO":
                            logger.info(f"[SafeTimer] {log_message}")
                        elif log_level.upper() == "WARNING":
                            logger.warning(f"[SafeTimer] {log_message}")
                        else:
                            logger.info(f"[SafeTimer] {log_message}")
                            
                    except Exception as e:
                        logger.debug(f"[SafeTimer] No se pudo loggear duración de '{operation_name}': {e}")
        
        return wrapper
    return decorator


def safe_performance_log(operation_name: str, duration: float, log_level: str = "info") -> bool:
    """
    🔧 FASE 10: Loggear performance de forma segura.
    
    Args:
        operation_name: Nombre de la operación
        duration: Duración en segundos
        log_level: Nivel de logging
        
    Returns:
        True si se loggeó correctamente, False en caso contrario
    """
    try:
        if duration is None or duration < 0:
            logger.debug(f"[SafeTimer] Duración inválida para '{operation_name}': {duration}")
            return False
        
        # Formatear duración
        if duration < 1.0:
            duration_str = f"{duration * 1000:.1f}ms"
        elif duration < 60.0:
            duration_str = f"{duration:.2f}s"
        else:
            minutes = int(duration // 60)
            seconds = duration % 60
            duration_str = f"{minutes}m {seconds:.1f}s"
        
        log_message = f"Performance '{operation_name}': {duration_str}"
        
        # Loggear según nivel
        if log_level.upper() == "DEBUG":
            logger.debug(f"[SafeTimer] {log_message}")
        elif log_level.upper() == "INFO":
            logger.info(f"[SafeTimer] {log_message}")
        elif log_level.upper() == "WARNING":
            logger.warning(f"[SafeTimer] {log_message}")
        else:
            logger.info(f"[SafeTimer] {log_message}")
        
        return True
        
    except Exception as e:
        logger.debug(f"[SafeTimer] Error loggeando performance de '{operation_name}': {e}")
        return False

