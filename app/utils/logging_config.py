# app/utils/logging_config.py
"""
🔧 FASE 9: Configuración centralizada de logging para evitar duplicación
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    force: bool = False
) -> None:
    """
    🔧 FASE 9: Configurar logging de forma centralizada y evitar duplicaciones.
    
    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Formato personalizado para los logs
        force: Forzar reconfiguración incluso si ya está configurado
    """
    
    # 🔧 FASE 9: Verificar si ya está configurado
    root_logger = logging.getLogger()
    if root_logger.handlers and not force:
        logger = logging.getLogger(__name__)
        logger.debug("🔧 FASE 9: Logging ya configurado, saltando configuración")
        return
    
    # 🔧 FASE 9: Configurar formato por defecto si no se especifica
    if format_string is None:
        format_string = "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
    
    # 🔧 FASE 9: Configurar logging básico
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=force
    )
    
    # 🔧 FASE 9: Configurar loggers específicos para evitar duplicación
    _configure_module_loggers()
    
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 FASE 9: Logging configurado con nivel {level}")


def _configure_module_loggers() -> None:
    """
    🔧 FASE 9: Configurar loggers de módulos específicos para evitar duplicación.
    """
    
    # 🔧 FASE 9: Logger principal de la aplicación
    app_logger = logging.getLogger("apichat")
    app_logger.propagate = False  # Evitar propagación al root
    if not app_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        app_logger.addHandler(handler)
    
    # 🔧 FASE 9: Logger de APIchat (main.py)
    api_logger = logging.getLogger("APIchat")
    api_logger.propagate = False  # Evitar propagación al root
    if not api_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        api_logger.addHandler(handler)
    
    # 🔧 FASE 9: Logger de run_scheduler
    scheduler_logger = logging.getLogger("run_scheduler")
    scheduler_logger.propagate = False  # Evitar propagación al root
    if not scheduler_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        scheduler_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    🔧 FASE 9: Obtener logger configurado correctamente para evitar duplicación.
    
    Args:
        name: Nombre del logger (normalmente __name__)
        
    Returns:
        Logger configurado sin duplicación
    """
    logger = logging.getLogger(name)
    
    # 🔧 FASE 9: Para loggers de módulos, evitar propagación si tienen handlers
    if logger.handlers:
        logger.propagate = False
    
    return logger


def reset_logging() -> None:
    """
    🔧 FASE 9: Resetear configuración de logging (útil para tests).
    """
    # Remover todos los handlers del root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Resetear nivel
    root_logger.setLevel(logging.WARNING)
    
    # Limpiar loggers específicos
    for logger_name in ["apichat", "APIchat", "run_scheduler"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

