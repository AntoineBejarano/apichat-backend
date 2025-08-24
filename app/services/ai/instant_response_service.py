"""
⚡ Instant Response Service: Respuestas instantáneas con fallback inteligente

Servicio que proporciona respuestas en <50ms combinando cache pre-generado
con generación rápida cuando no hay cache disponible.
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple, List
from uuid import UUID
from datetime import datetime
from enum import Enum

from app.services.cache.response_cache_service import ResponseCacheService, ResponseType
from app.services.background.response_pre_generation_service import ResponsePreGenerationService
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.agent_router_service import AgentRouterService

logger = logging.getLogger(__name__)


class ResponseSpeed(Enum):
    """Velocidades de respuesta disponibles"""
    INSTANT = "instant"      # <50ms (cache)
    FAST = "fast"           # 50-200ms (generación rápida)
    NORMAL = "normal"       # 200ms+ (generación completa)


class InstantResponseService:
    """
    ⚡ Servicio de respuestas instantáneas
    
    Funcionalidades:
    - Respuestas en <50ms desde cache pre-generado
    - Fallback a generación rápida si no hay cache
    - Generación completa como último recurso
    - Monitoreo de performance y hit ratio
    - Trigger automático de pre-generación
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.cache_service = factory.get_response_cache_service()
        self.pre_generation_service = factory.get_response_pre_generation_service()
        self.mode_detection_service = factory.get_mode_detection_service()
        self.agent_router_service = factory.get_agent_router_service()
        
        # Configuración de velocidad
        self._speed_config = {
            "instant_threshold": 0.05,    # 50ms
            "fast_threshold": 0.2,        # 200ms
            "max_wait_time": 1.0,         # 1 segundo máximo
            "enable_fallback": True,
            "auto_pre_generation": True
        }
        
        # Estadísticas de performance
        self._performance_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fast_generation": 0,
            "normal_generation": 0,
            "average_response_time": 0.0,
            "cache_hit_ratio": 0.0
        }
        
        logger.info(f"[InstantResponseService] 🚀 Inicializado para usuario {self.user_id}")
    
    async def get_instant_response(
        self, 
        user_message: str, 
        context: Dict[str, Any],
        chat_id: Optional[UUID] = None,
        force_speed: Optional[ResponseSpeed] = None
    ) -> Tuple[Dict[str, Any], ResponseSpeed, float]:
        """
        ⚡ Obtiene respuesta instantánea con fallback inteligente
        
        Args:
            user_message: Mensaje del usuario
            context: Contexto actual
            chat_id: ID del chat para logging
            force_speed: Velocidad forzada (opcional)
            
        Returns:
            Tupla con (respuesta, velocidad_obtenida, tiempo_ejecución)
        """
        try:
            start_time = time.time()
            self._performance_stats["total_requests"] += 1
            
            logger.info(f"[InstantResponseService] ⚡ Solicitando respuesta instantánea para: '{user_message[:50]}...'")
            
            # 1. Intentar respuesta instantánea desde cache
            if not force_speed or force_speed == ResponseSpeed.INSTANT:
                instant_response = await self._try_instant_cache_response(user_message, context)
                if instant_response:
                    execution_time = time.time() - start_time
                    self._performance_stats["cache_hits"] += 1
                    self._update_performance_stats(execution_time)
                    
                    logger.info(f"[InstantResponseService] ✅ Respuesta instantánea en {execution_time*1000:.1f}ms")
                    return instant_response, ResponseSpeed.INSTANT, execution_time
            
            # 2. Fallback a generación rápida
            if self._speed_config["enable_fallback"] and (
                not force_speed or force_speed in [ResponseSpeed.FAST, ResponseSpeed.NORMAL]
            ):
                fast_response = await self._try_fast_generation(user_message, context)
                if fast_response:
                    execution_time = time.time() - start_time
                    self._performance_stats["fast_generation"] += 1
                    self._update_performance_stats(execution_time)
                    
                    logger.info(f"[InstantResponseService] ⚡ Respuesta rápida en {execution_time*1000:.1f}ms")
                    return fast_response, ResponseSpeed.FAST, execution_time
            
            # 3. Generación completa como último recurso
            normal_response = await self._generate_complete_response(user_message, context)
            execution_time = time.time() - start_time
            self._performance_stats["normal_generation"] += 1
            self._update_performance_stats(execution_time)
            
            logger.info(f"[InstantResponseService] 🔧 Respuesta completa en {execution_time*1000:.1f}ms")
            return normal_response, ResponseSpeed.NORMAL, execution_time
            
        except Exception as e:
            logger.exception(f"[InstantResponseService] ❌ Error obteniendo respuesta instantánea: {e}")
            execution_time = time.time() - start_time
            
            # Respuesta de error como fallback
            error_response = self._build_error_response(user_message, context, str(e))
            return error_response, ResponseSpeed.NORMAL, execution_time
    
    async def _try_instant_cache_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Intenta obtener respuesta instantánea desde cache"""
        try:
            # Generar clave de cache inteligente
            cache_key = self._generate_smart_cache_key(user_message, context)
            
            # Intentar obtener desde cache
            cached_response = await self.cache_service.get_cached_response(
                cache_key, 
                ResponseType.GENERAL
            )
            
            if cached_response:
                logger.debug(f"[InstantResponseService] ✅ Cache hit para key: {cache_key[:20]}...")
                return cached_response
            
            # Intentar con variaciones de la clave
            alternative_keys = self._generate_alternative_cache_keys(user_message, context)
            for alt_key in alternative_keys:
                cached_response = await self.cache_service.get_cached_response(
                    alt_key, 
                    ResponseType.GENERAL
                )
                if cached_response:
                    logger.debug(f"[InstantResponseService] ✅ Cache hit con clave alternativa: {alt_key[:20]}...")
                    return cached_response
            
            return None
            
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error intentando cache instantáneo: {e}")
            return None
    
    async def _try_fast_generation(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Intenta generación rápida con templates y respuestas pre-definidas"""
        try:
            # Detectar modo del usuario
            mode_detection = await self.mode_detection_service.detect_mode(
                user_message, context
            )
            
            detected_mode = mode_detection.get("detected_mode", "auto")
            
            # Generar respuesta rápida basada en el modo
            if detected_mode == "explorer":
                return await self._generate_fast_explorer_response(user_message, context)
            elif detected_mode == "guided":
                return await self._generate_fast_guided_response(user_message, context)
            elif detected_mode == "ambiguous":
                return await self._generate_fast_ambiguous_response(user_message, context)
            else:
                return await self._generate_fast_generic_response(user_message, context)
                
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error en generación rápida: {e}")
            return None
    
    async def _generate_complete_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera respuesta completa usando el sistema normal"""
        try:
            # TODO: Integrar con el sistema de generación completo
            # Por ahora, respuesta de placeholder
            return {
                "type": "complete_response",
                "content": f"Respuesta completa generada para: {user_message[:100]}...",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "complete",
                "context": context
            }
            
        except Exception as e:
            logger.error(f"[InstantResponseService] ❌ Error en generación completa: {e}")
            return self._build_error_response(user_message, context, str(e))
    
    # ─────────────────────────────────────────────
    #   Generadores de respuestas rápidas
    # ─────────────────────────────────────────────
    
    async def _generate_fast_explorer_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera respuesta rápida para modo Explorer"""
        try:
            return {
                "type": "explorer",
                "content": "Aquí tienes un resumen rápido de tus recursos disponibles. ¿Qué te gustaría explorar más en detalle?",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "explorer",
                "response_speed": "fast",
                "suggestions": [
                    "Ver estructura de bases de datos",
                    "Explorar funciones de aplicaciones",
                    "Revisar estrategias disponibles"
                ]
            }
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando respuesta Explorer rápida: {e}")
            return None
    
    async def _generate_fast_guided_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera respuesta rápida para modo Guided"""
        try:
            return {
                "type": "guided",
                "content": "Perfecto, veo que tienes recursos seleccionados. Estoy preparando un plan de ejecución detallado...",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "guided",
                "response_speed": "fast",
                "next_step": "Generando plan de ejecución completo"
            }
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando respuesta Guided rápida: {e}")
            return None
    
    async def _generate_fast_ambiguous_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera respuesta rápida para intenciones ambiguas"""
        try:
            return {
                "type": "ambiguous",
                "content": "No estoy seguro de lo que quieres hacer. ¿Puedes ser más específico?",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "ambiguous",
                "response_speed": "fast",
                "options": [
                    "Explorar recursos disponibles",
                    "Ejecutar acción específica",
                    "Obtener ayuda general"
                ]
            }
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando respuesta ambigua rápida: {e}")
            return None
    
    async def _generate_fast_generic_response(
        self, 
        user_message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Genera respuesta rápida genérica"""
        try:
            return {
                "type": "generic",
                "content": "Estoy procesando tu solicitud. Déjame preparar una respuesta detallada...",
                "generated_at": datetime.utcnow().isoformat(),
                "mode": "auto",
                "response_speed": "fast",
                "status": "processing"
            }
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando respuesta genérica rápida: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   Métodos de utilidad
    # ─────────────────────────────────────────────
    
    def _generate_smart_cache_key(self, user_message: str, context: Dict[str, Any]) -> str:
        """Genera clave de cache inteligente"""
        try:
            # Hash del mensaje + contexto relevante
            message_hash = hash(user_message.lower().strip())
            context_str = str(sorted([
                (k, v) for k, v in context.items() 
                if v and k in ["db_ids", "app_ids", "explorer"]
            ]))
            
            combined = f"{message_hash}:{context_str}"
            return f"instant_{hash(combined) % 1000000}"
            
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando cache key: {e}")
            return f"instant_{hash(user_message) % 1000000}"
    
    def _generate_alternative_cache_keys(self, user_message: str, context: Dict[str, Any]) -> List[str]:
        """Genera claves alternativas para cache"""
        try:
            alternatives = []
            
            # Clave sin contexto
            alternatives.append(f"instant_{hash(user_message.lower().strip()) % 1000000}")
            
            # Clave con solo modo
            if "explorer" in context:
                alternatives.append(f"instant_mode_{context['explorer']}_{hash(user_message.lower().strip()) % 1000000}")
            
            # Clave con palabras clave
            words = user_message.lower().split()[:3]  # Primeras 3 palabras
            if words:
                word_key = "_".join(words)
                alternatives.append(f"instant_words_{hash(word_key) % 1000000}")
            
            return alternatives
            
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error generando claves alternativas: {e}")
            return []
    
    def _build_error_response(self, user_message: str, context: Dict[str, Any], error: str) -> Dict[str, Any]:
        """Construye respuesta de error como fallback"""
        return {
            "type": "error",
            "content": "Ha ocurrido un error procesando tu solicitud. Por favor, inténtalo de nuevo.",
            "generated_at": datetime.utcnow().isoformat(),
            "mode": "error",
            "error": error,
            "fallback": True
        }
    
    def _update_performance_stats(self, execution_time: float):
        """Actualiza estadísticas de performance"""
        try:
            # Actualizar tiempo promedio
            total_requests = self._performance_stats["total_requests"]
            current_avg = self._performance_stats["average_response_time"]
            
            new_avg = ((current_avg * (total_requests - 1)) + execution_time) / total_requests
            self._performance_stats["average_response_time"] = new_avg
            
            # Actualizar ratio de cache hits
            total_requests = self._performance_stats["total_requests"]
            cache_hits = self._performance_stats["cache_hits"]
            
            if total_requests > 0:
                self._performance_stats["cache_hit_ratio"] = cache_hits / total_requests
                
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error actualizando estadísticas: {e}")
    
    async def trigger_pre_generation(self) -> bool:
        """🔔 Trigger automático de pre-generación"""
        try:
            if not self._speed_config["auto_pre_generation"]:
                return False
            
            # Verificar si es necesario pre-generar
            if self._performance_stats["cache_hit_ratio"] < 0.7:  # Menos del 70% de hits
                logger.info("[InstantResponseService] 🔔 Trigger automático de pre-generación (cache hit ratio bajo)")
                
                # Iniciar pre-generación en background
                await self.pre_generation_service.start_pre_generation("auto_trigger")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"[InstantResponseService] ⚠️ Error en trigger automático: {e}")
            return False
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """📊 Obtiene estadísticas de performance"""
        try:
            stats = {
                "user_id": str(self.user_id),
                "performance": self._performance_stats.copy(),
                "speed_config": self._speed_config.copy()
            }
            
            # Agregar estadísticas de cache service si está disponible
            if self.cache_service:
                try:
                    cache_stats = await self.cache_service.get_cache_stats()
                    stats["cache_service_stats"] = cache_stats
                except Exception as e:
                    stats["cache_service_stats"] = {"error": str(e)}
            else:
                stats["cache_service_stats"] = {"error": "Service not available"}
            
            # Agregar estadísticas de pre-generation service si está disponible
            if self.pre_generation_service:
                try:
                    pre_gen_stats = await self.pre_generation_service.get_generation_stats()
                    stats["pre_generation_stats"] = pre_gen_stats
                except Exception as e:
                    stats["pre_generation_stats"] = {"error": str(e)}
            else:
                stats["pre_generation_stats"] = {"error": "Service not available"}
            
            return stats
            
        except Exception as e:
            logger.error(f"[InstantResponseService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def update_speed_config(self, new_config: Dict[str, Any]) -> bool:
        """Actualiza la configuración de velocidad"""
        try:
            # Validar configuración
            if "instant_threshold" in new_config:
                if new_config["instant_threshold"] <= 0 or new_config["instant_threshold"] > 1:
                    raise ValueError("instant_threshold debe estar entre 0 y 1")
            
            if "fast_threshold" in new_config:
                if new_config["fast_threshold"] <= 0 or new_config["fast_threshold"] > 1:
                    raise ValueError("fast_threshold debe estar entre 0 y 1")
            
            # Aplicar cambios
            self._speed_config.update(new_config)
            
            logger.info(f"[InstantResponseService] ✅ Configuración de velocidad actualizada: {new_config}")
            return True
            
        except Exception as e:
            logger.error(f"[InstantResponseService] ❌ Error actualizando configuración: {e}")
            return False


# Función helper para dependency injection
def get_instant_response_service(factory) -> InstantResponseService:
    """Obtiene una instancia del Instant Response Service"""
    return InstantResponseService(factory)
