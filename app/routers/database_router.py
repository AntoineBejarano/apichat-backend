from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.service_factory import ServiceFactory
from app.dependencies import (
    get_service_factory,
    get_service_factory_with_ai,
    get_service_factory_with_cache,
    get_service_factory_full
)
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionOut,
    DatabaseConnectionCreateResponse,
)
from app.services.background.schema_generation_service import generate_schema_background
from app.services.background.schema_refresh_service import refresh_schema_background
from app.services.background.schema_pipeline_service import SchemaPipelineService
from app.models.user_model import User
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def _get_estimated_completion(schema_status: str) -> str:
    """
    Obtiene el tiempo estimado de completado basado en el estado del schema.
    
    Args:
        schema_status: Estado actual del schema
        
    Returns:
        Tiempo estimado como string
    """
    if schema_status == "pending":
        return "2-5 minutes"
    elif schema_status == "generating":
        return "1-3 minutes"
    elif schema_status == "ready":
        return "Completed"
    elif schema_status == "error":
        return "Failed - requires manual intervention"
    elif schema_status == "connection_error":
        return "Failed - check database connection"
    else:
        return "Unknown"

router = APIRouter(
    prefix="/databases",
    tags=["🗄️ Databases"],
    responses={
        401: {"description": "No autorizado"},
        404: {"description": "Base de datos no encontrada"},
        500: {"description": "Error UUIDerno del servidor"},
    },
)

# 🧩 Inyección del ServiceFactory
# 🔧 OPTIMIZADO: Usar funciones helper según necesidades del endpoint

# Endpoints básicos (solo core)
get_factory_basic = get_service_factory

# Endpoints que necesitan cache
get_factory_with_cache = get_service_factory_with_cache

# Endpoints que necesitan AI
get_factory_with_ai = get_service_factory_with_ai

# Endpoints complejos (todas las fases)
get_factory_full = get_service_factory_full

# 🔧 ELIMINADO: Función local reemplazada por get_service_factory en dependencies.py


@router.post(
    "/",
    response_model=DatabaseConnectionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva conexión",
    response_description="Conexión creada correctamente"
)
async def create_connection(
    data: DatabaseConnectionCreate,
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory_with_cache),  # 🔧 OPTIMIZADO: Necesita cache para schema
):
    """
    🔌 Crear una nueva conexión a una base de datos externa para su uso en sesiones de IA.
    
    El schema se generará automáticamente en background.
    """
    db_service = factory.get_database_service()
    
    # Crear la conexión
    connection = db_service.create_connection(data)
    
    # 🔧 FASE 1: Lanzar pipeline de schema en background
    try:
        schema_pipeline_service = factory.get_schema_pipeline_service()
        if schema_pipeline_service:
            # Iniciar pipeline del nuevo sistema
            pipeline = await schema_pipeline_service.start_pipeline(connection.id, connection.user_id)
            if pipeline:
                logger.info(f"[DatabaseRouter] 🚀 Pipeline de schema iniciado: {pipeline.id}")
            else:
                logger.warning(f"[DatabaseRouter] ⚠️ No se pudo iniciar pipeline, usando método legacy")
                # Fallback al método anterior
                background_tasks.add_task(
                    generate_schema_background, 
                    connection.id,
                    connection.user_id,
                    factory
                )
        else:
            logger.warning(f"[DatabaseRouter] ⚠️ SchemaPipelineService no disponible, usando método legacy")
            # Fallback al método anterior
            background_tasks.add_task(
                generate_schema_background, 
                connection.id,
                connection.user_id,
                factory
            )
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error iniciando pipeline: {e}, usando método legacy")
        # Fallback al método anterior
        background_tasks.add_task(
            generate_schema_background, 
            connection.id,
            connection.user_id,
            factory
        )
    
    # 🔧 NUEVO: Retornar respuesta con mensaje informativo
    return DatabaseConnectionCreateResponse(
        connection=connection,
        message="We are working on adding your database. This may take a few minutes.",
        schema_status="pending",
        estimated_time="2-5 minutes"
    )


