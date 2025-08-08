# app/routers/performance_router.py

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.utils.profiler import generate_performance_report, profiler, db_profiler, memory_profiler
from app.utils.performance_monitor import performance_monitor, log_performance_summary

router = APIRouter(
    prefix="/performance",
    tags=["📊 Performance"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal Server Error"},
    }
)

def get_factory(request: Request, db: Session = Depends(get_db)) -> ServiceFactory:
    return ServiceFactory(db, request)

@router.get(
    "/report",
    summary="📊 Generar reporte de performance",
    description="Genera un reporte completo de performance incluyendo CPU, memoria y consultas de BD",
)
async def get_performance_report(factory: ServiceFactory = Depends(get_factory)):
    """Genera un reporte completo de performance"""
    try:
        report = generate_performance_report()
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando reporte: {str(e)}"
        )

@router.get(
    "/metrics",
    summary="📈 Métricas de performance",
    description="Obtiene métricas en tiempo real de performance",
)
async def get_performance_metrics(factory: ServiceFactory = Depends(get_factory)):
    """Obtiene métricas de performance en tiempo real"""
    try:
        # Métricas del monitor de performance
        slow_ops = performance_monitor.get_slow_operations(threshold=0.5)
        
        # Métricas de BD
        db_stats = db_profiler.get_query_stats()
        slow_queries = db_profiler.get_slow_queries()
        
        # Métricas de memoria
        memory_snapshots = memory_profiler.snapshots
        
        return {
            "success": True,
            "metrics": {
                "slow_operations": slow_ops,
                "database_stats": db_stats,
                "slow_queries": slow_queries[:5],  # Top 5
                "memory_snapshots": memory_snapshots
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo métricas: {str(e)}"
        )

@router.post(
    "/start-profiling",
    summary="🔍 Iniciar profiling",
    description="Inicia el profiling de CPU y memoria",
)
async def start_profiling(factory: ServiceFactory = Depends(get_factory)):
    """Inicia el profiling de performance"""
    try:
        profiler.start_profiling()
        return {
            "success": True,
            "message": "Profiling iniciado"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error iniciando profiling: {str(e)}"
        )

@router.post(
    "/stop-profiling",
    summary="⏹️ Detener profiling",
    description="Detiene el profiling y genera reporte",
)
async def stop_profiling(factory: ServiceFactory = Depends(get_factory)):
    """Detiene el profiling y genera reporte"""
    try:
        cpu_stats = profiler.stop_profiling()
        return {
            "success": True,
            "message": "Profiling detenido",
            "cpu_stats": cpu_stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deteniendo profiling: {str(e)}"
        )

@router.post(
    "/clear-metrics",
    summary="🧹 Limpiar métricas",
    description="Limpia todas las métricas de performance",
)
async def clear_metrics(factory: ServiceFactory = Depends(get_factory)):
    """Limpia todas las métricas de performance"""
    try:
        performance_monitor.clear_metrics()
        db_profiler.query_times.clear()
        db_profiler.slow_queries.clear()
        memory_profiler.snapshots.clear()
        
        return {
            "success": True,
            "message": "Métricas limpiadas"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error limpiando métricas: {str(e)}"
        )

@router.get(
    "/summary",
    summary="📋 Resumen de performance",
    description="Genera un resumen de performance con las operaciones más lentas",
)
async def get_performance_summary(factory: ServiceFactory = Depends(get_factory)):
    """Genera un resumen de performance"""
    try:
        # Log del resumen
        log_performance_summary()
        
        # Obtener métricas
        slow_ops = performance_monitor.get_slow_operations(threshold=0.5)
        db_stats = db_profiler.get_query_stats()
        
        return {
            "success": True,
            "summary": {
                "slow_operations_count": len(slow_ops),
                "database_queries": db_stats["total_queries"],
                "average_query_time": db_stats["avg_time"],
                "slow_queries_count": db_stats["slow_queries"]
            },
            "slow_operations": slow_ops
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando resumen: {str(e)}"
        ) 