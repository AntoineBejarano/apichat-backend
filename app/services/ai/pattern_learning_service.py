"""
PatternLearningService - Aprendizaje automático de patrones de uso
"""

import json
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from app.core.service_factory import ServiceFactory


class PatternType(Enum):
    """Tipos de patrones que se pueden aprender"""
    MODE_SELECTION = "mode_selection"
    QUERY_PATTERNS = "query_patterns"
    RESOURCE_USAGE = "resource_usage"
    RESPONSE_PREFERENCES = "response_preferences"
    TIME_PATTERNS = "time_patterns"
    ERROR_PATTERNS = "error_patterns"


class LearningStatus(Enum):
    """Estado del aprendizaje de patrones"""
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    OPTIMIZING = "optimizing"
    APPLYING = "applying"
    STABLE = "stable"


@dataclass
class UserPattern:
    """Patrón aprendido del usuario"""
    id: str
    user_id: str
    pattern_type: PatternType
    pattern_data: Dict[str, Any]
    confidence: float
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    is_active: bool = True


@dataclass
class PatternInsight:
    """Insight derivado de patrones"""
    id: str
    user_id: str
    insight_type: str
    description: str
    confidence: float
    recommendations: List[str]
    created_at: datetime


class PatternLearningService:
    """
    Servicio para aprendizaje automático de patrones de uso del usuario
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        self.cache_ttl = 900  # 15 minutos
        
        # Configuración de aprendizaje
        self.min_data_points = 10
        self.confidence_threshold = 0.7
        self.learning_cooldown = 3600  # 1 hora
        
        # Patrones base conocidos
        self.base_patterns = {
            PatternType.MODE_SELECTION: {
                "explorer": {"keywords": ["mostrar", "ver", "explorar", "listar"], "confidence": 0.8},
                "guided": {"keywords": ["ejecutar", "crear", "analizar", "planificar"], "confidence": 0.8},
                "auto": {"keywords": ["ayuda", "sugerir", "recomendar"], "confidence": 0.6}
            },
            PatternType.QUERY_PATTERNS: {
                "simple": {"complexity": 1, "confidence": 0.7},
                "moderate": {"complexity": 2, "confidence": 0.7},
                "complex": {"complexity": 3, "confidence": 0.7}
            }
        }
    
    async def initialize(self, user_id: str):
        """Inicializar el servicio para un usuario específico"""
        try:
            self.user_id = user_id
            self.user_patterns = await self._load_user_patterns()
            self.learning_status = await self._get_learning_status()
            self.last_learning_update = await self._get_last_learning_update()
            self.logger.info(f"PatternLearningService inicializado para usuario {user_id}")
        except Exception as e:
            self.logger.error(f"Error inicializando PatternLearningService: {e}")
            raise
    
    async def record_interaction(
        self,
        interaction_type: str,
        interaction_data: Dict[str, Any],
        context: Optional[Dict] = None
    ):
        """
        Registrar una nueva interacción para aprendizaje
        """
        try:
            # Crear entrada de interacción
            interaction_entry = {
                "id": f"interaction_{datetime.now().timestamp()}",
                "user_id": self.user_id,
                "type": interaction_type,
                "data": interaction_data,
                "context": context or {},
                "timestamp": datetime.now()
            }
            
            # Guardar interacción
            await self._save_interaction(interaction_entry)
            
            # Verificar si es momento de aprender
            if await self._should_learn():
                await self._trigger_learning()
            
            self.logger.debug(f"Interacción registrada: {interaction_type}")
            
        except Exception as e:
            self.logger.error(f"Error registrando interacción: {e}")
    
    async def get_user_patterns(self, pattern_type: Optional[PatternType] = None) -> List[UserPattern]:
        """Obtener patrones aprendidos del usuario"""
        try:
            if pattern_type:
                return [p for p in self.user_patterns if p.pattern_type == pattern_type and p.is_active]
            else:
                return [p for p in self.user_patterns if p.is_active]
        except Exception as e:
            self.logger.error(f"Error obteniendo patrones: {e}")
            return []
    
    async def get_pattern_insights(self) -> List[PatternInsight]:
        """Obtener insights derivados de patrones"""
        try:
            insights = []
            
            # Generar insights basados en patrones activos
            for pattern in self.user_patterns:
                if pattern.is_active and pattern.confidence >= self.confidence_threshold:
                    insight = await self._generate_insight_from_pattern(pattern)
                    if insight:
                        insights.append(insight)
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error generando insights: {e}")
            return []
    
    async def get_optimization_recommendations(self) -> List[str]:
        """Obtener recomendaciones de optimización basadas en patrones"""
        try:
            recommendations = []
            
            # Analizar patrones para recomendaciones
            mode_patterns = await self.get_user_patterns(PatternType.MODE_SELECTION)
            query_patterns = await self.get_user_patterns(PatternType.QUERY_PATTERNS)
            
            # Recomendaciones de modo
            if mode_patterns:
                preferred_mode = max(mode_patterns, key=lambda x: x.usage_count)
                if preferred_mode.pattern_data.get("mode") == "auto":
                    recommendations.append("Considera usar modos específicos (Explorer/Guided) para mejor control")
                elif preferred_mode.pattern_data.get("mode") in ["explorer", "guided"]:
                    recommendations.append("El modo Auto podría ser útil para consultas ambiguas")
            
            # Recomendaciones de queries
            if query_patterns:
                avg_complexity = sum(p.pattern_data.get("complexity", 1) for p in query_patterns) / len(query_patterns)
                if avg_complexity > 2:
                    recommendations.append("Tus consultas son complejas. Considera usar el modo Guided para mejor planificación")
                elif avg_complexity < 1.5:
                    recommendations.append("Tus consultas son simples. El modo Explorer podría ser más eficiente")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Error generando recomendaciones: {e}")
            return []
    
    async def force_pattern_learning(self):
        """Forzar el aprendizaje de patrones"""
        try:
            self.logger.info(f"Forzando aprendizaje de patrones para usuario {self.user_id}")
            await self._trigger_learning()
        except Exception as e:
            self.logger.error(f"Error forzando aprendizaje: {e}")
    
    async def _trigger_learning(self):
        """Disparar el proceso de aprendizaje"""
        try:
            # Cambiar estado a analizando
            self.learning_status = LearningStatus.ANALYZING
            await self._update_learning_status(self.learning_status)
            
            # 1. Recolectar datos de interacciones
            interactions = await self._collect_recent_interactions()
            
            if len(interactions) < self.min_data_points:
                self.logger.info(f"Datos insuficientes para aprendizaje: {len(interactions)}/{self.min_data_points}")
                self.learning_status = LearningStatus.COLLECTING
                await self._update_learning_status(self.learning_status)
                return
            
            # 2. Analizar patrones
            new_patterns = await self._analyze_patterns(interactions)
            
            # 3. Optimizar patrones existentes
            updated_patterns = await self._optimize_existing_patterns(new_patterns)
            
            # 4. Aplicar nuevos patrones
            await self._apply_new_patterns(updated_patterns)
            
            # 5. Actualizar estado
            self.learning_status = LearningStatus.STABLE
            await self._update_learning_status(self.learning_status)
            self.last_learning_update = datetime.now()
            await self._update_last_learning_update(self.last_learning_update)
            
            self.logger.info(f"Aprendizaje completado - {len(updated_patterns)} patrones actualizados")
            
        except Exception as e:
            self.logger.error(f"Error en proceso de aprendizaje: {e}")
            self.learning_status = LearningStatus.COLLECTING
            await self._update_learning_status(self.learning_status)
    
    async def _analyze_patterns(self, interactions: List[Dict]) -> List[UserPattern]:
        """Analizar interacciones para extraer patrones"""
        try:
            patterns = []
            
            # Agrupar interacciones por tipo
            interaction_groups = {}
            for interaction in interactions:
                interaction_type = interaction["type"]
                if interaction_type not in interaction_groups:
                    interaction_groups[interaction_type] = []
                interaction_groups[interaction_type].append(interaction)
            
            # Analizar patrones de selección de modo
            if "mode_selection" in interaction_groups:
                mode_patterns = await self._analyze_mode_patterns(interaction_groups["mode_selection"])
                patterns.extend(mode_patterns)
            
            # Analizar patrones de queries
            if "query_execution" in interaction_groups:
                query_patterns = await self._analyze_query_patterns(interaction_groups["query_execution"])
                patterns.extend(query_patterns)
            
            # Analizar patrones de uso de recursos
            if "resource_access" in interaction_groups:
                resource_patterns = await self._analyze_resource_patterns(interaction_groups["resource_access"])
                patterns.extend(resource_patterns)
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error analizando patrones: {e}")
            return []
    
    async def _analyze_mode_patterns(self, mode_interactions: List[Dict]) -> List[UserPattern]:
        """Analizar patrones de selección de modo"""
        try:
            patterns = []
            
            # Contar selecciones de modo
            mode_counts = {}
            for interaction in mode_interactions:
                mode = interaction["data"].get("selected_mode", "auto")
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            
            # Crear patrón para el modo más usado
            if mode_counts:
                preferred_mode = max(mode_counts, key=mode_counts.get)
                total_interactions = len(mode_interactions)
                confidence = mode_counts[preferred_mode] / total_interactions
                
                if confidence >= self.confidence_threshold:
                    pattern = UserPattern(
                        id=f"mode_pattern_{datetime.now().timestamp()}",
                        user_id=self.user_id,
                        pattern_type=PatternType.MODE_SELECTION,
                        pattern_data={
                            "mode": preferred_mode,
                            "usage_ratio": confidence,
                            "total_interactions": total_interactions
                        },
                        confidence=confidence,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        usage_count=mode_counts[preferred_mode]
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error analizando patrones de modo: {e}")
            return []
    
    async def _analyze_query_patterns(self, query_interactions: List[Dict]) -> List[UserPattern]:
        """Analizar patrones de queries"""
        try:
            patterns = []
            
            # Analizar complejidad de queries
            complexities = []
            for interaction in query_interactions:
                complexity = interaction["data"].get("complexity", 1)
                complexities.append(complexity)
            
            if complexities:
                avg_complexity = sum(complexities) / len(complexities)
                
                # Determinar nivel de complejidad
                if avg_complexity <= 1.5:
                    complexity_level = "simple"
                elif avg_complexity <= 2.5:
                    complexity_level = "moderate"
                else:
                    complexity_level = "complex"
                
                # Calcular confianza
                complexity_variance = sum((c - avg_complexity) ** 2 for c in complexities) / len(complexities)
                confidence = max(0.1, 1.0 - complexity_variance)
                
                if confidence >= self.confidence_threshold:
                    pattern = UserPattern(
                        id=f"query_pattern_{datetime.now().timestamp()}",
                        user_id=self.user_id,
                        pattern_type=PatternType.QUERY_PATTERNS,
                        pattern_data={
                            "complexity_level": complexity_level,
                            "average_complexity": avg_complexity,
                            "complexity_variance": complexity_variance,
                            "total_queries": len(complexities)
                        },
                        confidence=confidence,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        usage_count=len(complexities)
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error analizando patrones de queries: {e}")
            return []
    
    async def _analyze_resource_patterns(self, resource_interactions: List[Dict]) -> List[UserPattern]:
        """Analizar patrones de uso de recursos"""
        try:
            patterns = []
            
            # Contar acceso a recursos
            resource_counts = {}
            for interaction in resource_interactions:
                resource_type = interaction["data"].get("resource_type", "unknown")
                resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
            
            # Crear patrón para recursos más usados
            if resource_counts:
                preferred_resource = max(resource_counts, key=resource_counts.get)
                total_access = len(resource_interactions)
                confidence = resource_counts[preferred_resource] / total_access
                
                if confidence >= self.confidence_threshold:
                    pattern = UserPattern(
                        id=f"resource_pattern_{datetime.now().timestamp()}",
                        user_id=self.user_id,
                        pattern_type=PatternType.RESOURCE_USAGE,
                        pattern_data={
                            "preferred_resource": preferred_resource,
                            "usage_ratio": confidence,
                            "total_access": total_access,
                            "resource_distribution": resource_counts
                        },
                        confidence=confidence,
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        usage_count=resource_counts[preferred_resource]
                    )
                    patterns.append(pattern)
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error analizando patrones de recursos: {e}")
            return []
    
    async def _optimize_existing_patterns(self, new_patterns: List[UserPattern]) -> List[UserPattern]:
        """Optimizar patrones existentes con nuevos datos"""
        try:
            optimized_patterns = []
            
            for new_pattern in new_patterns:
                # Buscar patrón existente del mismo tipo
                existing_pattern = next(
                    (p for p in self.user_patterns 
                     if p.pattern_type == new_pattern.pattern_type and p.is_active),
                    None
                )
                
                if existing_pattern:
                    # Actualizar patrón existente
                    updated_pattern = await self._merge_patterns(existing_pattern, new_pattern)
                    optimized_patterns.append(updated_pattern)
                else:
                    # Agregar nuevo patrón
                    optimized_patterns.append(new_pattern)
            
            return optimized_patterns
            
        except Exception as e:
            self.logger.error(f"Error optimizando patrones: {e}")
            return new_patterns
    
    async def _merge_patterns(self, existing: UserPattern, new: UserPattern) -> UserPattern:
        """Fusionar patrón existente con nuevo"""
        try:
            # Calcular nueva confianza (promedio ponderado)
            total_usage = existing.usage_count + new.usage_count
            new_confidence = (
                (existing.confidence * existing.usage_count + new.confidence * new.usage_count) 
                / total_usage
            )
            
            # Fusionar datos del patrón
            merged_data = {**existing.pattern_data, **new.pattern_data}
            
            # Actualizar patrón existente
            existing.pattern_data = merged_data
            existing.confidence = new_confidence
            existing.usage_count = total_usage
            existing.updated_at = datetime.now()
            
            return existing
            
        except Exception as e:
            self.logger.error(f"Error fusionando patrones: {e}")
            return existing
    
    async def _generate_insight_from_pattern(self, pattern: UserPattern) -> Optional[PatternInsight]:
        """Generar insight a partir de un patrón"""
        try:
            insight_type = f"{pattern.pattern_type.value}_insight"
            description = ""
            recommendations = []
            
            if pattern.pattern_type == PatternType.MODE_SELECTION:
                mode = pattern.pattern_data.get("mode", "auto")
                usage_ratio = pattern.pattern_data.get("usage_ratio", 0)
                
                if mode == "explorer" and usage_ratio > 0.8:
                    description = "Prefieres explorar recursos antes de ejecutar acciones"
                    recommendations = [
                        "Considera usar el modo Guided para tareas específicas",
                        "El modo Auto podría sugerir transiciones automáticas"
                    ]
                elif mode == "guided" and usage_ratio > 0.8:
                    description = "Prefieres ejecutar acciones directamente con planificación"
                    recommendations = [
                        "El modo Explorer podría ser útil para descubrir nuevos recursos",
                        "Considera usar el modo Auto para consultas ambiguas"
                    ]
            
            elif pattern.pattern_type == PatternType.QUERY_PATTERNS:
                complexity_level = pattern.pattern_data.get("complexity_level", "moderate")
                
                if complexity_level == "simple":
                    description = "Tus consultas tienden a ser simples y directas"
                    recommendations = [
                        "El modo Explorer podría ser más eficiente para consultas simples",
                        "Considera usar el modo Guided para consultas más complejas"
                    ]
                elif complexity_level == "complex":
                    description = "Tus consultas tienden a ser complejas y detalladas"
                    recommendations = [
                        "El modo Guided es ideal para consultas complejas",
                        "Considera dividir consultas complejas en pasos más pequeños"
                    ]
            
            if description:
                insight = PatternInsight(
                    id=f"insight_{datetime.now().timestamp()}",
                    user_id=self.user_id,
                    insight_type=insight_type,
                    description=description,
                    confidence=pattern.confidence,
                    recommendations=recommendations,
                    created_at=datetime.now()
                )
                return insight
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generando insight: {e}")
            return None
    
    async def _should_learn(self) -> bool:
        """Determinar si es momento de aprender"""
        try:
            # Verificar cooldown
            if self.last_learning_update:
                time_since_update = datetime.now() - self.last_learning_update
                if time_since_update.total_seconds() < self.learning_cooldown:
                    return False
            
            # Verificar estado
            if self.learning_status in [LearningStatus.ANALYZING, LearningStatus.OPTIMIZING]:
                return False
            
            # Verificar si hay suficientes datos nuevos
            recent_interactions = await self._count_recent_interactions()
            return recent_interactions >= self.min_data_points
            
        except Exception as e:
            self.logger.error(f"Error verificando si debe aprender: {e}")
            return False
    
    async def _collect_recent_interactions(self) -> List[Dict]:
        """Recolectar interacciones recientes"""
        try:
            # Por ahora, retornamos lista vacía
            # En el futuro, esto vendría de una tabla de interacciones
            return []
            
        except Exception as e:
            self.logger.error(f"Error recolectando interacciones: {e}")
            return []
    
    async def _count_recent_interactions(self) -> int:
        """Contar interacciones recientes"""
        try:
            # Por ahora, retornamos 0
            # En el futuro, esto vendría de una tabla de interacciones
            return 0
            
        except Exception as e:
            self.logger.error(f"Error contando interacciones: {e}")
            return 0
    
    async def _apply_new_patterns(self, patterns: List[UserPattern]):
        """Aplicar nuevos patrones aprendidos"""
        try:
            # Actualizar patrones en cache local
            for pattern in patterns:
                # Buscar patrón existente
                existing_index = next(
                    (i for i, p in enumerate(self.user_patterns) 
                     if p.id == pattern.id),
                    None
                )
                
                if existing_index is not None:
                    # Actualizar existente
                    self.user_patterns[existing_index] = pattern
                else:
                    # Agregar nuevo
                    self.user_patterns.append(pattern)
            
            # Guardar en base de datos
            await self._save_user_patterns(self.user_patterns)
            
            self.logger.info(f"{len(patterns)} patrones aplicados")
            
        except Exception as e:
            self.logger.error(f"Error aplicando patrones: {e}")
    
    async def _load_user_patterns(self) -> List[UserPattern]:
        """Cargar patrones del usuario desde la base de datos"""
        try:
            # Por ahora, retornamos lista vacía
            # En el futuro, esto vendría de una tabla de patrones
            return []
            
        except Exception as e:
            self.logger.error(f"Error cargando patrones: {e}")
            return []
    
    async def _get_learning_status(self) -> LearningStatus:
        """Obtener estado de aprendizaje desde la base de datos"""
        try:
            # Por ahora, retornamos estado por defecto
            # En el futuro, esto vendría de una tabla de estado de aprendizaje
            return LearningStatus.COLLECTING
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estado de aprendizaje: {e}")
            return LearningStatus.COLLECTING
    
    async def _get_last_learning_update(self) -> Optional[datetime]:
        """Obtener última actualización de aprendizaje desde la base de datos"""
        try:
            # Por ahora, retornamos None
            # En el futuro, esto vendría de una tabla de estado de aprendizaje
            return None
            
        except Exception as e:
            self.logger.error(f"Error obteniendo última actualización: {e}")
            return None
    
    async def _save_interaction(self, interaction: Dict):
        """Guardar interacción en la base de datos"""
        # Implementar cuando se cree la tabla de interacciones
        pass
    
    async def _save_user_patterns(self, patterns: List[UserPattern]):
        """Guardar patrones del usuario en la base de datos"""
        # Implementar cuando se cree la tabla de patrones
        pass
    
    async def _update_learning_status(self, status: LearningStatus):
        """Actualizar estado de aprendizaje en la base de datos"""
        # Implementar cuando se cree la tabla de estado de aprendizaje
        pass
    
    async def _update_last_learning_update(self, timestamp: datetime):
        """Actualizar última actualización de aprendizaje en la base de datos"""
        # Implementar cuando se cree la tabla de estado de aprendizaje
        pass
    
    async def cleanup(self):
        """Limpiar recursos del servicio"""
        try:
            # Limpiar cache expirado
            current_time = datetime.now()
            expired_keys = []
            
            for key, value in self.cache.items():
                if current_time - value["timestamp"] > timedelta(seconds=self.cache_ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            self.logger.info(f"Cleanup completado - {len(expired_keys)} entradas expiradas removidas")
            
        except Exception as e:
            self.logger.error(f"Error en cleanup: {e}")
