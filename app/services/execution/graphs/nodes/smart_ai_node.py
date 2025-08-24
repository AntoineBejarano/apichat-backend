#!/usr/bin/env python3
"""
🤖 SmartAINode - Pre-procesamiento Inteligente de Consultas
────────────────────────────────────────────────────────────
Integra SmartRephraseService e IntentRouterService en el flujo
del ExplorationGraph para procesar consultas de forma inteligente
antes de la inferencia de recursos.
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.ai.smart_ai_orchestrator import SmartAIOrchestrator
from ..state.exploration_state import ExplorationState
from ..utils.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class SmartAINode:
    """
    🤖 Nodo que pre-procesa consultas usando Smart AI System.
    
    Características:
    - Rephrase inteligente de consultas
    - Clasificación de intenciones
    - Enrutamiento inteligente
    - Cache inteligente con versioning
    - Métricas de performance
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.orchestrator = SmartAIOrchestrator()
        self._performance_metrics = PerformanceMetrics()
        
        logger.info("[SmartAINode] 🚀 Nodo Smart AI inicializado")
    
    async def run(self, state: ExplorationState, performance_metrics: PerformanceMetrics) -> ExplorationState:
        """
        🤖 Procesa consulta con Smart AI System.
        
        Args:
            state: Estado del grafo con consulta y contexto
            performance_metrics: Métricas de performance del nodo
            
        Returns:
            Estado enriquecido con resultados del Smart AI
        """
        node_start_time = time.time()
        
        try:
            # Extraer información del estado
            # 🔧 CORRECCIÓN: message es ChatMessage, no dict, usar atributos directos
            message = state.get("message")
            if message and hasattr(message, 'content'):
                query = message.content
            else:
                query = ""
            
            chat_id = state.get("chat_id", "default")
            user_id = state.get("user_id", "default")
            
            if not query:
                logger.warning("[SmartAINode] ⚠️ No hay consulta para procesar")
                return state
            
            logger.info(f"[SmartAINode] 🤖 Procesando consulta: '{query[:100]}...'")
            
            # 🚀 PROCESAMIENTO INTELIGENTE CON SMART AI
            smart_result = await self.orchestrator.process_query_intelligently(
                query=query,
                context={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "source": "exploration_graph"
                }
            )
            
            # 📊 ENRIQUECER ESTADO CON RESULTADOS DEL SMART AI
            # 🔧 CORRECCIÓN: _enrich_state_with_smart_ai modifica state directamente
            await self._enrich_state_with_smart_ai(state, smart_result)
            
            # 📈 CALCULAR MÉTRICAS DE PERFORMANCE
            execution_time = time.time() - node_start_time
            performance_metrics.record_node_performance("smart_ai", execution_time)
            
            # 📊 REGISTRAR MÉTRICAS DEL SMART AI
            if 'performance_metrics' not in state:
                state['performance_metrics'] = {}
            if 'smart_ai' not in state['performance_metrics']:
                state['performance_metrics']['smart_ai'] = {}
            
            state['performance_metrics']['smart_ai'].update({
                'execution_time': execution_time,
                'rephrase_confidence': smart_result.get('rephrase', {}).get('confidence', 0.0),
                'intent_confidence': smart_result.get('intent', {}).get('confidence', 0.0),
                'cache_hit': smart_result.get('cache_hit', False),
                'processing_steps': len(smart_result.get('processing_steps', []))
            })
            
            logger.info(f"[SmartAINode] ✅ Consulta procesada en {execution_time:.3f}s")
            logger.info(f"[SmartAINode] 🎯 Intención: {smart_result.get('intent', {}).get('intent_type', 'unknown')}")
            logger.info(f"[SmartAINode] 🔄 Rephrase: {smart_result.get('rephrase', {}).get('normalized_query', '')[:50]}...")
            
            return state
            
        except Exception as e:
            execution_time = time.time() - node_start_time
            logger.error(f"[SmartAINode] ❌ Error procesando consulta ({execution_time:.3f}s): {e}")
            
            # 🛡️ FALLBACK: Retornar estado original sin enriquecer
            if 'performance_metrics' not in state:
                state['performance_metrics'] = {}
            if 'smart_ai' not in state['performance_metrics']:
                state['performance_metrics']['smart_ai'] = {}
            
            state['performance_metrics']['smart_ai'].update({
                'execution_time': execution_time,
                'error': str(e),
                'fallback_used': True
            })
            
            return state
    
    async def _enrich_state_with_smart_ai(self, state: ExplorationState, smart_result: Dict[str, Any]) -> ExplorationState:
        """
        📊 Enriquece el estado con los resultados del Smart AI.
        
        Args:
            state: Estado original del grafo
            smart_result: Resultado del procesamiento inteligente
            
        Returns:
            Estado enriquecido
        """
        try:
            # 🔄 REPHRASE
            if 'rephrase' in smart_result:
                state['normalized_query'] = smart_result['rephrase'].get('normalized_query', '')
                state['rephrase_confidence'] = smart_result['rephrase'].get('confidence', 0.0)
                state['rephrase_metadata'] = smart_result['rephrase'].get('metadata', {})
            
            # 🎯 INTENT CLASSIFICATION
            if 'intent' in smart_result:
                state['intent_type'] = smart_result['intent'].get('intent_type', 'unknown')
                state['intent_confidence'] = smart_result['intent'].get('confidence', 0.0)
                state['routing_path'] = smart_result['intent'].get('routing_path', [])
                state['intent_metadata'] = smart_result['intent'].get('metadata', {})
            
            # 🧠 SMART AI RESULT COMPLETO
            state['smart_ai_result'] = smart_result
            
            # 📋 PROCESSING STEPS
            if 'processing_steps' in smart_result:
                state['smart_ai_processing_steps'] = smart_result['processing_steps']
            
            # 🎯 RECOMMENDATIONS
            if 'recommendations' in smart_result:
                state['smart_ai_recommendations'] = smart_result['recommendations']
            
            # 📊 CACHE INFO
            if 'cache_info' in smart_result:
                state['smart_ai_cache_info'] = smart_result['cache_info']
            
            logger.info(f"[SmartAINode] 📊 Estado enriquecido con {len(smart_result)} campos del Smart AI")
            
            return state
            
        except Exception as e:
            logger.error(f"[SmartAINode] ❌ Error enriqueciendo estado: {e}")
            return state
    
    def get_smart_ai_stats(self) -> Dict[str, Any]:
        """
        📊 Obtiene estadísticas del Smart AI System.
        
        Returns:
            Diccionario con estadísticas
        """
        try:
            return self.orchestrator.get_combined_statistics()
        except Exception as e:
            logger.error(f"[SmartAINode] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def warm_up_cache(self) -> bool:
        """
        🔥 Pre-calienta el cache del Smart AI System.
        
        Returns:
            True si el warm-up fue exitoso
        """
        try:
            logger.info("[SmartAINode] 🔥 Iniciando warm-up del cache...")
            
            # Warm-up con consultas de ejemplo
            test_queries = [
                "¿Cuántos usuarios hay?",
                "Muestra las tablas disponibles",
                "Ejecuta esta función API",
                "Conecta con MCP"
            ]
            
            for query in test_queries:
                await self.orchestrator.process_query_intelligently(
                    query=query,
                    context={"source": "warm_up"}
                )
            
            logger.info("[SmartAINode] ✅ Warm-up del cache completado")
            return True
            
        except Exception as e:
            logger.error(f"[SmartAINode] ❌ Error en warm-up: {e}")
            return False