@router.get(
    "/",
    response_model=List[DatabaseConnectionOut],
    summary="Listar conexiones",
    response_description="Lista de conexiones activas del usuario"
)
async def list_connections(factory: ServiceFactory = Depends(get_factory_basic)):  # 🔧 OPTIMIZADO: Solo core
    """
    📋 Listar todas las conexiones de bases de datos del usuario autenticado.
    """
    db_service = factory.get_database_service()
    return db_service.get_user_databases()


@router.delete(
    "/{db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar conexión",
    response_description="Conexión eliminada correctamente"
)
async def delete_connection(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_basic),  # 🔧 OPTIMIZADO: Solo core
):
    """
    🧹 Eliminar una conexión de base de datos por su ID.
    """
    db_service = factory.get_database_service()
    success = db_service.delete_connection(db_id)
    if not success:
        raise HTTPException(status_code=404, detail="Base de datos no encontrada")


@router.get(
    "/test/{db_id}",
    summary="Testear conexión por ID",
    response_description="Conexión exitosa"
)
async def test_connection(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_basic),  # 🔧 OPTIMIZADO: Solo core
):
    """
    🧪 Testea si una conexión ya guardada (por ID) es válida y operativa.
    """
    db_service = factory.get_database_service()
    success = db_service.test_connection_by_id(db_id)
    if not success:
        raise HTTPException(status_code=400, detail="Conexión inválida o inaccesible")
    return {"message": "Conexión exitosa ✅"}


