#!/usr/bin/env python3
"""
APIGenerationService - Servicio de generación de cache para definiciones OpenAPI
───────────────────────────────────────────────────────────────────────────────
Implementa:
- Generación automática en background
- Compresión y optimización de OpenAPI
- Integración con notificaciones existentes
- Manejo de errores robusto
"""

import asyncio
import json
import gzip
import hashlib
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone
import time

from app.models.api_cache_model import APICache, APICacheStatus
from app.services.cache.api_cache_service import get_api_cache_service
from app.services.notifications.schema_notification_service import get_schema_notification_service
from app.utils.logger import logger


class APIGenerationService:
    """
    Servicio para generar cache de definiciones OpenAPI en background.
    
    Características:
    - Generación asíncrona no bloqueante
    - Compresión automática con Gzip
    - Integración con sistema de notificaciones
    - Manejo robusto de errores
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # Configuración
        self.max_generation_time = 300  # 5 minutos máximo
        self.max_retries = 3
        self.retry_delay = 60  # 1 minuto entre reintentos
        
        # Estadísticas
        self.generation_stats = {
            'total_generated': 0,
            'total_failed': 0,
            'total_retries': 0,
            'average_generation_time': 0.0
        }
    
    async def generate_cache_for_app(self, app_id: UUID, user_id: UUID, 
                                   openapi_data: Dict[str, Any]) -> bool:
        """
        Genera cache para una definición OpenAPI.
        
        Args:
            app_id: ID de la app
            user_id: ID del usuario
            openapi_data: Datos OpenAPI a procesar
        
        Returns:
            True si se generó exitosamente
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"[APIGenerationService] 🚀 Iniciando generación de cache para app {app_id}")
            
            # 🔧 FASE 7: Servicio de notificaciones
            notification_service = get_schema_notification_service(self.factory)
            
            # Obtener nombre de la app para notificaciones
            app_name = await self._get_app_name(app_id)
            
            # 1. Notificar inicio de generación
            await notification_service.notify_schema_generation_started(user_id, app_id, app_name)
            
            # 2. Actualizar estado de la app a "generating"
            await self._update_app_cache_status(app_id, user_id, APICacheStatus.GENERATING.value)
            
            # 3. Generar cache usando APICacheService
            cache_generated = await self._generate_cache(user_id, app_id, openapi_data)
            
            if cache_generated:
                # 4. Actualizar estado a "ready"
                await self._update_app_cache_status(app_id, user_id, APICacheStatus.READY.value)
                
                # 5. Notificar completado
                execution_time = time.time() - start_time
                await notification_service.notify_schema_generation_completed(user_id, app_id, app_name, execution_time)
                
                # 6. Actualizar estadísticas
                self._update_generation_stats(execution_time, True)
                
                self.logger.info(f"[APIGenerationService] ✅ Cache generado exitosamente para app {app_id}")
                return True
                
            else:
                # 7. Si falla, actualizar estado a "error"
                await self._update_app_cache_status(app_id, user_id, APICacheStatus.ERROR.value)
                
                # 8. Notificar fallo
                await notification_service.notify_schema_generation_failed(
                    user_id, app_id, app_name, "Error en la generación del cache"
                )
                
                # 9. Actualizar estadísticas
                self._update_generation_stats(time.time() - start_time, False)
                
                self.logger.error(f"[APIGenerationService] ❌ Error generando cache para app {app_id}")
                return False
                
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.exception(f"[APIGenerationService] ❌ Error inesperado: {e}")
            
            # Actualizar estado de la app a "error"
            await self._update_app_cache_status(app_id, user_id, APICacheStatus.ERROR.value)
            
            # Notificar fallo inesperado
            try:
                notification_service = get_schema_notification_service(self.factory)
                app_name = await self._get_app_name(app_id)
                await notification_service.notify_schema_generation_failed(user_id, app_id, app_name, str(e))
            except Exception as notify_error:
                self.logger.warning(f"[APIGenerationService] ⚠️ Error enviando notificación de fallo: {notify_error}")
            
            # Actualizar estadísticas
            self._update_generation_stats(execution_time, False)
            
            return False
    
    async def refresh_cache_for_app(self, app_id: UUID, user_id: UUID, 
                                  new_openapi_data: Dict[str, Any]) -> bool:
        """
        Refresca el cache de una app con nuevos datos OpenAPI.
        
        Returns:
            True si se refrescó exitosamente
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"[APIGenerationService] 🔄 Iniciando refresh de cache para app {app_id}")
            
            # 🔧 FASE 7: Servicio de notificaciones
            notification_service = get_schema_notification_service(self.factory)
            
            # Obtener nombre de la app para notificaciones
            app_name = await self._get_app_name(app_id)
            
            # 1. Notificar inicio de refresh
            await notification_service.notify_schema_refresh_started(user_id, app_id, app_name)
            
            # 2. Actualizar estado a "updating"
            await self._update_app_cache_status(app_id, user_id, APICacheStatus.UPDATING.value)
            
            # 3. Generar nuevo cache
            cache_refreshed = await self._generate_cache(user_id, app_id, new_openapi_data)
            
            if cache_refreshed:
                # 4. Actualizar estado a "ready"
                await self._update_app_cache_status(app_id, user_id, APICacheStatus.READY.value)
                
                # 5. Notificar éxito
                await notification_service.notify_schema_refresh_completed(user_id, app_id, app_name, True)
                
                execution_time = time.time() - start_time
                self.logger.info(f"[APIGenerationService] ✅ Cache refresh completado para app {app_id} ({execution_time:.2f}s)")
                return True
                
            else:
                # 6. Si falla, mantener estado anterior
                await self._update_app_cache_status(app_id, user_id, APICacheStatus.READY.value)
                
                # 7. Notificar fallo
                await notification_service.notify_schema_refresh_failed(
                    user_id, app_id, app_name, "Error en el refresh del cache"
                )
                
                self.logger.error(f"[APIGenerationService] ❌ Error en refresh de cache para app {app_id}")
                return False
                
        except Exception as e:
            self.logger.exception(f"[APIGenerationService] ❌ Error inesperado en refresh: {e}")
            
            # Mantener estado anterior
            await self._update_app_cache_status(app_id, user_id, APICacheStatus.READY.value)
            
            # Notificar fallo inesperado
            try:
                notification_service = get_schema_notification_service(self.factory)
                app_name = await self._get_app_name(app_id)
                await notification_service.notify_schema_refresh_failed(user_id, app_id, app_name, str(e))
            except Exception as notify_error:
                self.logger.warning(f"[APIGenerationService] ⚠️ Error enviando notificación de fallo: {notify_error}")
            
            return False
    
    async def generate_cache_batch(self, app_ids: List[UUID], user_id: UUID, 
                                 openapi_data_map: Dict[UUID, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Genera cache para múltiples apps en lote.
        
        Returns:
            Resumen de la generación en lote
        """
        try:
            self.logger.info(f"[APIGenerationService] 📦 Iniciando generación en lote para {len(app_ids)} apps")
            
            results = {
                'total_apps': len(app_ids),
                'successful': 0,
                'failed': 0,
                'skipped': 0,
                'details': []
            }
            
            for app_id in app_ids:
                try:
                    if app_id in openapi_data_map:
                        openapi_data = openapi_data_map[app_id]
                        success = await self.generate_cache_for_app(app_id, user_id, openapi_data)
                        
                        if success:
                            results['successful'] += 1
                            results['details'].append({
                                'app_id': str(app_id),
                                'status': 'success',
                                'message': 'Cache generado exitosamente'
                            })
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'app_id': str(app_id),
                                'status': 'failed',
                                'message': 'Error en generación de cache'
                            })
                    else:
                        results['skipped'] += 1
                        results['details'].append({
                            'app_id': str(app_id),
                            'status': 'skipped',
                            'message': 'Datos OpenAPI no disponibles'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'app_id': str(app_id),
                        'status': 'error',
                        'message': f'Error inesperado: {str(e)}'
                    })
                    
                    self.logger.error(f"[APIGenerationService] ❌ Error procesando app {app_id}: {e}")
            
            self.logger.info(f"[APIGenerationService] 📦 Generación en lote completada: {results['successful']}/{results['total_apps']} exitosas")
            return results
            
        except Exception as e:
            self.logger.error(f"[APIGenerationService] ❌ Error en generación en lote: {e}")
            return {
                'total_apps': len(app_ids),
                'successful': 0,
                'failed': len(app_ids),
                'skipped': 0,
                'details': [],
                'error': str(e)
            }
    
    async def retry_failed_generations(self, max_retries: int = 10) -> Dict[str, Any]:
        """
        Reintenta generaciones fallidas.
        
        Returns:
            Resumen de reintentos
        """
        try:
            self.logger.info(f"[APIGenerationService] 🔄 Iniciando reintentos de generaciones fallidas")
            
            # Obtener apps con estado de error
            api_cache_service = get_api_cache_service(self.factory.get_db())
            failed_apis = await api_cache_service.get_apis_needing_refresh(max_results=max_retries)
            
            if not failed_apis:
                self.logger.info("[APIGenerationService] ✅ No hay generaciones fallidas para reintentar")
                return {'total_retries': 0, 'successful': 0, 'failed': 0}
            
            results = {
                'total_retries': len(failed_apis),
                'successful': 0,
                'failed': 0,
                'details': []
            }
            
            for api_info in failed_apis:
                try:
                    app_id = UUID(api_info['app_id'])
                    user_id = UUID(api_info['user_id'])
                    
                    # Obtener datos OpenAPI originales (implementar según tu modelo)
                    openapi_data = await self._get_original_openapi_data(app_id, user_id)
                    
                    if openapi_data:
                        success = await self.generate_cache_for_app(app_id, user_id, openapi_data)
                        
                        if success:
                            results['successful'] += 1
                            results['details'].append({
                                'app_id': api_info['app_id'],
                                'status': 'retry_success',
                                'message': 'Reintento exitoso'
                            })
                        else:
                            results['failed'] += 1
                            results['details'].append({
                                'app_id': api_info['app_id'],
                                'status': 'retry_failed',
                                'message': 'Reintento fallido'
                            })
                    else:
                        results['failed'] += 1
                        results['details'].append({
                            'app_id': api_info['app_id'],
                            'status': 'retry_skipped',
                            'message': 'Datos OpenAPI no disponibles'
                        })
                        
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'app_id': api_info['app_id'],
                        'status': 'retry_error',
                        'message': f'Error en reintento: {str(e)}'
                    })
                    
                    self.logger.error(f"[APIGenerationService] ❌ Error en reintento para app {api_info['app_id']}: {e}")
            
            self.logger.info(f"[APIGenerationService] 🔄 Reintentos completados: {results['successful']}/{results['total_retries']} exitosos")
            return results
            
        except Exception as e:
            self.logger.error(f"[APIGenerationService] ❌ Error en reintentos: {e}")
            return {'total_retries': 0, 'successful': 0, 'failed': 0, 'error': str(e)}
    
    def get_generation_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de generación"""
        return {
            'generation_stats': self.generation_stats.copy(),
            'service_status': 'active',
            'max_generation_time': self.max_generation_time,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay
        }
    
    def update_config(self, **kwargs) -> None:
        """Actualiza configuración del servicio"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"[APIGenerationService] ⚙️ Configuración actualizada: {key} = {value}")
    
    # Métodos privados
    
    async def _generate_cache(self, user_id: UUID, app_id: UUID, 
                            openapi_data: Dict[str, Any]) -> bool:
        """
        Genera el cache para una definición OpenAPI.
        
        Returns:
            True si se generó exitosamente
        """
        try:
            # Obtener servicio de cache
            api_cache_service = get_api_cache_service(self.factory.get_db())
            
            # Generar cache con nivel de enriquecimiento 1 (básico)
            success = await api_cache_service.set_api_cache(
                user_id=user_id,
                app_id=app_id,
                api_data=openapi_data,
                enrichment_level=1,
                ttl_hours=24
            )
            
            if success:
                self.logger.info(f"[APIGenerationService] ✅ Cache generado para app {app_id}")
                return True
            else:
                self.logger.error(f"[APIGenerationService] ❌ Error generando cache para app {app_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"[APIGenerationService] ❌ Error en _generate_cache: {e}")
            return False
    
    async def _update_app_cache_status(self, app_id: UUID, user_id: UUID, status: int) -> bool:
        """
        Actualiza el estado del cache de una app.
        
        Returns:
            True si se actualizó exitosamente
        """
        try:
            # Obtener servicio de cache
            api_cache_service = get_api_cache_service(self.factory.get_db())
            
            # Buscar entrada existente
            cache_entry = api_cache_service.db.query(APICache).filter(
                APICache.app_id == app_id,
                APICache.user_id == user_id
            ).first()
            
            if cache_entry:
                cache_entry.status = status
                cache_entry.updated_at = datetime.now(timezone.utc)
                api_cache_service.db.commit()
                return True
            else:
                # Crear nueva entrada si no existe
                cache_entry = APICache(
                    app_id=app_id,
                    user_id=user_id,
                    status=status,
                    fingerprint="",  # Se generará cuando se complete
                    fingerprint_light="",
                    openapi_compressed="",
                    openapi_original_size=0,
                    openapi_compressed_size=0
                )
                api_cache_service.db.add(cache_entry)
                api_cache_service.db.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"[APIGenerationService] ❌ Error actualizando estado: {e}")
            try:
                api_cache_service.db.rollback()
            except:
                pass
            return False
    
    async def _get_app_name(self, app_id: UUID) -> str:
        """
        Obtiene el nombre de la app.
        """
        try:
            # Implementar según tu modelo de App
            # Por ahora retornamos un nombre genérico
            return f"App {str(app_id)[:8]}"
            
        except Exception as e:
            self.logger.warning(f"[APIGenerationService] ⚠️ Error obteniendo nombre de app {app_id}: {e}")
            return "Unknown App"
    
    async def _get_original_openapi_data(self, app_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene los datos OpenAPI originales para reintento.
        Implementar según tu modelo de datos.
        """
        try:
            # Implementar según tu modelo de App o OpenAPIIntegration
            # Por ahora retornamos None
            return None
            
        except Exception as e:
            self.logger.warning(f"[APIGenerationService] ⚠️ Error obteniendo datos OpenAPI para app {app_id}: {e}")
            return None
    
    def _update_generation_stats(self, execution_time: float, success: bool) -> None:
        """Actualiza estadísticas de generación"""
        if success:
            self.generation_stats['total_generated'] += 1
            
            # Actualizar tiempo promedio
            total_time = self.generation_stats['average_generation_time'] * (self.generation_stats['total_generated'] - 1)
            total_time += execution_time
            self.generation_stats['average_generation_time'] = total_time / self.generation_stats['total_generated']
        else:
            self.generation_stats['total_failed'] += 1


# Instancia global del servicio de generación de cache de API
api_generation_service = None


def get_api_generation_service(factory) -> APIGenerationService:
    """Obtiene la instancia global del servicio de generación de cache de API"""
    global api_generation_service
    if api_generation_service is None:
        api_generation_service = APIGenerationService(factory)
    return api_generation_service


# Funciones helper para FastAPI BackgroundTasks

async def generate_api_cache_background(app_id: UUID, user_id: UUID, 
                                     openapi_data: Dict[str, Any], factory) -> None:
    """
    Función helper para ejecutar generación de cache en background.
    
    Args:
        app_id: ID de la app
        user_id: ID del usuario
        openapi_data: Datos OpenAPI a procesar
        factory: ServiceFactory
    """
    try:
        service = get_api_generation_service(factory)
        await service.generate_cache_for_app(app_id, user_id, openapi_data)
    except Exception as e:
        logger.error(f"[generate_api_cache_background] ❌ Error: {e}")


async def refresh_api_cache_background(app_id: UUID, user_id: UUID, 
                                    new_openapi_data: Dict[str, Any], factory) -> None:
    """
    Función helper para ejecutar refresh de cache en background.
    
    Args:
        app_id: ID de la app
        user_id: ID del usuario
        new_openapi_data: Nuevos datos OpenAPI
        factory: ServiceFactory
    """
    try:
        service = get_api_generation_service(factory)
        await service.refresh_cache_for_app(app_id, user_id, new_openapi_data)
    except Exception as e:
        logger.error(f"[refresh_api_cache_background] ❌ Error: {e}")


async def generate_api_cache_batch_background(app_ids: List[UUID], user_id: UUID, 
                                           openapi_data_map: Dict[UUID, Dict[str, Any]], 
                                           factory) -> None:
    """
    Función helper para ejecutar generación en lote en background.
    
    Args:
        app_ids: Lista de IDs de apps
        user_id: ID del usuario
        openapi_data_map: Mapa de datos OpenAPI por app
        factory: ServiceFactory
    """
    try:
        service = get_api_generation_service(factory)
        await service.generate_cache_batch(app_ids, user_id, openapi_data_map)
    except Exception as e:
        logger.error(f"[generate_api_cache_batch_background] ❌ Error: {e}")
