from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.dependencies import get_current_user_id, get_service_factory
from app.services.security.system_hardening_service import SystemHardeningService, SecurityLevel
from app.services.security.timeout_retry_service import TimeoutRetryService
from app.services.security.rate_limiting_service import RateLimitingService, RateLimitScope
from typing import Dict, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/security/status")
async def get_security_status(
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene estado general de seguridad del sistema"""
    try:
        hardening_service = factory.security.get_system_hardening_service()
        status = await hardening_service.get_security_status()
        
        return {
            "user_id": user_id,
            "security_status": status,
            "timestamp": status.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de seguridad: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/security/metrics")
async def get_security_metrics(
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene métricas de seguridad del sistema"""
    try:
        hardening_service = factory.security.get_system_hardening_service()
        metrics = hardening_service.get_security_metrics()
        
        return {
            "user_id": user_id,
            "security_metrics": metrics,
            "timestamp": metrics.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas de seguridad: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/security/config/update")
async def update_security_config(
    security_level: SecurityLevel,
    config_updates: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Actualiza configuración de seguridad para un nivel específico"""
    try:
        hardening_service = factory.security.get_system_hardening_service()
        result = await hardening_service.update_security_config(security_level, **config_updates)
        
        if result["success"]:
            return {
                "user_id": user_id,
                "message": result["message"],
                "new_config": result["new_config"],
                "timestamp": result.get("timestamp")
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
        
    except Exception as e:
        logger.error(f"Error actualizando configuración de seguridad: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/security/rate-limits/reset")
async def reset_rate_limits(
    scope: Optional[RateLimitScope] = Query(None),
    identifier: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Resetea rate limits para un scope o identificador específico"""
    try:
        hardening_service = factory.security.get_system_hardening_service()
        await hardening_service.reset_rate_limits(scope, identifier)
        
        return {
            "user_id": user_id,
            "message": "Rate limits reseteados correctamente",
            "scope": scope.value if scope else "all",
            "identifier": identifier,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error reseteando rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeout-retry/status")
async def get_timeout_retry_status(
    circuit_breaker_key: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene estado de circuit breakers y reintentos"""
    try:
        timeout_service = factory.security.get_timeout_retry_service()
        
        if circuit_breaker_key:
            status = await timeout_service.get_circuit_breaker_status(circuit_breaker_key)
        else:
            status = await timeout_service.get_circuit_breaker_status()
        
        return {
            "user_id": user_id,
            "circuit_breaker_status": status,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de timeout/retry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/timeout-retry/statistics")
async def get_retry_statistics(
    operation_name: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene estadísticas de reintentos"""
    try:
        timeout_service = factory.security.get_timeout_retry_service()
        stats = await timeout_service.get_retry_statistics(operation_name)
        
        return {
            "user_id": user_id,
            "retry_statistics": stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de reintentos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeout-retry/circuit-breaker/reset")
async def reset_circuit_breaker(
    circuit_breaker_key: str,
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Resetea un circuit breaker específico"""
    try:
        timeout_service = factory.security.get_timeout_retry_service()
        await timeout_service.reset_circuit_breaker(circuit_breaker_key)
        
        return {
            "user_id": user_id,
            "message": f"Circuit breaker {circuit_breaker_key} reseteado correctamente",
            "circuit_breaker_key": circuit_breaker_key,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error reseteando circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/timeout-retry/config/update")
async def update_timeout_retry_config(
    retry_config: Optional[Dict[str, Any]] = None,
    timeout_config: Optional[Dict[str, Any]] = None,
    circuit_config: Optional[Dict[str, Any]] = None,
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Actualiza configuraciones de timeout y reintentos"""
    try:
        timeout_service = factory.security.get_timeout_retry_service()
        result = await timeout_service.update_config(
            retry_config=retry_config,
            timeout_config=timeout_config,
            circuit_config=circuit_config
        )
        
        if result["success"]:
            return {
                "user_id": user_id,
                "message": result["message"],
                "new_configs": result["new_configs"],
                "timestamp": time.time()
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
        
    except Exception as e:
        logger.error(f"Error actualizando configuración de timeout/retry: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rate-limiting/status")
async def get_rate_limit_status(
    scope: Optional[RateLimitScope] = Query(None),
    identifier: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene estado de rate limiting"""
    try:
        rate_limit_service = factory.security.get_rate_limiting_service()
        status = await rate_limit_service.get_rate_limit_status(scope, identifier)
        
        return {
            "user_id": user_id,
            "rate_limit_status": status,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo estado de rate limiting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rate-limiting/metrics")
async def get_rate_limit_metrics(
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Obtiene métricas de rate limiting"""
    try:
        rate_limit_service = factory.security.get_rate_limiting_service()
        metrics = await rate_limit_service.get_rate_limit_metrics()
        
        return {
            "user_id": user_id,
            "rate_limit_metrics": metrics,
            "timestamp": metrics.get("timestamp")
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo métricas de rate limiting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rate-limiting/config/update")
async def update_rate_limit_config(
    scope: RateLimitScope,
    new_config: Dict[str, Any],
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Actualiza configuración de rate limiting para un scope"""
    try:
        rate_limit_service = factory.security.get_rate_limiting_service()
        result = await rate_limit_service.update_rate_limit_config(scope, new_config)
        
        if result["success"]:
            return {
                "user_id": user_id,
                "message": result["message"],
                "new_config": result["new_config"],
                "timestamp": time.time()
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
        
    except Exception as e:
        logger.error(f"Error actualizando configuración de rate limiting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rate-limiting/reset")
async def reset_rate_limits(
    scope: Optional[RateLimitScope] = Query(None),
    identifier: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Resetea rate limits"""
    try:
        rate_limit_service = factory.security.get_rate_limiting_service()
        await rate_limit_service.reset_rate_limits(scope, identifier)
        
        return {
            "user_id": user_id,
            "message": "Rate limits reseteados correctamente",
            "scope": scope.value if scope else "all",
            "identifier": identifier,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error reseteando rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/security/health")
async def get_security_health(
    user_id: str = Depends(get_current_user_id),
    factory = Depends(get_service_factory)
):
    """Endpoint de salud para servicios de seguridad"""
    try:
        # Verificar que todos los servicios de seguridad estén disponibles
        services_status = {}
        
        try:
            hardening_service = factory.security.get_system_hardening_service()
            services_status["system_hardening"] = "available"
        except Exception:
            services_status["system_hardening"] = "unavailable"
        
        try:
            timeout_service = factory.security.get_timeout_retry_service()
            services_status["timeout_retry"] = "available"
        except Exception:
            services_status["timeout_retry"] = "unavailable"
        
        try:
            rate_limit_service = factory.security.get_rate_limiting_service()
            services_status["rate_limiting"] = "available"
        except Exception:
            services_status["rate_limiting"] = "unavailable"
        
        # Determinar estado general
        all_available = all(status == "available" for status in services_status.values())
        overall_status = "healthy" if all_available else "degraded"
        
        return {
            "user_id": user_id,
            "overall_status": overall_status,
            "services_status": services_status,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error verificando salud de seguridad: {e}")
        return {
            "user_id": user_id,
            "overall_status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }
