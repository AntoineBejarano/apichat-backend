"""
🎯 Resource Priority Service: Priorización automática de recursos y resolución de conflictos

Sistema que prioriza automáticamente recursos (DB > App > Estrategia) y resuelve conflictos
entre múltiples recursos solicitados por el usuario.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from uuid import UUID
import time

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Tipos de recursos disponibles"""
    DATABASE = "database"
    APP = "app"
    STRATEGY = "strategy"
    UNKNOWN = "unknown"


class PriorityLevel(Enum):
    """Niveles de prioridad para recursos"""
    CRITICAL = 1      # DB crítica (usuarios, auth, etc.)
    HIGH = 2          # DB principal
    MEDIUM = 3        # Apps importantes
    LOW = 4           # Apps secundarias
    MINIMAL = 5       # Estrategias


class ConflictResolution(Enum):
    """Tipos de resolución de conflictos"""
    AUTO_PRIORITY = "auto_priority"      # Priorización automática
    USER_CONFIRMATION = "user_confirmation"  # Confirmación del usuario
    SEQUENTIAL = "sequential"            # Ejecución secuencial
    PARALLEL = "parallel"                # Ejecución paralela


class ResourcePriorityService:
    """
    🎯 Servicio de priorización automática de recursos
    
    Funcionalidades:
    - Priorización automática: DB > App > Estrategia
    - Resolución de conflictos entre recursos
    - Confirmación automática cuando hay ambigüedad
    - Sugerencias inteligentes para el usuario
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Cache de prioridades de recursos
        self._resource_priorities = {}
        self._conflict_resolutions = {}
        
        # Configuración de prioridades por tipo
        self._type_priorities = {
            ResourceType.DATABASE: PriorityLevel.HIGH,
            ResourceType.APP: PriorityLevel.MEDIUM,
            ResourceType.STRATEGY: PriorityLevel.MINIMAL
        }
        
        # Recursos críticos que siempre tienen prioridad máxima
        self._critical_resources = {
            "users", "auth", "authentication", "user_management",
            "sessions", "permissions", "roles", "security"
        }
        
        logger.info(f"[ResourcePriorityService] 🚀 Inicializado para usuario {self.user_id}")
    
    async def prioritize_resources(
        self, 
        requested_resources: List[Dict[str, Any]],
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🎯 Prioriza recursos automáticamente y resuelve conflictos
        
        Args:
            requested_resources: Lista de recursos solicitados
            query_context: Contexto de la consulta del usuario
            
        Returns:
            Recursos priorizados y plan de ejecución
        """
        try:
            start_time = time.time()
            logger.info(f"[ResourcePriorityService] 🎯 Priorizando {len(requested_resources)} recursos")
            
            # 1. Analizar y clasificar recursos
            classified_resources = await self._classify_resources(requested_resources)
            
            # 2. Calcular prioridades individuales
            prioritized_resources = await self._calculate_priorities(classified_resources, query_context)
            
            # 3. Detectar y resolver conflictos
            conflict_resolution = await self._resolve_conflicts(prioritized_resources, query_context)
            
            # 4. Generar plan de ejecución
            execution_plan = await self._generate_execution_plan(
                prioritized_resources, 
                conflict_resolution, 
                query_context
            )
            
            execution_time = time.time() - start_time
            
            result = {
                "success": True,
                "prioritized_resources": prioritized_resources,
                "conflict_resolution": conflict_resolution,
                "execution_plan": execution_plan,
                "metadata": {
                    "total_resources": len(requested_resources),
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "conflicts_resolved": len(conflict_resolution.get("resolved_conflicts", [])),
                    "user_confirmation_required": conflict_resolution.get("requires_confirmation", False)
                }
            }
            
            logger.info(f"[ResourcePriorityService] ✅ Priorización completada en {execution_time:.3f}s")
            return result
            
        except Exception as e:
            logger.exception(f"[ResourcePriorityService] ❌ Error en priorización: {e}")
            return self._build_error_result(
                error=f"Error en priorización: {str(e)}",
                requested_resources=requested_resources
            )
    
    async def _classify_resources(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clasifica recursos por tipo y extrae información relevante"""
        classified = []
        
        for resource in resources:
            try:
                resource_type = await self._detect_resource_type(resource)
                priority_level = self._type_priorities.get(resource_type, PriorityLevel.MINIMAL)
                
                classified_resource = {
                    "original": resource,
                    "type": resource_type,
                    "priority_level": priority_level,
                    "name": resource.get("name", "unknown"),
                    "id": resource.get("id"),
                    "description": resource.get("description", ""),
                    "is_critical": self._is_critical_resource(resource.get("name", "")),
                    "metadata": resource.get("metadata", {})
                }
                
                classified.append(classified_resource)
                
            except Exception as e:
                logger.warning(f"[ResourcePriorityService] ⚠️ Error clasificando recurso: {e}")
                # Agregar como desconocido
                classified.append({
                    "original": resource,
                    "type": ResourceType.UNKNOWN,
                    "priority_level": PriorityLevel.MINIMAL,
                    "name": resource.get("name", "unknown"),
                    "id": resource.get("id"),
                    "description": resource.get("description", ""),
                    "is_critical": False,
                    "metadata": resource.get("metadata", {})
                })
        
        return classified
    
    async def _detect_resource_type(self, resource: Dict[str, Any]) -> ResourceType:
        """Detecta el tipo de recurso basado en su estructura"""
        try:
            # Detectar por campos específicos
            if "connection_string" in resource or "database_type" in resource:
                return ResourceType.DATABASE
            elif "api_endpoint" in resource or "app_type" in resource:
                return ResourceType.APP
            elif "strategy_type" in resource or "execution_plan" in resource:
                return ResourceType.STRATEGY
            
            # Detectar por nombre
            name = resource.get("name", "").lower()
            if any(db_keyword in name for db_keyword in ["db", "database", "table", "schema"]):
                return ResourceType.DATABASE
            elif any(app_keyword in name for app_keyword in ["app", "api", "service", "integration"]):
                return ResourceType.APP
            elif any(strategy_keyword in name for strategy_keyword in ["strategy", "plan", "workflow"]):
                return ResourceType.STRATEGY
            
            # Detectar por descripción
            description = resource.get("description", "").lower()
            if any(db_keyword in description for db_keyword in ["database", "table", "schema", "query"]):
                return ResourceType.DATABASE
            elif any(app_keyword in description for app_keyword in ["application", "api", "service"]):
                return ResourceType.APP
            elif any(strategy_keyword in description for strategy_keyword in ["strategy", "plan", "workflow"]):
                return ResourceType.STRATEGY
            
            return ResourceType.UNKNOWN
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error detectando tipo: {e}")
            return ResourceType.UNKNOWN
    
    def _is_critical_resource(self, resource_name: str) -> bool:
        """Determina si un recurso es crítico"""
        if not resource_name:
            return False
        
        name_lower = resource_name.lower()
        return any(critical in name_lower for critical in self._critical_resources)
    
    async def _calculate_priorities(
        self, 
        classified_resources: List[Dict[str, Any]], 
        query_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Calcula prioridades individuales para cada recurso"""
        prioritized = []
        
        for resource in classified_resources:
            try:
                # Prioridad base por tipo
                base_priority = resource["priority_level"].value
                
                # Bonus por recurso crítico
                critical_bonus = 2 if resource["is_critical"] else 0
                
                # Bonus por contexto de consulta
                context_bonus = await self._calculate_context_bonus(resource, query_context)
                
                # Prioridad final (menor número = mayor prioridad)
                final_priority = max(1, base_priority - critical_bonus - context_bonus)
                
                prioritized_resource = {
                    **resource,
                    "base_priority": base_priority,
                    "critical_bonus": critical_bonus,
                    "context_bonus": context_bonus,
                    "final_priority": final_priority
                }
                
                prioritized.append(prioritized_resource)
                
            except Exception as e:
                logger.warning(f"[ResourcePriorityService] ⚠️ Error calculando prioridad: {e}")
                prioritized.append(resource)
        
        # Ordenar por prioridad final (ascendente)
        prioritized.sort(key=lambda x: x.get("final_priority", 999))
        
        return prioritized
    
    async def _calculate_context_bonus(self, resource: Dict[str, Any], query_context: Dict[str, Any]) -> int:
        """Calcula bonus de prioridad basado en el contexto de la consulta"""
        try:
            bonus = 0
            query_text = query_context.get("query", "").lower()
            resource_name = resource.get("name", "").lower()
            
            # Bonus si el recurso está mencionado explícitamente en la consulta
            if resource_name in query_text:
                bonus += 1
            
            # Bonus por tipo de consulta
            query_type = query_context.get("query_type", "")
            if query_type == "data_analysis" and resource["type"] == ResourceType.DATABASE:
                bonus += 1
            elif query_type == "integration" and resource["type"] == ResourceType.APP:
                bonus += 1
            elif query_type == "execution" and resource["type"] == ResourceType.STRATEGY:
                bonus += 1
            
            # Bonus por recursos recientemente utilizados
            recent_usage = query_context.get("recent_resources", [])
            if resource.get("id") in recent_usage:
                bonus += 1
            
            return min(bonus, 2)  # Máximo 2 de bonus
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error calculando bonus de contexto: {e}")
            return 0
    
    async def _resolve_conflicts(
        self, 
        prioritized_resources: List[Dict[str, Any]], 
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resuelve conflictos entre recursos priorizados"""
        try:
            conflicts = []
            resolved_conflicts = []
            requires_confirmation = False
            
            # Detectar conflictos por tipo de recurso
            resource_types = [r["type"] for r in prioritized_resources]
            type_conflicts = self._detect_type_conflicts(resource_types)
            
            if type_conflicts:
                conflicts.extend(type_conflicts)
            
            # Detectar conflictos por prioridad similar
            priority_conflicts = self._detect_priority_conflicts(prioritized_resources)
            if priority_conflicts:
                conflicts.extend(priority_conflicts)
            
            # Resolver conflictos automáticamente cuando sea posible
            for conflict in conflicts:
                resolution = await self._resolve_single_conflict(conflict, prioritized_resources, query_context)
                resolved_conflicts.append(resolution)
                
                if resolution["resolution_type"] == ConflictResolution.USER_CONFIRMATION:
                    requires_confirmation = True
            
            return {
                "conflicts_detected": conflicts,
                "resolved_conflicts": resolved_conflicts,
                "requires_confirmation": requires_confirmation,
                "resolution_strategy": "auto_priority_with_confirmation" if requires_confirmation else "auto_priority"
            }
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error resolviendo conflictos: {e}")
            return {
                "conflicts_detected": [],
                "resolved_conflicts": [],
                "requires_confirmation": False,
                "resolution_strategy": "error_fallback"
            }
    
    def _detect_type_conflicts(self, resource_types: List[ResourceType]) -> List[Dict[str, Any]]:
        """Detecta conflictos entre diferentes tipos de recursos"""
        conflicts = []
        
        # Conflicto: Múltiples bases de datos
        db_count = resource_types.count(ResourceType.DATABASE)
        if db_count > 1:
            conflicts.append({
                "type": "multiple_databases",
                "severity": "medium",
                "description": f"Se detectaron {db_count} bases de datos",
                "suggestion": "Considerar ejecución secuencial o priorizar por importancia"
            })
        
        # Conflicto: Múltiples apps
        app_count = resource_types.count(ResourceType.APP)
        if app_count > 2:
            conflicts.append({
                "type": "multiple_apps",
                "severity": "low",
                "description": f"Se detectaron {app_count} aplicaciones",
                "suggestion": "Agrupar por funcionalidad relacionada"
            })
        
        return conflicts
    
    def _detect_priority_conflicts(self, prioritized_resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detecta conflictos por prioridades similares"""
        conflicts = []
        
        if len(prioritized_resources) < 2:
            return conflicts
        
        # Detectar recursos con prioridad muy similar
        for i in range(len(prioritized_resources) - 1):
            current = prioritized_resources[i]
            next_resource = prioritized_resources[i + 1]
            
            priority_diff = abs(current["final_priority"] - next_resource["final_priority"])
            
            if priority_diff <= 1:  # Prioridades muy similares
                conflicts.append({
                    "type": "similar_priority",
                    "severity": "low",
                    "description": f"Recursos '{current['name']}' y '{next_resource['name']}' tienen prioridad similar",
                    "suggestion": "Confirmar orden de ejecución con el usuario",
                    "resources": [current["name"], next_resource["name"]]
                })
        
        return conflicts
    
    async def _resolve_single_conflict(
        self, 
        conflict: Dict[str, Any], 
        prioritized_resources: List[Dict[str, Any]], 
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resuelve un conflicto individual"""
        try:
            conflict_type = conflict["type"]
            
            if conflict_type == "multiple_databases":
                # Priorizar por criticidad y orden alfabético
                db_resources = [r for r in prioritized_resources if r["type"] == ResourceType.DATABASE]
                db_resources.sort(key=lambda x: (x["is_critical"], x["name"]))
                
                return {
                    "conflict": conflict,
                    "resolution_type": ConflictResolution.AUTO_PRIORITY,
                    "resolution": "Priorización automática por criticidad",
                    "new_order": [r["name"] for r in db_resources],
                    "requires_confirmation": False
                }
            
            elif conflict_type == "similar_priority":
                # Requerir confirmación del usuario
                return {
                    "conflict": conflict,
                    "resolution_type": ConflictResolution.USER_CONFIRMATION,
                    "resolution": "Confirmación requerida del usuario",
                    "suggestion": f"¿En qué orden prefieres ejecutar: {', '.join(conflict['resources'])}?",
                    "requires_confirmation": True
                }
            
            else:
                # Resolución por defecto
                return {
                    "conflict": conflict,
                    "resolution_type": ConflictResolution.AUTO_PRIORITY,
                    "resolution": "Resolución automática por prioridad",
                    "requires_confirmation": False
                }
                
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error resolviendo conflicto: {e}")
            return {
                "conflict": conflict,
                "resolution_type": ConflictResolution.AUTO_PRIORITY,
                "resolution": "Resolución automática por error",
                "requires_confirmation": False
            }
    
    async def _generate_execution_plan(
        self, 
        prioritized_resources: List[Dict[str, Any]], 
        conflict_resolution: Dict[str, Any], 
        query_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera plan de ejecución basado en recursos priorizados"""
        try:
            execution_plan = {
                "phases": [],
                "estimated_duration": "unknown",
                "parallel_execution": False,
                "fallback_strategy": "sequential"
            }
            
            # Fase 1: Recursos críticos (si los hay)
            critical_resources = [r for r in prioritized_resources if r["is_critical"]]
            if critical_resources:
                execution_plan["phases"].append({
                    "phase": 1,
                    "name": "Recursos Críticos",
                    "resources": [r["name"] for r in critical_resources],
                    "execution_type": "sequential",
                    "priority": "critical"
                })
            
            # Fase 2: Bases de datos
            db_resources = [r for r in prioritized_resources if r["type"] == ResourceType.DATABASE and not r["is_critical"]]
            if db_resources:
                execution_plan["phases"].append({
                    "phase": len(execution_plan["phases"]) + 1,
                    "name": "Bases de Datos",
                    "resources": [r["name"] for r in db_resources],
                    "execution_type": "sequential",
                    "priority": "high"
                })
            
            # Fase 3: Aplicaciones
            app_resources = [r for r in prioritized_resources if r["type"] == ResourceType.APP]
            if app_resources:
                execution_plan["phases"].append({
                    "phase": len(execution_plan["phases"]) + 1,
                    "name": "Aplicaciones",
                    "resources": [r["name"] for r in app_resources],
                    "execution_type": "parallel" if len(app_resources) > 1 else "sequential",
                    "priority": "medium"
                })
            
            # Fase 4: Estrategias
            strategy_resources = [r for r in prioritized_resources if r["type"] == ResourceType.STRATEGY]
            if strategy_resources:
                execution_plan["phases"].append({
                    "phase": len(execution_plan["phases"]) + 1,
                    "name": "Estrategias",
                    "resources": [r["name"] for r in strategy_resources],
                    "execution_type": "sequential",
                    "priority": "low"
                })
            
            # Calcular duración estimada
            total_phases = len(execution_plan["phases"])
            if total_phases > 0:
                execution_plan["estimated_duration"] = f"{total_phases * 2-3} minutos"
            
            # Determinar si se puede ejecutar en paralelo
            execution_plan["parallel_execution"] = any(
                phase["execution_type"] == "parallel" for phase in execution_plan["phases"]
            )
            
            return execution_plan
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error generando plan: {e}")
            return {
                "phases": [],
                "estimated_duration": "unknown",
                "parallel_execution": False,
                "fallback_strategy": "sequential",
                "error": str(e)
            }
    
    async def get_priority_suggestions(self, query: str) -> List[str]:
        """Obtiene sugerencias de priorización para una consulta"""
        try:
            suggestions = []
            
            # Sugerencias basadas en palabras clave
            query_lower = query.lower()
            
            if any(word in query_lower for word in ["database", "db", "table", "query"]):
                suggestions.append("💾 Priorizar bases de datos para consultas de datos")
            
            if any(word in query_lower for word in ["app", "api", "integration"]):
                suggestions.append("🔗 Priorizar aplicaciones para integraciones")
            
            if any(word in query_lower for word in ["strategy", "plan", "workflow"]):
                suggestions.append("📋 Priorizar estrategias para ejecución de planes")
            
            if any(word in query_lower for word in ["analyze", "analyze", "report"]):
                suggestions.append("📊 Considerar ejecución secuencial para análisis complejos")
            
            if any(word in query_lower for word in ["fast", "quick", "urgent"]):
                suggestions.append("⚡ Priorizar recursos críticos para respuestas rápidas")
            
            return suggestions[:3]  # Máximo 3 sugerencias
            
        except Exception as e:
            logger.warning(f"[ResourcePriorityService] ⚠️ Error obteniendo sugerencias: {e}")
            return ["💡 Usar modo automático para priorización inteligente"]
    
    async def clear_cache(self):
        """Limpia el cache de prioridades"""
        self._resource_priorities.clear()
        self._conflict_resolutions.clear()
        logger.info("[ResourcePriorityService] 🧹 Cache limpiado")
    
    def _build_error_result(self, error: str, requested_resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construye resultado de error"""
        return {
            "success": False,
            "error": error,
            "requested_resources": requested_resources,
            "fallback_message": "I'm not sure how to prioritize these resources. Would you like me to show your resources or start with a plan?",
            "requires_user_guidance": True
        }


# Función helper para dependency injection
def get_resource_priority_service(factory) -> ResourcePriorityService:
    """Obtiene una instancia del Resource Priority Service"""
    return ResourcePriorityService(factory)
