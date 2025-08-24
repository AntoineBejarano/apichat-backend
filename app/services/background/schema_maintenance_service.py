#!/usr/bin/env python3
"""
SchemaMaintenanceService - Servicio de mantenimiento programado para schemas
────────────────────────────────────────────────────────────────────────────
Implementa jobs programados para:
- Check diario de fingerprints
- Limpieza semanal de caches antiguos
- Background refresh de schemas obsoletos
- Monitoreo de salud del sistema de cache
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_, func

from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.services.cache.redis_schema_cache import redis_schema_cache
from app.services.background.schema_refresh_service import SchemaRefreshService
from app.utils.logger import logger

logger = logging.getLogger(__name__)


class SchemaMaintenanceService:
    """
    Servicio de mantenimiento programado para schemas de bases de datos.
    
    Características:
    - Check diario de fingerprints para detectar cambios
    - Limpieza semanal de caches antiguos y obsoletos
    - Background refresh de schemas obsoletos
    - Monitoreo de salud del sistema de cache
    - Reportes de mantenimiento automáticos
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # Configuración de mantenimiento
        self.daily_check_enabled = True
        self.weekly_cleanup_enabled = True
        self.auto_refresh_enabled = True
        
        # Límites de mantenimiento
        self.max_daily_checks = 100  # Máximo DBs a verificar por día
        self.max_weekly_cleanup = 1000  # Máximo caches a limpiar por semana
        self.max_auto_refresh = 50  # Máximo schemas a refrescar automáticamente
    
    async def run_daily_maintenance(self) -> Dict[str, Any]:
        """
        Ejecuta mantenimiento diario del sistema de schemas.
        
        Returns:
            Reporte del mantenimiento diario
        """
        start_time = time.time()
        logger.info("[SchemaMaintenanceService] 🌅 Iniciando mantenimiento diario")
        
        try:
            maintenance_report = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'daily',
                'status': 'completed',
                'execution_time': 0,
                'checks_performed': 0,
                'changes_detected': 0,
                'caches_invalidated': 0,
                'errors': []
            }
            
            # 1. Check diario de fingerprints
            if self.daily_check_enabled:
                fingerprint_results = await self._daily_fingerprint_check()
                maintenance_report['checks_performed'] = fingerprint_results['total_checked']
                maintenance_report['changes_detected'] = fingerprint_results['changes_detected']
                maintenance_report['caches_invalidated'] = fingerprint_results['caches_invalidated']
                
                if fingerprint_results['errors']:
                    maintenance_report['errors'].extend(fingerprint_results['errors'])
            
            # 2. Health check del sistema
            health_status = await self._check_system_health()
            maintenance_report['system_health'] = health_status
            
            # 3. Limpieza de caches temporales
            cleanup_results = await self._cleanup_temporary_caches()
            maintenance_report['temp_caches_cleaned'] = cleanup_results['cleaned_count']
            
            execution_time = (time.time() - start_time) * 1000
            maintenance_report['execution_time'] = execution_time
            
            logger.info(f"[SchemaMaintenanceService] ✅ Mantenimiento diario completado en {execution_time:.2f}ms")
            return maintenance_report
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error en mantenimiento diario: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'daily',
                'status': 'failed',
                'error': str(e),
                'execution_time': (time.time() - start_time) * 1000
            }
    
    async def run_weekly_maintenance(self) -> Dict[str, Any]:
        """
        Ejecuta mantenimiento semanal del sistema de schemas.
        
        Returns:
            Reporte del mantenimiento semanal
        """
        start_time = time.time()
        logger.info("[SchemaMaintenanceService] 📅 Iniciando mantenimiento semanal")
        
        try:
            maintenance_report = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'weekly',
                'status': 'completed',
                'execution_time': 0,
                'caches_cleaned': 0,
                'schemas_refreshed': 0,
                'storage_freed': 0,
                'errors': []
            }
            
            # 1. Limpieza semanal de caches antiguos
            if self.weekly_cleanup_enabled:
                cleanup_results = await self._weekly_cache_cleanup()
                maintenance_report['caches_cleaned'] = cleanup_results['cleaned_count']
                maintenance_report['storage_freed'] = cleanup_results['storage_freed']
                
                if cleanup_results['errors']:
                    maintenance_report['errors'].extend(cleanup_results['errors'])
            
            # 2. Auto-refresh de schemas obsoletos
            if self.auto_refresh_enabled:
                refresh_results = await self._auto_refresh_obsolete_schemas()
                maintenance_report['schemas_refreshed'] = refresh_results['refreshed_count']
                
                if refresh_results['errors']:
                    maintenance_report['errors'].extend(refresh_results['errors'])
            
            # 3. Optimización de índices (si es necesario)
            optimization_results = await self._optimize_cache_indexes()
            maintenance_report['indexes_optimized'] = optimization_results['optimized_count']
            
            execution_time = (time.time() - start_time) * 1000
            maintenance_report['execution_time'] = execution_time
            
            logger.info(f"[SchemaMaintenanceService] ✅ Mantenimiento semanal completado en {execution_time:.2f}ms")
            return maintenance_report
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error en mantenimiento semanal: {e}")
            return {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': 'weekly',
                'status': 'failed',
                'error': str(e),
                'execution_time': (time.time() - start_time) * 1000
            }
    
    async def _daily_fingerprint_check(self) -> Dict[str, Any]:
        """Ejecuta check diario de fingerprints para detectar cambios"""
        try:
            logger.info("[SchemaMaintenanceService] 🔍 Iniciando check diario de fingerprints")
            
            cache_service = DetailedSchemaCacheService(self.factory)
            
            # Obtener todas las DBs activas (limitado para no sobrecargar)
            active_dbs = self._get_active_databases(limit=self.max_daily_checks)
            
            results = {
                'total_checked': 0,
                'changes_detected': 0,
                'caches_invalidated': 0,
                'errors': []
            }
            
            for db_info in active_dbs:
                try:
                    user_id = db_info['user_id']
                    db_id = db_info['db_id']
                    
                    # Detectar cambios en el schema
                    change_result = await cache_service.detect_schema_changes(user_id, db_id)
                    
                    results['total_checked'] += 1
                    
                    if change_result.get('changes_detected'):
                        results['changes_detected'] += 1
                        results['caches_invalidated'] += 1
                        
                        logger.info(f"[SchemaMaintenanceService] 🔄 Cambios detectados en DB {db_id}")
                    
                    # Pequeña pausa para no sobrecargar el sistema
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"Error verificando DB {db_info.get('db_id', 'unknown')}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.warning(f"[SchemaMaintenanceService] ⚠️ {error_msg}")
            
            logger.info(f"[SchemaMaintenanceService] ✅ Check diario completado: {results['total_checked']} DBs verificadas")
            return results
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error en check diario: {e}")
            return {
                'total_checked': 0,
                'changes_detected': 0,
                'caches_invalidated': 0,
                'errors': [str(e)]
            }
    
    async def _weekly_cache_cleanup(self) -> Dict[str, Any]:
        """Ejecuta limpieza semanal de caches antiguos"""
        try:
            logger.info("[SchemaMaintenanceService] 🧹 Iniciando limpieza semanal de caches")
            
            cache_service = DetailedSchemaCacheService(self.factory)
            
            # Limpiar caches antiguos (más de 30 días sin acceso)
            cleaned_count = cache_service.cleanup_old_caches(older_than_days=30)
            
            # Limpiar caches obsoletos (marcados como OBSOLETE_)
            obsolete_cleanup = await self._cleanup_obsolete_caches()
            
            # Limpiar cache Redis de schemas expirados
            redis_cleanup = await self._cleanup_expired_redis_caches()
            
            results = {
                'cleaned_count': cleaned_count + obsolete_cleanup['cleaned_count'] + redis_cleanup['cleaned_count'],
                'storage_freed': 'N/A',  # Se puede implementar cálculo de storage
                'errors': obsolete_cleanup['errors'] + redis_cleanup['errors']
            }
            
            logger.info(f"[SchemaMaintenanceService] ✅ Limpieza semanal completada: {results['cleaned_count']} caches limpiados")
            return results
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error en limpieza semanal: {e}")
            return {
                'cleaned_count': 0,
                'storage_freed': 0,
                'errors': [str(e)]
            }
    
    async def _auto_refresh_obsolete_schemas(self) -> Dict[str, Any]:
        """Refresca automáticamente schemas obsoletos"""
        try:
            logger.info("[SchemaMaintenanceService] 🔄 Iniciando auto-refresh de schemas obsoletos")
            
            cache_service = DetailedSchemaCacheService(self.factory)
            refresh_service = SchemaRefreshService(self.factory)
            
            # Obtener schemas que necesitan refresh
            obsolete_schemas = cache_service.get_schemas_needing_refresh(
                user_id=self.factory.user.id,
                limit=self.max_auto_refresh
            )
            
            results = {
                'refreshed_count': 0,
                'errors': []
            }
            
            for schema in obsolete_schemas:
                try:
                    # Refrescar schema en background
                    refresh_result = await refresh_service.refresh_schema_for_db(
                        db_id=schema.db_id,
                        user_id=schema.user_id,
                        force=False
                    )
                    
                    if refresh_result.get('success'):
                        results['refreshed_count'] += 1
                        logger.info(f"[SchemaMaintenanceService] ✅ Schema refrescado para DB {schema.db_id}")
                    else:
                        error_msg = f"Error refrescando DB {schema.db_id}: {refresh_result.get('message', 'Unknown error')}"
                        results['errors'].append(error_msg)
                        logger.warning(f"[SchemaMaintenanceService] ⚠️ {error_msg}")
                    
                    # Pausa entre refreshes para no sobrecargar
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    error_msg = f"Error refrescando DB {schema.db_id}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.warning(f"[SchemaMaintenanceService] ⚠️ {error_msg}")
            
            logger.info(f"[SchemaMaintenanceService] ✅ Auto-refresh completado: {results['refreshed_count']} schemas refrescados")
            return results
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error en auto-refresh: {e}")
            return {
                'refreshed_count': 0,
                'errors': [str(e)]
            }
    
    async def _cleanup_obsolete_caches(self) -> Dict[str, Any]:
        """Limpia caches marcados como obsoletos"""
        try:
            # Obtener caches obsoletos
            from app.models.detailed_schema_cache_model import DetailedSchemaCache
            
            obsolete_caches = self.factory.db.query(DetailedSchemaCache).filter(
                DetailedSchemaCache.fingerprint_light.like('OBSOLETE_%')
            ).limit(self.max_weekly_cleanup).all()
            
            cleaned_count = 0
            errors = []
            
            for cache in obsolete_caches:
                try:
                    # Invalidar en Redis
                    redis_schema_cache.invalidate_schema(cache.user_id, cache.db_id)
                    
                    # Eliminar de BD
                    self.factory.db.delete(cache)
                    cleaned_count += 1
                    
                except Exception as e:
                    error_msg = f"Error limpiando cache obsoleto {cache.id}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(f"[SchemaMaintenanceService] ⚠️ {error_msg}")
            
            # Commit de cambios
            self.factory.db.commit()
            
            return {
                'cleaned_count': cleaned_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error limpiando caches obsoletos: {e}")
            return {
                'cleaned_count': 0,
                'errors': [str(e)]
            }
    
    async def _cleanup_expired_redis_caches(self) -> Dict[str, Any]:
        """Limpia caches Redis expirados"""
        try:
            # Redis maneja TTL automáticamente, pero podemos limpiar metadatos obsoletos
            cleaned_count = 0
            errors = []
            
            # Buscar claves de metadatos obsoletas
            pattern = "schema_meta:*"
            try:
                keys = redis_schema_cache.redis_client.keys(pattern)
                
                for key in keys:
                    try:
                        # Verificar si el schema correspondiente existe
                        metadata = redis_schema_cache.redis_client.get(key)
                        if metadata:
                            meta_data = json.loads(metadata.decode('utf-8'))
                            last_updated = meta_data.get('last_updated', 0)
                            
                            # Si no se ha actualizado en más de 7 días, limpiar
                            if time.time() - last_updated > 7 * 24 * 3600:
                                redis_schema_cache.redis_client.delete(key)
                                cleaned_count += 1
                                
                    except Exception as e:
                        # Si hay error con una clave, continuar con las demás
                        continue
                        
            except Exception as e:
                errors.append(f"Error limpiando Redis: {str(e)}")
            
            return {
                'cleaned_count': cleaned_count,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error limpiando Redis: {e}")
            return {
                'cleaned_count': 0,
                'errors': [str(e)]
            }
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """Verifica la salud del sistema de cache"""
        try:
            health_status = {
                'redis_status': 'unknown',
                'database_status': 'unknown',
                'cache_hit_ratio': 0,
                'active_caches': 0,
                'obsolete_caches': 0
            }
            
            # Check Redis
            try:
                redis_health = redis_schema_cache.health_check()
                health_status['redis_status'] = redis_health.get('status', 'unknown')
            except Exception as e:
                health_status['redis_status'] = 'error'
                logger.warning(f"[SchemaMaintenanceService] ⚠️ Error checkeando Redis: {e}")
            
            # Check Database
            try:
                from app.models.detailed_schema_cache_model import DetailedSchemaCache
                
                # Contar caches activos
                active_count = self.factory.db.query(func.count(DetailedSchemaCache.id)).scalar() or 0
                health_status['active_caches'] = active_count
                
                # Contar caches obsoletos
                obsolete_count = self.factory.db.query(func.count(DetailedSchemaCache.id)).filter(
                    DetailedSchemaCache.fingerprint_light.like('OBSOLETE_%')
                ).scalar() or 0
                health_status['obsolete_caches'] = obsolete_count
                
                health_status['database_status'] = 'healthy'
                
            except Exception as e:
                health_status['database_status'] = 'error'
                logger.warning(f"[SchemaMaintenanceService] ⚠️ Error checkeando BD: {e}")
            
            # Cache hit ratio (aproximado)
            try:
                redis_stats = redis_schema_cache.get_cache_stats()
                if redis_stats.get('status') == 'available':
                    keyspace_hits = redis_stats.get('keyspace_hits', 0)
                    keyspace_misses = redis_stats.get('keyspace_misses', 0)
                    total_requests = keyspace_hits + keyspace_misses
                    
                    if total_requests > 0:
                        health_status['cache_hit_ratio'] = (keyspace_hits / total_requests) * 100
                        
            except Exception as e:
                logger.warning(f"[SchemaMaintenanceService] ⚠️ Error calculando hit ratio: {e}")
            
            return health_status
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error checkeando salud del sistema: {e}")
            return {
                'redis_status': 'error',
                'database_status': 'error',
                'cache_hit_ratio': 0,
                'active_caches': 0,
                'obsolete_caches': 0
            }
    
    async def _optimize_cache_indexes(self) -> Dict[str, Any]:
        """Optimiza índices de cache si es necesario"""
        try:
            # Por ahora, solo retornamos que no hay optimizaciones necesarias
            # En el futuro, se pueden implementar optimizaciones de índices
            return {
                'optimized_count': 0,
                'message': 'No optimizaciones necesarias en este momento'
            }
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error optimizando índices: {e}")
            return {
                'optimized_count': 0,
                'message': f'Error: {str(e)}'
            }
    
    def _get_active_databases(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtiene lista de bases de datos activas para mantenimiento"""
        try:
            from app.models.database_model import DatabaseConnection
            
            active_dbs = self.factory.db.query(DatabaseConnection).filter(
                DatabaseConnection.schema_status.in_(['ready', 'updating'])
            ).limit(limit).all()
            
            return [
                {
                    'user_id': db.user_id,
                    'db_id': db.id,
                    'name': db.name,
                    'schema_status': db.schema_status
                }
                for db in active_dbs
            ]
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error obteniendo DBs activas: {e}")
            return []
    
    def get_maintenance_status(self) -> Dict[str, Any]:
        """Obtiene estado actual del servicio de mantenimiento"""
        return {
            'daily_check_enabled': self.daily_check_enabled,
            'weekly_cleanup_enabled': self.weekly_cleanup_enabled,
            'auto_refresh_enabled': self.auto_refresh_enabled,
            'max_daily_checks': self.max_daily_checks,
            'max_weekly_cleanup': self.max_weekly_cleanup,
            'max_auto_refresh': self.max_auto_refresh,
            'last_daily_run': getattr(self, '_last_daily_run', None),
            'last_weekly_run': getattr(self, '_last_weekly_run', None)
        }
    
    def update_config(self, **kwargs) -> bool:
        """Actualiza configuración del servicio de mantenimiento"""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                    logger.info(f"[SchemaMaintenanceService] ✅ Configuración actualizada: {key} = {value}")
            
            return True
            
        except Exception as e:
            logger.error(f"[SchemaMaintenanceService] ❌ Error actualizando configuración: {e}")
            return False


# Funciones helper para usar con FastAPI BackgroundTasks
async def run_daily_maintenance_background(factory) -> None:
    """Función helper para ejecutar mantenimiento diario en background"""
    try:
        service = SchemaMaintenanceService(factory)
        result = await service.run_daily_maintenance()
        
        if result['status'] == 'completed':
            logger.info("[BackgroundTask] ✅ Mantenimiento diario completado")
        else:
            logger.warning(f"[BackgroundTask] ⚠️ Mantenimiento diario falló: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"[BackgroundTask] ❌ Error en mantenimiento diario: {e}")


async def run_weekly_maintenance_background(factory) -> None:
    """Función helper para ejecutar mantenimiento semanal en background"""
    try:
        service = SchemaMaintenanceService(factory)
        result = await service.run_weekly_maintenance()
        
        if result['status'] == 'completed':
            logger.info("[BackgroundTask] ✅ Mantenimiento semanal completado")
        else:
            logger.warning(f"[BackgroundTask] ⚠️ Mantenimiento semanal falló: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"[BackgroundTask] ❌ Error en mantenimiento semanal: {e}")
