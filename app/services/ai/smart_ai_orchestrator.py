import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import UUID

from .smart_rephrase_service import SmartRephraseService, RephraseRequest, RephraseResult
from .intent_router_service import IntentRouterService, IntentRequest, IntentResult, IntentType

logger = logging.getLogger(__name__)


class SmartAIOrchestrator:
    """
    Orquestador inteligente que integra rephrase y clasificación de intenciones
    Proporciona un punto único de entrada para el procesamiento inteligente de consultas
    """
    
    def __init__(self):
        # Servicios inteligentes
        self._rephrase_service = SmartRephraseService()
        self._intent_service = IntentRouterService()
        
        # Cache compartido
        self._redis_cache = None
        self._redis_connected = False
        
        # Estadísticas del orquestador
        self._stats = {
            'total_requests': 0,
            'rephrase_requests': 0,
            'intent_requests': 0,
            'combined_requests': 0,
            'avg_total_time_ms': 0.0,
            'cache_hit_rate': 0.0
        }
        
        logger.info("[SmartAIOrchestrator] 🚀 Orquestador inteligente inicializado")
    
    def set_redis_cache(self, redis_cache):
        """Configura Redis cache para ambos servicios"""
        self._redis_cache = redis_cache
        self._redis_connected = True
        
        # Configurar Redis en ambos servicios
        self._rephrase_service.set_redis_cache(redis_cache)
        self._intent_service.set_redis_cache(redis_cache)
        
        logger.info("[SmartAIOrchestrator] 🔗 Redis cache configurado para ambos servicios")
    
    async def process_query_intelligently(self, query: str, context: Dict[str, Any] = None,
                                        user_id: Optional[UUID] = None, session_id: Optional[str] = None,
                                        language: str = "auto", domain: str = "general",
                                        force_refresh: bool = False) -> Dict[str, Any]:
        """
        Procesa una consulta de forma inteligente combinando rephrase y clasificación
        
        Args:
            query: Consulta original del usuario
            context: Contexto adicional
            user_id: ID del usuario
            session_id: ID de sesión
            language: Idioma de la consulta
            domain: Dominio de la consulta
            force_refresh: Si forzar refresco del cache
            
        Returns:
            Resultado completo con rephrase e intención clasificada
        """
        start_time = time.time()
        
        try:
            # Actualizar estadísticas
            self._stats['total_requests'] += 1
            
            # Contexto por defecto
            context = context or {}
            
            # 1. REPHRASE: Normalizar y estandarizar la consulta
            logger.debug(f"[SmartAIOrchestrator] 🔄 Procesando rephrase para: {query[:50]}...")
            self._stats['rephrase_requests'] += 1
            
            rephrase_result = await self._rephrase_service.rephrase_query(
                original_query=query,
                language=language,
                domain=domain,
                context=context,
                user_id=user_id,
                force_refresh=force_refresh
            )
            
            # 2. INTENT CLASSIFICATION: Clasificar la intención de la consulta normalizada
            logger.debug(f"[SmartAIOrchestrator] 🎯 Clasificando intención para: {rephrase_result.normalized_query[:50]}...")
            self._stats['intent_requests'] += 1
            
            # Agregar contexto del rephrase
            enhanced_context = {
                **context,
                "original_query": query,
                "normalized_query": rephrase_result.normalized_query,
                "rephrase_confidence": rephrase_result.confidence_score,
                "language": language,
                "domain": domain
            }
            
            intent_result = await self._intent_service.classify_intent(
                query=rephrase_result.normalized_query,
                context=enhanced_context,
                user_id=user_id,
                session_id=session_id,
                force_refresh=force_refresh
            )
            
            # 3. RESULTADO COMBINADO
            self._stats['combined_requests'] += 1
            
            total_time = (time.time() - start_time) * 1000
            self._update_time_stats(total_time)
            
            result = {
                "orchestrator_id": f"orch_{int(time.time())}",
                "timestamp": datetime.now().isoformat(),
                "processing_time_ms": total_time,
                
                # Información original
                "original_query": query,
                "user_id": str(user_id) if user_id else None,
                "session_id": session_id,
                
                # Resultado del rephrase
                "rephrase": {
                    "normalized_query": rephrase_result.normalized_query,
                    "confidence_score": rephrase_result.confidence_score,
                    "language": rephrase_result.language,
                    "domain": rephrase_result.domain,
                    "version": rephrase_result.version,
                    "cache_key": rephrase_result.cache_key
                },
                
                # Resultado de la clasificación
                "intent": {
                    "intent_type": intent_result.intent_type.value,
                    "confidence_score": intent_result.confidence_score,
                    "routing_path": intent_result.routing_path,
                    "suggested_actions": intent_result.suggested_actions,
                    "metadata": intent_result.metadata
                },
                
                # Recomendaciones del orquestador
                "recommendations": self._generate_recommendations(rephrase_result, intent_result),
                
                # Estadísticas de cache
                "cache_stats": {
                    "rephrase_cache_hit": rephrase_result.cache_key != "fallback",
                    "intent_cache_hit": intent_result.intent_id.startswith("fallback") == False
                }
            }
            
            logger.info(f"[SmartAIOrchestrator] ✅ Consulta procesada en {total_time:.1f}ms - "
                       f"Rephrase: {rephrase_result.confidence_score:.2f}, "
                       f"Intent: {intent_result.intent_type.value} ({intent_result.confidence_score:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error procesando consulta: {e}")
            
            # Fallback en caso de error
            return {
                "orchestrator_id": f"error_{int(time.time())}",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "original_query": query,
                "fallback": True,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
    
    async def batch_process_queries(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Procesa múltiples consultas en batch de forma inteligente
        
        Args:
            queries: Lista de consultas con metadatos
            
        Returns:
            Lista de resultados procesados
        """
        start_time = time.time()
        
        try:
            # Procesar consultas en paralelo
            tasks = []
            for query_data in queries:
                task = self.process_query_intelligently(
                    query=query_data['query'],
                    context=query_data.get('context', {}),
                    user_id=query_data.get('user_id'),
                    session_id=query_data.get('session_id'),
                    language=query_data.get('language', 'auto'),
                    domain=query_data.get('domain', 'general'),
                    force_refresh=query_data.get('force_refresh', False)
                )
                tasks.append(task)
            
            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filtrar errores
            valid_results = []
            for result in results:
                if isinstance(result, dict) and "error" not in result:
                    valid_results.append(result)
                else:
                    logger.error(f"[SmartAIOrchestrator] ❌ Error en batch: {result}")
            
            batch_time = (time.time() - start_time) * 1000
            logger.info(f"[SmartAIOrchestrator] 📦 Batch completado: {len(valid_results)}/{len(queries)} en {batch_time:.1f}ms")
            
            return valid_results
            
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error en batch processing: {e}")
            return []
    
    async def get_smart_suggestions(self, query: str, context: Dict[str, Any] = None,
                                   user_id: Optional[UUID] = None, limit: int = 5) -> Dict[str, Any]:
        """
        Obtiene sugerencias inteligentes basadas en consultas similares
        
        Args:
            query: Consulta de referencia
            context: Contexto adicional
            user_id: ID del usuario
            limit: Número máximo de sugerencias
            
        Returns:
            Sugerencias inteligentes combinadas
        """
        try:
            # Obtener sugerencias de rephrase
            rephrase_suggestions = self._rephrase_service.get_similar_rephrases(query, limit)
            
            # Obtener sugerencias de intención
            intent_suggestions = self._intent_service.get_similar_intents(query, limit)
            
            # Combinar y rankear sugerencias
            combined_suggestions = []
            
            # Agregar sugerencias de rephrase
            for rephrase_result, similarity in rephrase_suggestions:
                combined_suggestions.append({
                    "type": "rephrase",
                    "content": rephrase_result.normalized_query,
                    "similarity": similarity,
                    "confidence": rephrase_result.confidence_score,
                    "domain": rephrase_result.domain,
                    "usage_count": rephrase_result.usage_count
                })
            
            # Agregar sugerencias de intención
            for intent_result, similarity in intent_suggestions:
                combined_suggestions.append({
                    "type": "intent",
                    "content": intent_result.query,
                    "similarity": similarity,
                    "confidence": intent_result.confidence_score,
                    "intent_type": intent_result.intent_type.value,
                    "routing_path": intent_result.routing_path
                })
            
            # Ordenar por similitud y confianza
            combined_suggestions.sort(
                key=lambda x: (x["similarity"], x["confidence"]), 
                reverse=True
            )
            
            return {
                "query": query,
                "suggestions": combined_suggestions[:limit],
                "total_found": len(combined_suggestions),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error obteniendo sugerencias: {e}")
            return {
                "query": query,
                "suggestions": [],
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas completas del orquestador"""
        rephrase_stats = self._rephrase_service.get_cache_stats()
        intent_stats = self._intent_service.get_intent_stats()
        
        return {
            "orchestrator": {
                **self._stats,
                "cache_hit_rate": f"{self._stats['cache_hit_rate']:.1f}%"
            },
            "rephrase_service": rephrase_stats,
            "intent_service": intent_stats,
            "combined_metrics": {
                "total_processing_time_saved_ms": (
                    rephrase_stats.get('total_time_saved_ms', 0) + 
                    intent_stats.get('total_time_saved_ms', 0)
                ),
                "overall_cache_hit_rate": (
                    (rephrase_stats.get('cache_hits', 0) + intent_stats.get('cache_hits', 0)) /
                    max(1, rephrase_stats.get('total_requests', 0) + intent_stats.get('total_requests', 0)) * 100
                )
            }
        }
    
    def invalidate_cache_by_domain(self, domain: str):
        """Invalida cache por dominio en ambos servicios"""
        try:
            self._rephrase_service.invalidate_cache_by_domain(domain)
            logger.info(f"[SmartAIOrchestrator] 🗑️ Cache invalidado por dominio: {domain}")
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error invalidando cache por dominio: {e}")
    
    def invalidate_cache_by_version(self, version: str):
        """Invalida cache por versión en ambos servicios"""
        try:
            self._rephrase_service.invalidate_cache_by_version(version)
            logger.info(f"[SmartAIOrchestrator] 🗑️ Cache invalidado por versión: {version}")
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error invalidando cache por versión: {e}")
    
    # ==================== MÉTODOS PRIVADOS ====================
    
    def _generate_recommendations(self, rephrase_result: RephraseResult, 
                                 intent_result: IntentResult) -> List[str]:
        """Genera recomendaciones basadas en los resultados"""
        recommendations = []
        
        try:
            # Recomendaciones basadas en confianza del rephrase
            if rephrase_result.confidence_score < 0.7:
                recommendations.append("Considera reformular tu consulta para mejor comprensión")
            
            # Recomendaciones basadas en tipo de intención
            if intent_result.intent_type == IntentType.DB_QUERY:
                recommendations.append("Consulta de base de datos detectada - se aplicará validación de esquema")
            elif intent_result.intent_type == IntentType.API_FUNCTION:
                recommendations.append("Función de API detectada - se validarán parámetros")
            elif intent_result.intent_type == IntentType.MCP_INTEGRATION:
                recommendations.append("Integración MCP detectada - se cargarán herramientas disponibles")
            
            # Recomendaciones basadas en ruta de enrutamiento
            if intent_result.routing_path == "fallback":
                recommendations.append("Ruta de enrutamiento no determinada - usando procesamiento genérico")
            
            # Recomendaciones de optimización
            if rephrase_result.confidence_score > 0.9 and intent_result.confidence_score > 0.9:
                recommendations.append("Consulta altamente optimizada - procesamiento rápido esperado")
            
        except Exception as e:
            logger.error(f"[SmartAIOrchestrator] ❌ Error generando recomendaciones: {e}")
            recommendations.append("Error generando recomendaciones")
        
        return recommendations
    
    def _update_time_stats(self, processing_time: float):
        """Actualiza estadísticas de tiempo de procesamiento"""
        if self._stats['avg_total_time_ms'] == 0:
            self._stats['avg_total_time_ms'] = processing_time
        else:
            # Promedio móvil simple
            self._stats['avg_total_time_ms'] = (
                self._stats['avg_total_time_ms'] * 0.8 + processing_time * 0.2
            )