@router.put(
    "/{db_id}/schema/refresh",
    summary="🔄 Refrescar schema de base de datos",
    response_description="Schema refresh iniciado en background"
)
async def refresh_database_schema(
    db_id: UUID,
    background_tasks: BackgroundTasks,
    factory: ServiceFactory = Depends(get_factory_with_cache),  # 🔧 OPTIMIZADO: Necesita cache para schema
):
    """
    🔄 Refrescar manualmente el schema de una base de datos.
    
    El schema se regenerará completamente en background, incluyendo:
    - Análisis de la estructura actual de la DB
    - Actualización del cache (Redis + BD)
    - Invalidación de cache anterior
    - Fallback a schema anterior si falla
    
    ⚠️ **Nota**: Este proceso puede tomar varios minutos dependiendo del tamaño de la DB.
    """
    try:
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Lanzar refresh de schema en background
        background_tasks.add_task(
            refresh_schema_background,
            db_id,
            factory.user.id,
            factory,
            False  # force=False por defecto
        )
        
        # Retornar respuesta informativa
        return {
            "success": True,
            "message": "We are refreshing your database schema. This may take a few minutes.",
            "db_id": str(db_id),
            "status": "updating",
            "estimated_time": "2-5 minutes",
            "note": "Your database will remain available during the refresh process"
        }
        
    except HTTPException:
        # Re-lanzar HTTPExceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get(
    "/{db_id}/schema/status",
    summary="📊 Verificar estado del schema",
    response_description="Estado actual del schema de la base de datos"
)
async def get_schema_status(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_basic),  # 🔧 OPTIMIZADO: Solo core
):
    """
    📊 Obtiene el estado actual del schema de una base de datos.
    
    Estados posibles:
    - 'pending': En espera de generación
    - 'generating': Generación en progreso
    - 'ready': Schema generado y listo
    - 'error': Error durante la generación
    - 'connection_error': Error de conexión
    
    Útil para monitorear el progreso de generación de schema.
    """
    try:
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # 🔧 FASE 1: Intentar obtener estado del pipeline primero
        pipeline_status = None
        try:
            schema_pipeline_service = factory.get_schema_pipeline_service()
            if schema_pipeline_service:
                # Buscar pipeline activo para esta DB
                db = factory.get_db()
                from app.models.schema_pipeline_model import SchemaPipeline
                active_pipeline = db.query(SchemaPipeline).filter(
                    SchemaPipeline.database_id == db_id,
                    SchemaPipeline.status.in_(["pending", "running"])
                ).order_by(SchemaPipeline.created_at.desc()).first()
                
                if active_pipeline:
                    # Obtener estado detallado del pipeline
                    pipeline_status = await schema_pipeline_service.get_pipeline_status(active_pipeline.id)
        except Exception as e:
            logger.warning(f"[DatabaseRouter] ⚠️ Error obteniendo estado del pipeline: {e}")
        
        # Retornar estado del schema (con pipeline si está disponible)
        response = {
            "db_id": str(db_id),
            "name": connection.name,
            "schema_status": connection.schema_status,
            "error_message": getattr(connection, 'error_message', None),
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
            "last_schema_update": getattr(connection, 'last_schema_update', None),
            "schema_version": getattr(connection, 'schema_version', None),
            "estimated_completion": _get_estimated_completion(connection.schema_status)
        }
        
        # 🔧 FASE 1: Agregar información del pipeline si está disponible
        if pipeline_status:
            response.update({
                "pipeline_id": pipeline_status["id"],
                "current_stage": pipeline_status["current_stage"],
                "progress_pct": pipeline_status["progress_pct"],
                "trace_id": pipeline_status["trace_id"],
                "elapsed_time_seconds": pipeline_status["elapsed_time_seconds"],
                "remaining_time_seconds": pipeline_status["remaining_time_seconds"],
                "pipeline_status": pipeline_status["status"]
            })
        
        return response
        
    except HTTPException:
        # Re-lanzar HTTPExceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.get(
    "/{db_id}/graph",
    summary="🕸️ Obtener grafo de relaciones del esquema",
    response_description="Grafo de relaciones del esquema de la base de datos"
)
async def get_schema_graph(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_with_cache),  # 🔧 OPTIMIZADO: Necesita cache para grafo
):
    """
    🕸️ Obtiene el grafo de relaciones del esquema de una base de datos.
    
    El grafo incluye:
    - Nodos: tablas y columnas
    - Aristas: relaciones FK, M2M, HAS_COLUMN
    - Caché optimizado para respuesta rápida
    - Matriz de adyacencia para búsquedas
    - Estadísticas de complejidad
    
    Si no existe el grafo, se construye automáticamente.
    """
    try:
        logger.info(f"[DatabaseRouter] 🕸️ Obteniendo grafo para DB {db_id}")
        
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Obtener el servicio del grafo
        graph_service = factory.get_schema_graph_service()
        if not graph_service:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio del grafo no disponible"
            )
        
        # Obtener el grafo existente
        graph = await graph_service.get_graph(db_id, factory.user.id)
        
        if not graph:
            # Construir el grafo automáticamente
            logger.info(f"[DatabaseRouter] 🚀 Construyendo grafo para DB {db_id}")
            
            # Verificar que el schema esté listo
            if connection.schema_status != "ready":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El schema debe estar listo para construir el grafo. Estado actual: " + connection.schema_status
                )
            
            # Construir grafo en background
            asyncio.create_task(
                graph_service.build_graph_from_snapshot(db_id, factory.user.id)
            )
            
            return {
                "success": True,
                "message": "Grafo en construcción. Use GET /{db_id}/graph para ver el progreso.",
                "db_id": str(db_id),
                "status": "building",
                "estimated_time": "30-60 seconds"
            }
        
        # Retornar el grafo completo
        return {
            "success": True,
            "message": "Grafo obtenido exitosamente",
            "graph": graph
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error obteniendo grafo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post(
    "/{db_id}/schema/retry",
    summary="🔄 Reintentar pipeline de schema fallido",
    response_description="Pipeline de schema reintentado"
)
async def retry_schema_pipeline(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_with_cache),  # 🔧 OPTIMIZADO: Necesita cache para reintento
):
    """
    🔄 Reintenta un pipeline de schema que haya fallado.
    
    Este endpoint es útil cuando:
    - El pipeline de schema falló en algún stage
    - Quieres reintentar la generación automáticamente
    - El error fue transitorio y se puede resolver
    
    El proceso:
    1. Busca el pipeline más reciente fallido para esta DB
    2. Verifica que se pueda reintentar (retry_count < max_retries)
    3. Reinicia el pipeline desde el stage inicial
    4. Mantiene el trace_id para trazabilidad
    
    ⚠️ ATENCIÓN: Solo reintenta pipelines fallidos, no regenera desde cero.
    """
    try:
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # 🔧 FASE 1: Intentar reintentar pipeline
        try:
            schema_pipeline_service = factory.get_schema_pipeline_service()
            if schema_pipeline_service:
                # Buscar pipeline fallido más reciente
                db = factory.get_db()
                from app.models.schema_pipeline_model import SchemaPipeline
                failed_pipeline = db.query(SchemaPipeline).filter(
                    SchemaPipeline.database_id == db_id,
                    SchemaPipeline.status == "failed"
                ).order_by(SchemaPipeline.created_at.desc()).first()
                
                if failed_pipeline:
                    if failed_pipeline.can_retry:
                        # Reintentar pipeline
                        retry_success = await schema_pipeline_service.retry_pipeline(failed_pipeline.id)
                        if retry_success:
                            return {
                                "success": True,
                                "message": f"Pipeline {failed_pipeline.id} reintentado exitosamente",
                                "pipeline_id": str(failed_pipeline.id),
                                "retry_count": failed_pipeline.retry_count + 1,
                                "trace_id": failed_pipeline.trace_id
                            }
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="No se pudo reintentar el pipeline"
                            )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Pipeline {failed_pipeline.id} no se puede reintentar (máximo de reintentos alcanzado)"
                        )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No se encontró pipeline fallido para reintentar"
                    )
            else:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Servicio de pipeline no disponible"
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[DatabaseRouter] ❌ Error reintentando pipeline: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno reintentando pipeline: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )

