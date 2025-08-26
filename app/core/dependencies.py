from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extrae el user_id del token JWT.
    Por ahora retorna un user_id de prueba para desarrollo.
    """
    try:
        # TODO: Implementar validación real de JWT
        # Por ahora retornamos un user_id de prueba
        token = credentials.credentials
        
        # Simular validación de token
        if not token or len(token) < 10:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido"
            )
        
        # TODO: Decodificar JWT y extraer user_id real
        # Por ahora retornamos un ID de prueba
        user_id = "test_user_123"
        
        logger.info(f"Usuario autenticado: {user_id}")
        return user_id
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en autenticación: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error de autenticación"
        )

async def get_service_factory() -> ServiceFactory:
    """
    Inyecta la instancia de ServiceFactory.
    Por ahora retorna una instancia básica para desarrollo.
    """
    try:
        # TODO: Implementar inyección real de ServiceFactory
        # Por ahora creamos una instancia básica
        factory = ServiceFactory()
        
        logger.debug("ServiceFactory inyectado correctamente")
        return factory
        
    except Exception as e:
        logger.error(f"Error inyectando ServiceFactory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del sistema"
        )
