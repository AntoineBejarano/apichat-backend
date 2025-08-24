"""
🎯 Resource Priority Service: Priorización inteligente de recursos

Este servicio prioriza recursos por tipo (DB > App > Estrategia) y
optimiza el orden de consulta para maximizar la eficiencia del sistema.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.data.database_service import DatabaseService
from app.services.management.app_service import AppService

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Tipos de recursos disponibles"""
    DATABASE = "database"
    APPLICATION = "application"
    STRATEGY = "strategy"
    INTEGRATION = "integration"
    CACHE = "cache"
    EXTERNAL_API = "external_api"


class PriorityLevel(Enum):
    """Niveles de prioridad para recursos"""
    CRITICAL = "critical"      # Prioridad máxima (DB principal)
    HIGH = "high"              # Alta prioridad (DB secundarias, Apps críticas)
    MEDIUM = "medium"          # Prioridad media (Apps normales, Estrategias)
    LOW = "low"                # Prioridad baja (Integraciones, APIs externas)
    OPTIONAL = "optional"      # Prioridad mínima (Recursos opcionales)


class QueryType(Enum):
    """Tipos de consultas para optimización"""
    DATA_QUERY = "data_query"           # Consultas de datos (prioridad DB)
    OPERATION_QUERY = "operation_query" # Operaciones (prioridad App)
    ANALYSIS_QUERY = "analysis_query"   # Análisis (prioridad Estrategia)
    INTEGRATION_QUERY = "integration_query" # Integraciones (prioridad baja)