@router.post(
    "/{db_id}/cache/redis/retry",
    summary="🔄 Regenerar completamente el schema desde DB externa",
    response_description="Regeneración completa del schema iniciada"
)
async def retry_redis_cache(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_with_cache),  # 🔧 OPTIMIZADO: Necesita cache para regeneración
):
    """
    🔄 Regenera completamente el schema desde la base de datos externa del usuario.
    
    Este endpoint es útil cuando:
    - Quieres refrescar completamente el cache
    - La DB externa ha cambiado (nuevas tablas, columnas, etc.)
    - El cache está obsoleto o corrupto
    - Quieres forzar una sincronización total
    
    El proceso:
    1. Borra completamente el cache existente
    2. Limpia Redis y memoria
    3. Regenera el schema desde la DB externa
    4. Crea un nuevo cache completamente fresco
    5. Sincroniza con Redis
    
    ⚠️ ATENCIÓN: Este proceso es destructivo y regenera todo desde cero.
    """
    try:
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Verificar que el schema esté listo
        if connection.schema_status != "ready":
            return {
                "success": False,
                "message": "Schema no está listo. Debe estar en estado 'ready' para cachear en Redis.",
                "db_id": str(db_id),
                "current_status": connection.schema_status,
                "note": "Complete la generación del schema primero"
            }
        
        # 🔧 NUEVO: Preparar Fase 4 para acceso a cache
        try:
            await factory.prepare_for_orchestrator()
            logger.info("[DatabaseRouter] ✅ Fase 4 (Orchestrator) preparada para Redis cache")
        except Exception as e:
            logger.warning(f"[DatabaseRouter] ⚠️ No se pudo preparar Fase 4: {e}")
            return {
                "success": False,
                "message": "No se pudo preparar el sistema de cache",
                "db_id": str(db_id),
                "error": str(e)
            }
        
        # 🔥 REGENERACIÓN COMPLETA DEL SCHEMA
        try:
            detailed_cache = factory.get_detailed_schema_cache_service()
            if not detailed_cache:
                return {
                    "success": False,
                    "message": "Servicio de cache detallado no disponible",
                    "db_id": str(db_id)
                }
            
            logger.info(f"[DatabaseRouter] 🔄 Iniciando regeneración completa para DB {db_id}")
            
            # Forzar regeneración completa del schema
            regeneration_result = detailed_cache.force_regenerate_schema(
                user_id=factory.user.id,
                db_id=db_id
            )
            
            if not regeneration_result.get('success', False):
                error_msg = regeneration_result.get('error', 'Error desconocido en la regeneración')
                logger.error(f"[DatabaseRouter] ❌ Error en regeneración: {error_msg}")
                return {
                    "success": False,
                    "message": f"Error regenerando schema: {error_msg}",
                    "db_id": str(db_id),
                    "cache_status": "regeneration_failed"
                }
            
            # 🚀 NUEVO: Generar Graph RAG Pro después de la regeneración
            graph_schema = None
            try:
                logger.info(f"[DatabaseRouter] 🚀 Generando Graph RAG Pro después de regeneración para DB {db_id}")
                graph_schema = detailed_cache._generate_graph_schema(
                    user_id=factory.user.id,
                    db_id=db_id
                )
                
                if graph_schema:
                    # Actualizar el cache con Graph RAG Pro
                    cache_entry = detailed_cache.get_cache_entry(
                        user_id=factory.user.id,
                        db_id=db_id
                    )
                    
                    if cache_entry:
                        cache_entry.graph_schema = graph_schema
                        detailed_cache.db.commit()
                        logger.info(f"[DatabaseRouter] ✅ Graph RAG Pro incluido en cache regenerado para DB {db_id}")
                    else:
                        logger.warning(f"[DatabaseRouter] ⚠️ No se pudo obtener cache entry para actualizar Graph RAG Pro")
                else:
                    logger.warning(f"[DatabaseRouter] ⚠️ No se pudo generar Graph RAG Pro después de regeneración")
                    
            except Exception as e:
                logger.warning(f"[DatabaseRouter] ⚠️ Error generando Graph RAG Pro después de regeneración: {e}")
                # No fallar la regeneración por esto, solo log warning
            
            # ✅ REGENERACIÓN EXITOSA
            details = regeneration_result.get('regeneration_details', {})
            
            # 🚀 NUEVO: Verificar si se generó Graph RAG Pro
            graph_rag_pro_status = "generated" if graph_schema else "not_generated"
            
            logger.info(f"[DatabaseRouter] ✅ Schema regenerado exitosamente para DB {db_id}")
            
            return {
                "success": True,
                "message": "Schema regenerado completamente desde DB externa",
                "db_id": str(db_id),
                "cache_status": "completely_regenerated",
                "regeneration_details": details,
                "graph_rag_pro_status": graph_rag_pro_status,
                "note": "Cache completamente regenerado, sincronizado con Redis e incluye Graph RAG Pro"
            }
                
        except Exception as e:
            logger.error(f"[DatabaseRouter] ❌ Error en regeneración completa: {e}")
            return {
                "success": False,
                "message": f"Error interno: {str(e)}",
                "db_id": str(db_id),
                "cache_status": "internal_error"
            }
        
    except HTTPException:
        # Re-lanzar HTTPExceptions
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor: {str(e)}"
        )


