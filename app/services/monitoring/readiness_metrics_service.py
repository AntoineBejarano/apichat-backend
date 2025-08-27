from typing import Dict, List, Any, Optional
import logging
from datetime import datetime, timezone
from app.services.management.readiness_registry import ReadinessStatus

logger = logging.getLogger(__name__)


class ReadinessMetricsService:
    """Servicio para métricas de readiness del sistema (INTERNO - sin endpoints)"""
    
    def __init__(self, factory):
        self.factory = factory
        self.readiness_registry = factory.readiness_registry
    
    async def get_readiness_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de readiness del sistema (INTERNO)"""
        try:
            # Usar datos del ReadinessRegistry existente
            all_resources = self.readiness_registry.resource_readiness
            
            ready_count = 0
            pending_count = 0
            error_count = 0
            preparing_count = 0
            validating_count = 0
            
            # Contar recursos por estado
            for (resource_type, resource_id), status_data in all_resources.items():
                if isinstance(status_data, dict):
                    status = status_data.get('status')
                else:
                    status = status_data
                
                if status == ReadinessStatus.READY:
                    ready_count += 1
                elif status == ReadinessStatus.PENDING:
                    pending_count += 1
                elif status == ReadinessStatus.ERROR:
                    error_count += 1
                elif status == ReadinessStatus.PREPARING:
                    preparing_count += 1
                elif status == ReadinessStatus.VALIDATING:
                    validating_count += 1
            
            total_resources = len(all_resources)
            readiness_percentage = (ready_count / total_resources * 100) if total_resources > 0 else 0
            
            return {
                'total_resources': total_resources,
                'ready_resources': ready_count,
                'pending_resources': pending_count,
                'error_resources': error_count,
                'preparing_resources': preparing_count,
                'validating_resources': validating_count,
                'readiness_percentage': round(readiness_percentage, 2),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting readiness stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_user_waiting_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de usuarios esperando (INTERNO)"""
        try:
            # Usar datos del ReadinessRegistry existente
            pending_resources = await self.readiness_registry.get_pending_resources()
            
            # Agrupar por tipo de recurso
            resource_types_waiting = {}
            for resource in pending_resources:
                resource_type = resource['type']
                if resource_type not in resource_types_waiting:
                    resource_types_waiting[resource_type] = 0
                resource_types_waiting[resource_type] += 1
            
            # Calcular tiempo estimado de completado
            estimated_completion_time = len(pending_resources) * 3  # 3 segundos por recurso
            
            return {
                'pending_resources_count': len(pending_resources),
                'resource_types_waiting': resource_types_waiting,
                'estimated_completion_time': estimated_completion_time,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting user waiting stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_resource_type_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas por tipo de recurso"""
        try:
            all_resources = self.readiness_registry.resource_readiness
            
            resource_type_stats = {}
            
            for (resource_type, resource_id), status_data in all_resources.items():
                if resource_type not in resource_type_stats:
                    resource_type_stats[resource_type] = {
                        'total': 0,
                        'ready': 0,
                        'pending': 0,
                        'error': 0,
                        'preparing': 0,
                        'validating': 0
                    }
                
                if isinstance(status_data, dict):
                    status = status_data.get('status')
                else:
                    status = status_data
                
                resource_type_stats[resource_type]['total'] += 1
                
                if status == ReadinessStatus.READY:
                    resource_type_stats[resource_type]['ready'] += 1
                elif status == ReadinessStatus.PENDING:
                    resource_type_stats[resource_type]['pending'] += 1
                elif status == ReadinessStatus.ERROR:
                    resource_type_stats[resource_type]['error'] += 1
                elif status == ReadinessStatus.PREPARING:
                    resource_type_stats[resource_type]['preparing'] += 1
                elif status == ReadinessStatus.VALIDATING:
                    resource_type_stats[resource_type]['validating'] += 1
            
            # Calcular porcentajes por tipo
            for resource_type, stats in resource_type_stats.items():
                if stats['total'] > 0:
                    stats['ready_percentage'] = round((stats['ready'] / stats['total']) * 100, 2)
                    stats['error_percentage'] = round((stats['error'] / stats['total']) * 100, 2)
                else:
                    stats['ready_percentage'] = 0
                    stats['error_percentage'] = 0
            
            return {
                'resource_type_stats': resource_type_stats,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting resource type stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_error_analysis(self) -> Dict[str, Any]:
        """Obtiene análisis de errores para debugging"""
        try:
            all_resources = self.readiness_registry.resource_readiness
            
            error_analysis = {}
            total_errors = 0
            
            for (resource_type, resource_id), status_data in all_resources.items():
                if isinstance(status_data, dict):
                    status = status_data.get('status')
                    errors = status_data.get('errors', [])
                else:
                    status = status_data
                    errors = []
                
                if status == ReadinessStatus.ERROR:
                    total_errors += 1
                    
                    if resource_type not in error_analysis:
                        error_analysis[resource_type] = {
                            'count': 0,
                            'common_errors': {},
                            'resources': []
                        }
                    
                    error_analysis[resource_type]['count'] += 1
                    error_analysis[resource_type]['resources'].append({
                        'resource_id': resource_id,
                        'errors': errors,
                        'timestamp': status_data.get('timestamp', 'N/A') if isinstance(status_data, dict) else 'N/A'
                    })
                    
                    # Contar errores comunes
                    for error in errors:
                        if error not in error_analysis[resource_type]['common_errors']:
                            error_analysis[resource_type]['common_errors'][error] = 0
                        error_analysis[resource_type]['common_errors'][error] += 1
            
            return {
                'total_errors': total_errors,
                'error_analysis': error_analysis,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting error analysis: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas comprehensivas del sistema"""
        try:
            # Obtener todas las métricas en paralelo
            readiness_stats = await self.get_readiness_stats()
            waiting_stats = await self.get_user_waiting_stats()
            resource_type_stats = await self.get_resource_type_stats()
            error_analysis = await self.get_error_analysis()
            
            # Calcular métricas adicionales
            system_health_score = self._calculate_health_score(readiness_stats)
            performance_trend = self._calculate_performance_trend(readiness_stats)
            
            return {
                'system_overview': {
                    'health_score': system_health_score,
                    'performance_trend': performance_trend,
                    'total_resources': readiness_stats.get('total_resources', 0),
                    'readiness_percentage': readiness_stats.get('readiness_percentage', 0)
                },
                'readiness_stats': readiness_stats,
                'waiting_stats': waiting_stats,
                'resource_type_stats': resource_type_stats,
                'error_analysis': error_analysis,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting comprehensive metrics: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _calculate_health_score(self, readiness_stats: Dict[str, Any]) -> int:
        """Calcula un score de salud del sistema (0-100)"""
        try:
            total = readiness_stats.get('total_resources', 0)
            ready = readiness_stats.get('ready_resources', 0)
            errors = readiness_stats.get('error_resources', 0)
            
            if total == 0:
                return 100
            
            # Score basado en recursos listos y penalización por errores
            base_score = (ready / total) * 100
            error_penalty = (errors / total) * 20  # Penalización por errores
            
            health_score = max(0, min(100, base_score - error_penalty))
            return round(health_score)
            
        except Exception:
            return 0
    
    def _calculate_performance_trend(self, readiness_stats: Dict[str, Any]) -> str:
        """Calcula tendencia de performance del sistema"""
        try:
            readiness_percentage = readiness_stats.get('readiness_percentage', 0)
            
            if readiness_percentage >= 90:
                return "excellent"
            elif readiness_percentage >= 75:
                return "good"
            elif readiness_percentage >= 50:
                return "fair"
            elif readiness_percentage >= 25:
                return "poor"
            else:
                return "critical"
                
        except Exception:
            return "unknown"