class ResourcePriorityService:
    """
    🎯 Servicio de priorización inteligente de recursos
    
    Funcionalidades:
    - Priorización automática por tipo de recurso
    - Optimización de orden de consulta
    - Métricas de priorización
    - Aprendizaje de patrones de uso
    - Balanceo de carga inteligente
    """
    
    def __init__(self, factory):
        """
        Inicializa el servicio de priorización de recursos
        
        Args:
            factory: ServiceFactory para obtener servicios
        """
        self.factory = factory
        self.database_service = None
        self.app_service = None
        self.mode_detection_service = None
        
        # Configuración de prioridades por tipo
        self._setup_priority_config()
        
        # Métricas de uso de recursos
        self.resource_usage_metrics = {}
        self.query_performance_metrics = {}
        
        logger.info("[ResourcePriorityService] 🚀 Inicializado para priorización inteligente de recursos")
    
    def _setup_priority_config(self):
        """Configura las prioridades por tipo de recurso"""
        self.priority_config = {
            ResourceType.DATABASE: {
                "base_priority": PriorityLevel.CRITICAL,
                "weight": 1.0,
                "fallback_timeout": 5000,  # 5 segundos
                "retry_attempts": 3
            },
            ResourceType.APPLICATION: {
                "base_priority": PriorityLevel.HIGH,
                "weight": 0.8,
                "fallback_timeout": 3000,  # 3 segundos
                "retry_attempts": 2
            },
            ResourceType.STRATEGY: {
                "base_priority": PriorityLevel.MEDIUM,
                "weight": 0.6,
                "fallback_timeout": 2000,  # 2 segundos
                "retry_attempts": 1
            },
            ResourceType.INTEGRATION: {
                "base_priority": PriorityLevel.LOW,
                "weight": 0.4,
                "fallback_timeout": 1000,  # 1 segundo
                "retry_attempts": 1
            },
            ResourceType.EXTERNAL_API: {
                "base_priority": PriorityLevel.OPTIONAL,
                "weight": 0.2,
                "fallback_timeout": 500,   # 0.5 segundos
                "retry_attempts": 0
            }
        }
    
    async def _get_services(self):
        """Obtiene servicios necesarios de forma lazy"""
        try:
            if not self.database_service:
                self.database_service = self.factory.get_database_service()
            
            if not self.app_service:
                self.app_service = self.factory.get_app_service()
            
            if not self.mode_detection_service:
                self.mode_detection_service = self.factory.get_mode_detection_service()
                
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo servicios: {e}")
    
    async def prioritize_resources(
        self,
        user_id: UUID,
        query_type: QueryType,
        available_resources: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Prioriza recursos según tipo de consulta y contexto
        
        Args:
            user_id: ID del usuario
            query_type: Tipo de consulta
            available_resources: Lista de recursos disponibles
            context: Contexto adicional
            
        Returns:
            Lista de recursos priorizados
        """
        try:
            await self._get_services()
            
            # Calcular prioridades para cada recurso
            prioritized_resources = []
            
            for resource in available_resources:
                priority_score = await self._calculate_resource_priority(
                    resource, query_type, context, user_id
                )
                
                prioritized_resource = {
                    **resource,
                    "priority_score": priority_score,
                    "priority_level": self._get_priority_level(priority_score),
                    "recommended_order": 0  # Se actualizará después
                }
                
                prioritized_resources.append(prioritized_resource)
            
            # Ordenar por prioridad descendente
            prioritized_resources.sort(key=lambda x: x["priority_score"], reverse=True)
            
            # Asignar orden recomendado
            for i, resource in enumerate(prioritized_resources):
                resource["recommended_order"] = i + 1
            
            # Actualizar métricas
            await self._update_priority_metrics(user_id, query_type, prioritized_resources)
            
            logger.info(
                f"[ResourcePriorityService] 🎯 Recursos priorizados para usuario {user_id}: "
                f"{len(prioritized_resources)} recursos ordenados por prioridad"
            )
            
            return prioritized_resources
            
        except Exception as e:
            logger.error(f"[ResourcePriorityService] ❌ Error priorizando recursos: {e}")
            return available_resources
    
    async def _calculate_resource_priority(
        self,
        resource: Dict[str, Any],
        query_type: QueryType,
        context: Dict[str, Any],
        user_id: UUID
    ) -> float:
        """
        Calcula la prioridad de un recurso específico
        
        Args:
            resource: Recurso a evaluar
            query_type: Tipo de consulta
            query_type: Tipo de consulta
            context: Contexto de la consulta
            user_id: ID del usuario
            
        Returns:
            Score de prioridad (0.0 - 1.0)
        """
        try:
            # Obtener tipo de recurso
            resource_type = self._classify_resource_type(resource)
            
            # Prioridad base según tipo
            base_priority = self._get_base_priority_score(resource_type)
            
            # Ajustes por tipo de consulta
            query_adjustment = self._get_query_type_adjustment(query_type, resource_type)
            
            # Ajustes por contexto
            context_adjustment = await self._get_context_adjustment(resource, context, user_id)
            
            # Ajustes por rendimiento histórico
            performance_adjustment = await self._get_performance_adjustment(resource, user_id)
            
            # Ajustes por disponibilidad
            availability_adjustment = self._get_availability_adjustment(resource)
            
            # Calcular prioridad final
            final_priority = (
                base_priority * 0.4 +
                query_adjustment * 0.2 +
                context_adjustment * 0.2 +
                performance_adjustment * 0.15 +
                availability_adjustment * 0.05
            )
            
            # Normalizar a rango 0.0 - 1.0
            final_priority = max(0.0, min(1.0, final_priority))
            
            return round(final_priority, 3)
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error calculando prioridad: {e}")
            return 0.5
    
    def _classify_resource_type(self, resource: Dict[str, Any]) -> ResourceType:
        """Clasifica el tipo de recurso"""
        try:
            resource_category = resource.get("category", "").lower()
            resource_type = resource.get("type", "").lower()
            
            if "database" in resource_category or "db" in resource_type:
                return ResourceType.DATABASE
            elif "application" in resource_category or "app" in resource_type:
                return ResourceType.APPLICATION
            elif "strategy" in resource_category or "strategy" in resource_type:
                return ResourceType.STRATEGY
            elif "integration" in resource_category or "api" in resource_type:
                return ResourceType.INTEGRATION
            elif "external" in resource_category or "third_party" in resource_type:
                return ResourceType.EXTERNAL_API
            else:
                # Intentar inferir por otros campos
                if resource.get("connection_string") or resource.get("schema"):
                    return ResourceType.DATABASE
                elif resource.get("endpoint") or resource.get("method"):
                    return ResourceType.APPLICATION
                else:
                    return ResourceType.STRATEGY
                    
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error clasificando recurso: {e}")
            return ResourceType.STRATEGY
    
    def _get_base_priority_score(self, resource_type: ResourceType) -> float:
        """Obtiene el score de prioridad base según tipo de recurso"""
        try:
            if resource_type in self.priority_config:
                base_priority = self.priority_config[resource_type]["base_priority"]
                
                priority_scores = {
                    PriorityLevel.CRITICAL: 1.0,
                    PriorityLevel.HIGH: 0.8,
                    PriorityLevel.MEDIUM: 0.6,
                    PriorityLevel.LOW: 0.4,
                    PriorityLevel.OPTIONAL: 0.2
                }
                
                return priority_scores.get(base_priority, 0.5)
            
            return 0.5
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo prioridad base: {e}")
            return 0.5
    
    def _get_query_type_adjustment(self, query_type: QueryType, resource_type: ResourceType) -> float:
        """Obtiene ajuste de prioridad según tipo de consulta"""
        try:
            # Matriz de ajustes: query_type vs resource_type
            adjustment_matrix = {
                QueryType.DATA_QUERY: {
                    ResourceType.DATABASE: 1.0,      # Máxima prioridad
                    ResourceType.APPLICATION: 0.6,   # Prioridad media
                    ResourceType.STRATEGY: 0.3,      # Prioridad baja
                    ResourceType.INTEGRATION: 0.2,   # Prioridad muy baja
                    ResourceType.EXTERNAL_API: 0.1   # Prioridad mínima
                },
                QueryType.OPERATION_QUERY: {
                    ResourceType.DATABASE: 0.7,      # Alta prioridad
                    ResourceType.APPLICATION: 1.0,   # Máxima prioridad
                    ResourceType.STRATEGY: 0.5,      # Prioridad media
                    ResourceType.INTEGRATION: 0.4,   # Prioridad media-baja
                    ResourceType.EXTERNAL_API: 0.2   # Prioridad baja
                },
                QueryType.ANALYSIS_QUERY: {
                    ResourceType.DATABASE: 0.8,      # Alta prioridad
                    ResourceType.APPLICATION: 0.6,   # Prioridad media
                    ResourceType.STRATEGY: 1.0,      # Máxima prioridad
                    ResourceType.INTEGRATION: 0.3,   # Prioridad baja
                    ResourceType.EXTERNAL_API: 0.2   # Prioridad baja
                },
                QueryType.INTEGRATION_QUERY: {
                    ResourceType.DATABASE: 0.3,      # Prioridad baja
                    ResourceType.APPLICATION: 0.5,   # Prioridad media
                    ResourceType.STRATEGY: 0.4,      # Prioridad media-baja
                    ResourceType.INTEGRATION: 1.0,   # Máxima prioridad
                    ResourceType.EXTERNAL_API: 0.8   # Alta prioridad
                }
            }
            
            if query_type in adjustment_matrix and resource_type in adjustment_matrix[query_type]:
                return adjustment_matrix[query_type][resource_type]
            
            return 0.5
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo ajuste de consulta: {e}")
            return 0.5
    
    async def _get_context_adjustment(
        self,
        resource: Dict[str, Any],
        context: Dict[str, Any],
        user_id: UUID
    ) -> float:
        """
        Obtiene ajuste de prioridad basado en contexto
        
        Args:
            resource: Recurso a evaluar
            context: Contexto de la consulta
            user_id: ID del usuario
            
        Returns:
            Ajuste de prioridad (0.0 - 1.0)
        """
        try:
            adjustment = 0.5  # Valor neutral
            
            # Ajuste por recursos específicos solicitados
            requested_resources = context.get("requested_resources", [])
            if resource.get("id") in requested_resources:
                adjustment += 0.3
            
            # Ajuste por modo activo
            active_mode = context.get("active_mode", "auto")
            if active_mode == "explorer" and resource.get("type") == "database":
                adjustment += 0.2
            elif active_mode == "guided" and resource.get("type") == "application":
                adjustment += 0.2
            
            # Ajuste por historial de uso del usuario
            user_preference = await self._get_user_resource_preference(user_id, resource)
            adjustment += user_preference * 0.2
            
            # Ajuste por complejidad de la consulta
            query_complexity = context.get("query_complexity", 5)
            if query_complexity > 7 and resource.get("type") == "database":
                adjustment += 0.1
            elif query_complexity < 3 and resource.get("type") == "application":
                adjustment += 0.1
            
            return max(0.0, min(1.0, adjustment))
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo ajuste de contexto: {e}")
            return 0.5
    
    async def _get_user_resource_preference(self, user_id: UUID, resource: Dict[str, Any]) -> float:
        """Obtiene preferencia del usuario por un tipo de recurso"""
        try:
            # Aquí se implementaría lógica para obtener preferencias del usuario
            # Por ahora retornamos un valor neutral
            return 0.0
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo preferencia de usuario: {e}")
            return 0.0
    
    async def _get_performance_adjustment(self, resource: Dict[str, Any], user_id: UUID) -> float:
        """Obtiene ajuste de prioridad basado en rendimiento histórico"""
        try:
            # Obtener métricas de rendimiento del recurso
            resource_id = resource.get("id")
            if not resource_id:
                return 0.5
            
            # Obtener métricas del usuario
            user_metrics = self.resource_usage_metrics.get(str(user_id), {})
            resource_metrics = user_metrics.get(str(resource_id), {})
            
            if not resource_metrics:
                return 0.5
            
            # Calcular ajuste basado en rendimiento
            avg_response_time = resource_metrics.get("avg_response_time", 1000)
            success_rate = resource_metrics.get("success_rate", 0.9)
            last_used = resource_metrics.get("last_used", 0)
            
            # Ajuste por tiempo de respuesta (menor = mejor)
            response_adjustment = max(0.0, 1.0 - (avg_response_time / 5000))
            
            # Ajuste por tasa de éxito
            success_adjustment = success_rate
            
            # Ajuste por uso reciente (más reciente = mejor)
            time_since_last = (datetime.utcnow() - datetime.fromtimestamp(last_used)).total_seconds() if last_used > 0 else 0
            recency_adjustment = max(0.0, 1.0 - (time_since_last / 3600))  # 1 hora
            
            # Calcular ajuste final
            final_adjustment = (
                response_adjustment * 0.4 +
                success_adjustment * 0.4 +
                recency_adjustment * 0.2
            )
            
            return round(final_adjustment, 3)
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo ajuste de rendimiento: {e}")
            return 0.5
    
    def _get_availability_adjustment(self, resource: Dict[str, Any]) -> float:
        """Obtiene ajuste de prioridad basado en disponibilidad"""
        try:
            # Verificar estado del recurso
            status = resource.get("status", "unknown")
            health_score = resource.get("health_score", 1.0)
            
            # Ajuste por estado
            status_adjustments = {
                "active": 1.0,
                "available": 0.9,
                "healthy": 0.8,
                "warning": 0.6,
                "error": 0.3,
                "offline": 0.1,
                "unknown": 0.5
            }
            
            status_adjustment = status_adjustments.get(status, 0.5)
            
            # Ajuste por salud del recurso
            health_adjustment = health_score
            
            # Calcular ajuste final
            final_adjustment = (status_adjustment + health_adjustment) / 2
            
            return round(final_adjustment, 3)
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo ajuste de disponibilidad: {e}")
            return 0.5
    
    def _get_priority_level(self, priority_score: float) -> str:
        """Convierte score de prioridad a nivel de prioridad"""
        try:
            if priority_score >= 0.8:
                return PriorityLevel.CRITICAL.value
            elif priority_score >= 0.6:
                return PriorityLevel.HIGH.value
            elif priority_score >= 0.4:
                return PriorityLevel.MEDIUM.value
            elif priority_score >= 0.2:
                return PriorityLevel.LOW.value
            else:
                return PriorityLevel.OPTIONAL.value
                
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo nivel de prioridad: {e}")
            return PriorityLevel.MEDIUM.value
    
    async def _update_priority_metrics(
        self,
        user_id: UUID,
        query_type: QueryType,
        prioritized_resources: List[Dict[str, Any]]
    ):
        """Actualiza métricas de priorización"""
        try:
            user_id_str = str(user_id)
            
            if user_id_str not in self.resource_usage_metrics:
                self.resource_usage_metrics[user_id_str] = {}
            
            # Actualizar métricas por recurso
            for resource in prioritized_resources:
                resource_id = str(resource.get("id"))
                
                if resource_id not in self.resource_usage_metrics[user_id_str]:
                    self.resource_usage_metrics[user_id_str][resource_id] = {
                        "usage_count": 0,
                        "avg_response_time": 0,
                        "success_rate": 1.0,
                        "last_used": 0,
                        "priority_history": []
                    }
                
                # Actualizar métricas
                metrics = self.resource_usage_metrics[user_id_str][resource_id]
                metrics["usage_count"] += 1
                metrics["last_used"] = datetime.utcnow().timestamp()
                metrics["priority_history"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "priority_score": resource.get("priority_score", 0),
                    "priority_level": resource.get("priority_level", "medium"),
                    "query_type": query_type.value
                })
                
                # Mantener solo los últimos 100 registros
                if len(metrics["priority_history"]) > 100:
                    metrics["priority_history"] = metrics["priority_history"][-100:]
            
            # Actualizar métricas de consulta
            if user_id_str not in self.query_performance_metrics:
                self.query_performance_metrics[user_id_str] = {}
            
            query_type_str = query_type.value
            if query_type_str not in self.query_performance_metrics[user_id_str]:
                self.query_performance_metrics[user_id_str][query_type_str] = {
                    "total_queries": 0,
                    "avg_priority_score": 0,
                    "resource_distribution": {}
                }
            
            # Actualizar métricas de consulta
            query_metrics = self.query_performance_metrics[user_id_str][query_type_str]
            query_metrics["total_queries"] += 1
            
            # Calcular prioridad promedio
            total_priority = sum(r.get("priority_score", 0) for r in prioritized_resources)
            avg_priority = total_priority / len(prioritized_resources) if prioritized_resources else 0
            query_metrics["avg_priority_score"] = (
                (query_metrics["avg_priority_score"] * (query_metrics["total_queries"] - 1) + avg_priority) /
                query_metrics["total_queries"]
            )
            
            # Actualizar distribución de recursos
            for resource in prioritized_resources:
                resource_type = resource.get("type", "unknown")
                if resource_type not in query_metrics["resource_distribution"]:
                    query_metrics["resource_distribution"][resource_type] = 0
                query_metrics["resource_distribution"][resource_type] += 1
                
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error actualizando métricas: {e}")
    
    async def get_priority_analytics(
        self,
        user_id: UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Obtiene análisis de priorización para un usuario
        
        Args:
            user_id: ID del usuario
            days: Días hacia atrás para el análisis
            
        Returns:
            Análisis de priorización
        """
        try:
            user_id_str = str(user_id)
            
            if user_id_str not in self.resource_usage_metrics:
                return {
                    "user_id": str(user_id),
                    "message": "No hay datos de priorización disponibles"
                }
            
            # Obtener métricas del usuario
            user_metrics = self.resource_usage_metrics[user_id_str]
            
            # Calcular estadísticas generales
            total_resources = len(user_metrics)
            total_usage = sum(metrics["usage_count"] for metrics in user_metrics.values())
            
            # Análisis por tipo de recurso
            resource_type_analysis = {}
            for resource_id, metrics in user_metrics.items():
                # Aquí se implementaría lógica para obtener tipo de recurso
                # Por ahora usamos un placeholder
                resource_type = "unknown"
                
                if resource_type not in resource_type_analysis:
                    resource_type_analysis[resource_type] = {
                        "count": 0,
                        "total_usage": 0,
                        "avg_priority": 0
                    }
                
                resource_type_analysis[resource_type]["count"] += 1
                resource_type_analysis[resource_type]["total_usage"] += metrics["usage_count"]
                
                # Calcular prioridad promedio
                if metrics["priority_history"]:
                    avg_priority = sum(h["priority_score"] for h in metrics["priority_history"]) / len(metrics["priority_history"])
                    resource_type_analysis[resource_type]["avg_priority"] = round(avg_priority, 3)
            
            # Análisis de tendencias de prioridad
            priority_trends = {}
            for resource_id, metrics in user_metrics.items():
                if metrics["priority_history"]:
                    # Agrupar por día
                    daily_priorities = {}
                    for history in metrics["priority_history"]:
                        date = history["timestamp"][:10]  # YYYY-MM-DD
                        if date not in daily_priorities:
                            daily_priorities[date] = []
                        daily_priorities[date].append(history["priority_score"])
                    
                    # Calcular promedio diario
                    for date, priorities in daily_priorities.items():
                        if date not in priority_trends:
                            priority_trends[date] = []
                        priority_trends[date].extend(priorities)
            
            # Calcular tendencia general
            overall_trend = 0
            if priority_trends:
                all_priorities = []
                for priorities in priority_trends.values():
                    all_priorities.extend(priorities)
                if all_priorities:
                    overall_trend = sum(all_priorities) / len(all_priorities)
            
            return {
                "user_id": str(user_id),
                "analysis_period_days": days,
                "summary": {
                    "total_resources": total_resources,
                    "total_usage": total_usage,
                    "overall_avg_priority": round(overall_trend, 3)
                },
                "resource_type_analysis": resource_type_analysis,
                "priority_trends": {
                    "daily_averages": {
                        date: round(sum(priorities) / len(priorities), 3)
                        for date, priorities in priority_trends.items()
                    },
                    "overall_trend": round(overall_trend, 3)
                }
            }
            
        except Exception as e:
            logger.error(f"[ResourcePriorityService] ❌ Error obteniendo análisis: {e}")
            return {"error": str(e)}
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtiene información del servicio"""
        return {
            "service_name": "ResourcePriorityService",
            "description": "Servicio de priorización inteligente de recursos",
            "features": [
                "Priorización automática por tipo de recurso",
                "Optimización de orden de consulta",
                "Métricas de priorización",
                "Aprendizaje de patrones de uso",
                "Balanceo de carga inteligente"
            ],
            "supported_resource_types": [rt.value for rt in ResourceType],
            "supported_priority_levels": [pl.value for pl in PriorityLevel],
            "supported_query_types": [qt.value for qt in QueryType],
            "priority_config": {
                rt.value: {
                    "base_priority": config["base_priority"].value,
                    "weight": config["weight"]
                }
                for rt, config in self.priority_config.items()
            },
            "status": "active"
        }