@router.post("/{db_id}/schema/graph-rag-pro")
async def generate_graph_rag_pro_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_with_cache)  # 🔧 OPTIMIZADO: Necesita cache para Graph RAG Pro
):
    """
    Genera un schema enriquecido de nivel Graph RAG Pro.
    
    Incluye:
    - Primary keys y foreign keys
    - Índices y constraints
    - Metadata semántica
    - Grafo de relaciones
    - Estadísticas básicas
    - Patrones de diseño detectados
    - Recomendaciones de consultas
    - Contexto relacional para AI
    """
    try:
        logger.info(f"[DatabaseRouter] 🚀 Generando Graph RAG Pro schema para DB {db_id}")
        
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Obtener el servicio de cache detallado
        detailed_cache = factory.get_detailed_schema_cache_service()
        if not detailed_cache:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio de cache detallado no disponible"
            )
        
        # Generar el schema enriquecido
        graph_schema = detailed_cache._generate_graph_schema(
            user_id=factory.user.id,
            db_id=db_id
        )
        
        if not graph_schema:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo generar el Graph RAG Pro schema"
            )
        
        logger.info(f"[DatabaseRouter] ✅ Graph RAG Pro schema generado para DB {db_id}")
        
        return {
            "success": True,
            "message": "Graph RAG Pro schema generado exitosamente",
            "schema": graph_schema,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error generando Graph RAG Pro schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando Graph RAG Pro schema: {str(e)}"
        )


