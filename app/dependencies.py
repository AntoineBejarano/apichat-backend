# app/dependencies.py

# 🔧 CORRECCIÓN: Este archivo estaba creando servicios sin factory
# Los servicios deben obtenerse a través de ServiceFactory en lugar de crearse directamente

# NOTA: Este archivo parece estar obsoleto. Los servicios se obtienen a través de ServiceFactory
# que se inyecta en los routers y servicios que los necesitan.

# Si necesitas servicios OpenAI o Langchain, úsalos a través de ServiceFactory:
# factory.get_openai_service() o factory.get_langchain_service()

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.service_factory import ServiceFactory
from app.core.database import get_db


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


async def get_service_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    """
    🔧 FUNCIÓN HELPER UNIFICADA: Crea ServiceFactory correctamente para todos los routers
    
    Esta función:
    1. Obtiene el usuario autenticado
    2. Crea el ServiceFactory con los parámetros correctos
    3. Inicializa SOLO la fase core (mínimo necesario)
    4. Las fases adicionales se cargan bajo demanda
    
    Args:
        request: Request de FastAPI
        db: Sesión de base de datos
        
    Returns:
        ServiceFactory con fase core inicializada
    """
    try:
        # Obtener usuario autenticado
        user = await get_authenticated_user(request, db)
        
        # Crear ServiceFactory con parámetros correctos
        factory = ServiceFactory(request, user)
        
        # 🔧 OPTIMIZACIÓN: Solo inicializar fase core (mínimo necesario)
        await factory.prepare_phase_1_core()
        
        return factory
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inicializando ServiceFactory: {str(e)}"
        )

async def get_service_factory_with_ai(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    """
    🔧 FUNCIÓN HELPER PARA ENDPOINTS QUE NECESITAN AI:
    - Chat, agentes, generación de contenido
    - Inicializa fases core + AI
    """
    try:
        user = await get_authenticated_user(request, db)
        factory = ServiceFactory(request, user)
        
        # Inicializar core + AI
        await factory.prepare_phase_1_core()
        await factory.prepare_phase_2_ai()
        
        return factory
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inicializando ServiceFactory con AI: {str(e)}"
        )

async def get_service_factory_with_cache(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    """
    🔧 FUNCIÓN HELPER PARA ENDPOINTS QUE NECESITAN CACHE:
    - Generación de schemas, cache de datos
    - Inicializa fases core + orchestrator (cache)
    """
    try:
        user = await get_authenticated_user(request, db)
        factory = ServiceFactory(request, user)
        
        # Inicializar core + orchestrator (cache)
        await factory.prepare_phase_1_core()
        await factory.prepare_phase_4_orchestrator()
        
        return factory
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inicializando ServiceFactory con cache: {str(e)}"
        )

async def get_service_factory_full(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    """
    🔧 FUNCIÓN HELPER PARA ENDPOINTS COMPLEJOS:
    - Ejecución de queries, workflows complejos
    - Inicializa todas las fases
    """
    try:
        user = await get_authenticated_user(request, db)
        factory = ServiceFactory(request, user)
        
        # Inicializar todas las fases
        await factory.prepare_phase_1_core()
        await factory.prepare_phase_2_ai()
        await factory.prepare_phase_3_execution()
        await factory.prepare_phase_4_orchestrator()
        
        return factory
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inicializando ServiceFactory completo: {str(e)}"
        )


async def get_authenticated_user(request: Request, db: Session):
    """
    Obtiene el usuario autenticado desde la request.
    Busca el token de sesión en cookies, headers o Authorization.
    """
    try:
        # Obtener token de sesión (prioridad: cookies > headers > Authorization)
        session_token = None
        
        # 1. Intentar obtener de cookies
        if hasattr(request, 'cookies') and request.cookies:
            session_token = request.cookies.get("session_token")
        
        # 2. Si no hay cookies, intentar de headers
        if not session_token:
            session_token = request.headers.get("session_token")
        
        # 3. Si no hay headers, intentar de Authorization header
        if not session_token:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                session_token = auth_header.replace("Bearer ", "")
        
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se proporcionó token de sesión"
            )
        
        # Validar sesión y obtener usuario
        from app.services.data.session_service import SessionService
        session_service = SessionService(db)
        session = session_service.validate_session(session_token)
        
        if not session or not session.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión inválida o expirada"
            )
        
        return session.user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticación"
        )
