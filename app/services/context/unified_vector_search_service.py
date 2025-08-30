"""
UnifiedVectorSearchService - Búsqueda vectorial unificada
────────────────────────────────────────────────────────
Servicio que unifica la búsqueda vectorial entre:
- Esquemas de base de datos (tablas, columnas, relaciones)
- APIs (endpoints, parámetros, respuestas)
- Estrategias (reglas, condiciones, acciones) - futuro
- Funciones (código, documentación) - futuro
"""

import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from app.services.context.extensible_embedding_service import (
    ExtensibleEmbeddingService,
    ResourceType,
    EmbeddingSearchResult
)
from app.services.context.vector_search_service import VectorSearchService
from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


@dataclass
class UnifiedSearchResult:
    """Resultado de búsqueda unificada"""
    resource_id: str
    resource_type: str  # "database", "api", "strategy", "function"
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    namespace: str
    relevance_boost: float = 1.0


@dataclass
class SearchContext:
    """Contexto de búsqueda para personalizar resultados"""
    user_id: UUID
    app_id: Optional[UUID] = None
    db_id: Optional[UUID] = None
    search_types: List[str] = None  # ["database", "api", "strategy", "function"]
    confidence_threshold: float = 0.7
    max_results_per_type: int = 5


class UnifiedVectorSearchService:
    """
    Servicio de búsqueda vectorial unificada que combina múltiples fuentes.
    Permite búsquedas inteligentes que abarcan tanto bases de datos como APIs.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        
        # Servicios especializados
        self.extensible_embedding_service = ExtensibleEmbeddingService(factory)
        self.db_vector_search_service = VectorSearchService()
        
        # Cache de resultados unificados
        self.search_cache = {}
        
        self.logger.info("[UnifiedVectorSearchService] 🔍 Inicializado con búsqueda unificada")
    
    async def unified_search(
        self,
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """
        Búsqueda unificada en múltiples fuentes de datos.
        
        Args:
            query: Query de búsqueda
            context: Contexto de búsqueda con filtros y preferencias
            
        Returns:
            Lista de resultados unificados ordenados por relevancia
        """
        try:
            self.logger.info(f"[UnifiedVectorSearchService] 🔍 Búsqueda unificada: '{query}' para user_id={context.user_id}")
            
            # Determinar tipos de búsqueda
            search_types = context.search_types or ["database", "api"]
            
            all_results = []
            
            # Búsqueda en bases de datos
            if "database" in search_types and context.db_id:
                db_results = await self._search_database_schemas(query, context)
                all_results.extend(db_results)
            
            # Búsqueda en APIs
            if "api" in search_types:
                api_results = await self._search_api_endpoints(query, context)
                all_results.extend(api_results)
            
            # Búsqueda en estrategias (futuro)
            if "strategy" in search_types:
                strategy_results = await self._search_strategies(query, context)
                all_results.extend(strategy_results)
            
            # Búsqueda en funciones (futuro)
            if "function" in search_types:
                function_results = await self._search_functions(query, context)
                all_results.extend(function_results)
            
            # Aplicar filtros de confianza
            filtered_results = [
                result for result in all_results
                if result.similarity_score >= context.confidence_threshold
            ]
            
            # Ordenar por relevancia combinada
            sorted_results = self._rank_results_by_relevance(filtered_results, query, context)
            
            # Limitar resultados por tipo
            final_results = self._limit_results_per_type(sorted_results, context.max_results_per_type)
            
            self.logger.info(f"[UnifiedVectorSearchService] ✅ Encontrados {len(final_results)} resultados unificados")
            return final_results
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error en búsqueda unificada: {e}")
            return []
    
    async def _search_database_schemas(
        self,
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """Búsqueda en esquemas de base de datos"""
        try:
            if not context.db_id:
                return []
            
            # Usar el servicio existente de búsqueda de DB
            db_results = await self.db_vector_search_service.semantic_search(
                db_id=context.db_id,
                query=query,
                top_k=context.max_results_per_type
            )
            
            # Convertir a formato unificado
            unified_results = []
            for result in db_results:
                unified_results.append(UnifiedSearchResult(
                    resource_id=result.element_id,
                    resource_type="database",
                    content=result.content,
                    similarity_score=result.similarity_score,
                    metadata={
                        **result.metadata,
                        "db_id": str(context.db_id),
                        "semantic_type": result.semantic_type
                    },
                    namespace=f"db_{context.db_id}",
                    relevance_boost=self._calculate_db_relevance_boost(result, query)
                ))
            
            return unified_results
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error buscando en DB: {e}")
            return []
    
    async def _search_api_endpoints(
        self,
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """Búsqueda en endpoints de API"""
        try:
            # Buscar en APIs usando el servicio extensible
            api_results = await self.extensible_embedding_service.search_embeddings(
                query=query,
                resource_types=[ResourceType.API_ENDPOINT, ResourceType.API_PARAMETER],
                namespace=f"api_{context.app_id}_*" if context.app_id else "api_*",
                top_k=context.max_results_per_type,
                app_id=str(context.app_id) if context.app_id else None
            )
            
            # Convertir a formato unificado
            unified_results = []
            for result in api_results:
                unified_results.append(UnifiedSearchResult(
                    resource_id=result.resource_id,
                    resource_type="api",
                    content=result.content,
                    similarity_score=result.similarity_score,
                    metadata={
                        **result.metadata,
                        "app_id": str(context.app_id) if context.app_id else None
                    },
                    namespace=result.namespace,
                    relevance_boost=self._calculate_api_relevance_boost(result, query)
                ))
            
            return unified_results
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error buscando en APIs: {e}")
            return []
    
    async def _search_strategies(
        self,
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """Búsqueda en estrategias (implementación futura)"""
        try:
            # TODO: Implementar cuando se añadan las estrategias
            self.logger.info("[UnifiedVectorSearchService] 🔮 Búsqueda en estrategias - implementación futura")
            return []
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error buscando en estrategias: {e}")
            return []
    
    async def _search_functions(
        self,
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """Búsqueda en funciones (implementación futura)"""
        try:
            # TODO: Implementar cuando se añadan las funciones embebibles
            self.logger.info("[UnifiedVectorSearchService] 🔮 Búsqueda en funciones - implementación futura")
            return []
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error buscando en funciones: {e}")
            return []
    
    def _calculate_db_relevance_boost(self, result: Any, query: str) -> float:
        """Calcular boost de relevancia para resultados de DB"""
        boost = 1.0
        
        # Boost por tipo semántico
        semantic_type = getattr(result, 'semantic_type', '')
        if semantic_type == 'table':
            boost += 0.2  # Las tablas son más relevantes
        elif semantic_type == 'column':
            boost += 0.1
        
        # Boost por coincidencia exacta en nombres
        query_lower = query.lower()
        if hasattr(result, 'element_id'):
            if query_lower in result.element_id.lower():
                boost += 0.3
        
        return min(boost, 2.0)  # Máximo boost de 2.0
    
    def _calculate_api_relevance_boost(self, result: EmbeddingSearchResult, query: str) -> float:
        """Calcular boost de relevancia para resultados de API"""
        boost = 1.0
        
        # Boost por tipo de recurso
        if result.resource_type == ResourceType.API_ENDPOINT:
            boost += 0.2  # Los endpoints son más relevantes
        elif result.resource_type == ResourceType.API_PARAMETER:
            boost += 0.1
        
        # Boost por método HTTP
        method = result.metadata.get("method", "").upper()
        if method in ["GET", "POST"]:
            boost += 0.1  # Métodos más comunes
        
        # Boost por coincidencia en casos de uso
        use_cases = result.metadata.get("use_cases", "")
        if use_cases and query.lower() in use_cases.lower():
            boost += 0.4
        
        return min(boost, 2.0)  # Máximo boost de 2.0
    
    def _rank_results_by_relevance(
        self,
        results: List[UnifiedSearchResult],
        query: str,
        context: SearchContext
    ) -> List[UnifiedSearchResult]:
        """Rankear resultados por relevancia combinada"""
        
        def calculate_combined_score(result: UnifiedSearchResult) -> float:
            # Score base de similitud
            base_score = result.similarity_score
            
            # Aplicar boost de relevancia
            boosted_score = base_score * result.relevance_boost
            
            # Boost por contexto del usuario
            context_boost = self._calculate_context_boost(result, context)
            
            return boosted_score * context_boost
        
        # Ordenar por score combinado
        return sorted(results, key=calculate_combined_score, reverse=True)
    
    def _calculate_context_boost(self, result: UnifiedSearchResult, context: SearchContext) -> float:
        """Calcular boost basado en el contexto del usuario"""
        boost = 1.0
        
        # Boost por app específica
        if context.app_id and result.metadata.get("app_id") == str(context.app_id):
            boost += 0.2
        
        # Boost por DB específica
        if context.db_id and result.metadata.get("db_id") == str(context.db_id):
            boost += 0.2
        
        return min(boost, 1.5)  # Máximo boost de contexto de 1.5
    
    def _limit_results_per_type(
        self,
        results: List[UnifiedSearchResult],
        max_per_type: int
    ) -> List[UnifiedSearchResult]:
        """Limitar resultados por tipo de recurso"""
        type_counts = {}
        limited_results = []
        
        for result in results:
            resource_type = result.resource_type
            current_count = type_counts.get(resource_type, 0)
            
            if current_count < max_per_type:
                limited_results.append(result)
                type_counts[resource_type] = current_count + 1
        
        return limited_results
    
    async def get_search_suggestions(
        self,
        partial_query: str,
        context: SearchContext,
        max_suggestions: int = 5
    ) -> List[str]:
        """Obtener sugerencias de búsqueda basadas en el contexto"""
        try:
            suggestions = []
            
            # Sugerencias de DB
            if "database" in (context.search_types or ["database"]) and context.db_id:
                db_suggestions = await self._get_db_suggestions(partial_query, context.db_id)
                suggestions.extend(db_suggestions)
            
            # Sugerencias de API
            if "api" in (context.search_types or ["api"]):
                api_suggestions = await self._get_api_suggestions(partial_query, context.app_id)
                suggestions.extend(api_suggestions)
            
            # Limitar y retornar
            return suggestions[:max_suggestions]
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error obteniendo sugerencias: {e}")
            return []
    
    async def _get_db_suggestions(self, partial_query: str, db_id: UUID) -> List[str]:
        """Obtener sugerencias de base de datos"""
        try:
            # TODO: Implementar sugerencias inteligentes de DB
            return [f"Buscar en {db_id}: {partial_query}"]
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error obteniendo sugerencias de DB: {e}")
            return []
    
    async def _get_api_suggestions(self, partial_query: str, app_id: Optional[UUID]) -> List[str]:
        """Obtener sugerencias de API"""
        try:
            # TODO: Implementar sugerencias inteligentes de API
            return [f"Buscar en APIs: {partial_query}"]
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error obteniendo sugerencias de API: {e}")
            return []
    
    async def get_search_analytics(self) -> Dict[str, Any]:
        """Obtener analytics de búsquedas"""
        try:
            analytics = {
                "total_searches": len(self.search_cache),
                "cache_hit_rate": 0.0,  # TODO: Implementar métricas
                "most_searched_types": [],
                "average_response_time": 0.0
            }
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"[UnifiedVectorSearchService] ❌ Error obteniendo analytics: {e}")
            return {}