@router.get("/{db_id}/schema/graph-rag-pro")
async def get_graph_rag_pro_schema(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_with_cache)  # 🔧 OPTIMIZADO: Necesita cache para Graph RAG Pro
):
    """
    Obtiene el Graph RAG Pro schema existente.
    
    Si no existe, lo genera automáticamente.
    """
    try:
        logger.info(f"[DatabaseRouter] 🔍 Obteniendo Graph RAG Pro schema para DB {db_id}")
        
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Obtener el servicio de cache detallado
        detailed_cache = factory.get_detailed_schema_cache_service()
        if not detailed_cache:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio de cache detallado no disponible"
            )
        
        # Obtener el cache existente
        cache_entry = detailed_cache.get_cache_entry(
            user_id=factory.user.id,
            db_id=db_id
        )
        
        if not cache_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró cache para esta base de datos"
            )
        
        # 🔧 CORRECCIÓN: Verificar si ya está en proceso de generación
        if hasattr(cache_entry, 'graph_schema_generating') and cache_entry.graph_schema_generating:
            # Verificar si no ha pasado mucho tiempo (timeout de 10 minutos)
            from datetime import timedelta
            if cache_entry.graph_schema_generating_at and (datetime.now(timezone.utc) - cache_entry.graph_schema_generating_at) < timedelta(minutes=10):
                return {
                    "success": True,
                    "message": "Graph RAG Pro schema está siendo generado",
                    "status": "generating",
                    "estimated_time": "2-5 minutes",
                    "started_at": cache_entry.graph_schema_generating_at.isoformat()
                }
            else:
                # Timeout alcanzado, resetear estado
                logger.warning(f"[DatabaseRouter] ⚠️ Timeout alcanzado para generación de Graph RAG Pro en DB {db_id}")
                cache_entry.graph_schema_generating = False
                cache_entry.graph_schema_generating_at = None
                detailed_cache.db.commit()
        
        # Si no tiene Graph RAG Pro schema, generarlo
        if not cache_entry.graph_schema:
            try:
                # 🔧 CORRECCIÓN: Marcar como en proceso de generación
                cache_entry.graph_schema_generating = True
                cache_entry.graph_schema_generating_at = datetime.now(timezone.utc)
                detailed_cache.db.commit()
                
                logger.info(f"[DatabaseRouter] 🚀 Generando Graph RAG Pro schema para DB {db_id}")
                graph_schema = detailed_cache._generate_graph_schema(
                    user_id=factory.user.id,
                    db_id=db_id
                )
                
                if graph_schema:
                    # Actualizar el cache con el nuevo schema
                    cache_entry.graph_schema = graph_schema
                    cache_entry.graph_schema_generating = False
                    cache_entry.graph_schema_generating_at = None
                    detailed_cache.db.commit()
                    logger.info(f"[DatabaseRouter] ✅ Graph RAG Pro schema guardado para DB {db_id}")
                else:
                    # 🔧 CORRECCIÓN: Resetear estado si falla
                    cache_entry.graph_schema_generating = False
                    cache_entry.graph_schema_generating_at = None
                    detailed_cache.db.commit()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="No se pudo generar el Graph RAG Pro schema"
                    )
                    
            except Exception as e:
                # 🔧 CORRECCIÓN: Resetear estado en caso de error
                try:
                    cache_entry.graph_schema_generating = False
                    cache_entry.graph_schema_generating_at = None
                    detailed_cache.db.commit()
                except:
                    pass
                raise e
        else:
            graph_schema = cache_entry.graph_schema
        
        return {
            "success": True,
            "message": "Graph RAG Pro schema obtenido exitosamente",
            "schema": graph_schema,
            "cached_at": cache_entry.generated_at.isoformat() if cache_entry.generated_at else None,
            "status": "ready"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error obteniendo Graph RAG Pro schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo Graph RAG Pro schema: {str(e)}"
        )


