# app/dependencies.py

# 🔧 CORRECCIÓN: Este archivo estaba creando servicios sin factory
# Los servicios deben obtenerse a través de ServiceFactory en lugar de crearse directamente

# NOTA: Este archivo parece estar obsoleto. Los servicios se obtienen a través de ServiceFactory
# que se inyecta en los routers y servicios que los necesitan.

# Si necesitas servicios OpenAI o Langchain, úsalos a través de ServiceFactory:
# factory.get_openai_service() o factory.get_langchain_service()

from typing import Optional
from fastapi import Depends, HTTPException, status
from app.core.service_factory import ServiceFactory


def get_current_user(factory: ServiceFactory):
    """Obtiene el usuario actual desde el factory"""
    if not factory or not factory.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autenticado"
        )
    return factory.user


def is_admin(factory) -> bool:
    """Verifica si el usuario autenticado es administrador."""
    if hasattr(factory, 'user') and factory.user:
        return bool(getattr(factory.user, "is_admin", False))
    return False