@router.get("/{db_id}/schema/graph-rag-pro/status")
async def get_graph_rag_pro_status(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_basic)  # 🔧 OPTIMIZADO: Solo core
):
    """
    🔍 Obtiene el estado de generación del Graph RAG Pro schema.
    
    Útil para monitorear el progreso sin generar el schema completo.
    """
    try:
        logger.info(f"[DatabaseRouter] 🔍 Verificando estado de Graph RAG Pro para DB {db_id}")
        
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Obtener el servicio de cache detallado
        detailed_cache = factory.get_detailed_schema_cache_service()
        if not detailed_cache:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio de cache detallado no disponible"
            )
        
        # Obtener el cache existente
        cache_entry = detailed_cache.get_cache_entry(
            user_id=factory.user.id,
            db_id=db_id
        )
        
        if not cache_entry:
            return {
                "success": True,
                "db_id": str(db_id),
                "status": "no_cache",
                "message": "No se encontró cache para esta base de datos"
            }
        
        # Verificar estado del Graph RAG Pro schema
        if cache_entry.graph_schema:
            return {
                "success": True,
                "db_id": str(db_id),
                "status": "ready",
                "message": "Graph RAG Pro schema está listo",
                "cached_at": cache_entry.generated_at.isoformat() if cache_entry.generated_at else None
            }
        elif hasattr(cache_entry, 'graph_schema_generating') and cache_entry.graph_schema_generating:
            # Verificar timeout
            from datetime import timedelta
            if cache_entry.graph_schema_generating_at and (datetime.now(timezone.utc) - cache_entry.graph_schema_generating_at) < timedelta(minutes=10):
                return {
                    "success": True,
                    "db_id": str(db_id),
                    "status": "generating",
                    "message": "Graph RAG Pro schema está siendo generado",
                    "started_at": cache_entry.graph_schema_generating_at.isoformat(),
                    "estimated_time": "2-5 minutes"
                }
            else:
                # Timeout alcanzado
                return {
                    "success": True,
                    "db_id": str(db_id),
                    "status": "timeout",
                    "message": "Timeout alcanzado en la generación del Graph RAG Pro schema",
                    "started_at": cache_entry.graph_schema_generating_at.isoformat() if cache_entry.graph_schema_generating_at else None,
                    "note": "La generación se detuvo por timeout. Puede reintentarla."
                }
        else:
            return {
                "success": True,
                "db_id": str(db_id),
                "status": "not_generated",
                "message": "Graph RAG Pro schema no ha sido generado",
                "note": "Use POST /{db_id}/schema/graph-rag-pro para generarlo"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error verificando estado de Graph RAG Pro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verificando estado: {str(e)}"
        )


@router.post("/{db_id}/schema/graph-rag-pro/cancel")
async def cancel_graph_rag_pro_generation(
    db_id: UUID,
    factory: ServiceFactory = Depends(get_factory_basic)  # 🔧 OPTIMIZADO: Solo core
):
    """
    🚫 Cancela la generación en curso del Graph RAG Pro schema.
    
    Útil cuando la generación está atascada o toma demasiado tiempo.
    """
    try:
        logger.info(f"[DatabaseRouter] 🚫 Cancelando generación de Graph RAG Pro para DB {db_id}")
        
        # Verificar que la DB existe y pertenece al usuario
        db_service = factory.get_database_service()
        connection = db_service.get_record(db_id)
        
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Base de datos no encontrada"
            )
        
        # Verificar que pertenece al usuario autenticado
        if connection.user_id != factory.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta base de datos"
            )
        
        # Obtener el servicio de cache detallado
        detailed_cache = factory.get_detailed_schema_cache_service()
        if not detailed_cache:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Servicio de cache detallado no disponible"
            )
        
        # Obtener el cache existente
        cache_entry = detailed_cache.get_cache_entry(
            user_id=factory.user.id,
            db_id=db_id
        )
        
        if not cache_entry:
            return {
                "success": False,
                "db_id": str(db_id),
                "message": "No se encontró cache para esta base de datos"
            }
        
        # Verificar si hay generación en curso
        if not hasattr(cache_entry, 'graph_schema_generating') or not cache_entry.graph_schema_generating:
            return {
                "success": False,
                "db_id": str(db_id),
                "message": "No hay generación en curso para cancelar"
            }
        
        # Cancelar la generación
        cache_entry.graph_schema_generating = False
        cache_entry.graph_schema_generating_at = None
        detailed_cache.db.commit()
        
        logger.info(f"[DatabaseRouter] ✅ Generación de Graph RAG Pro cancelada para DB {db_id}")
        
        return {
            "success": True,
            "db_id": str(db_id),
            "message": "Generación de Graph RAG Pro cancelada exitosamente",
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DatabaseRouter] ❌ Error cancelando generación de Graph RAG Pro: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelando generación: {str(e)}"
        )
