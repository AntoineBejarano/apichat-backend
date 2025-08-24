"""
🔥 Response Pre-generation Service: Generación en background para cache warming

Servicio que pre-genera respuestas comunes en background para mantener el cache
caliente y proporcionar respuestas instantáneas a los usuarios.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, Set
from uuid import UUID
from datetime import datetime, timedelta
import time
from enum import Enum

from app.services.cache.response_cache_service import ResponseCacheService, ResponseType
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.agent_router_service import AgentRouterService

logger = logging.getLogger(__name__)


class PreGenerationPriority(Enum):
    """Prioridades de pre-generación"""
    HIGH = "high"      # Respuestas críticas (explorer, fallback)
    MEDIUM = "medium"  # Respuestas comunes (guided, transition)
    LOW = "low"        # Respuestas opcionales (general, historical)


class ResponsePreGenerationService:
    """
    🔥 Servicio de pre-generación en background
    
    Funcionalidades:
    - Pre-generación automática de respuestas comunes
    - Cache warming inteligente basado en patrones de uso
    - Generación en background sin bloquear el usuario
    - Priorización de respuestas por importancia
    - Monitoreo de performance y hit ratio
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.cache_service = factory.get_response_cache_service()
        self.mode_detection_service = factory.get_mode_detection_service()
        self.agent_router_service = factory.get_agent_router_service()
        
        # Configuración de pre-generación
        self._pre_generation_config = {
            "enabled": True,
            "max_concurrent_tasks": 3,
            "batch_size": 10,
            "retry_attempts": 3,
            "retry_delay": 5  # segundos
        }
        
        # Estado del servicio
        self._is_running = False
        self._active_tasks: Set[asyncio.Task] = set()
        self._generation_stats = {
            "total_generated": 0,
            "successful": 0,
            "failed": 0,
            "last_run": None,
            "average_generation_time": 0.0
        }
        
        # Patrones de pre-generación
        self._pre_generation_patterns = self._init_pre_generation_patterns()
        
        logger.info(f"[ResponsePreGenerationService] 🚀 Inicializado para usuario {self.user_id}")
    
    def _init_pre_generation_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Inicializa patrones de pre-generación"""
        return {
            "explorer_responses": {
                "priority": PreGenerationPriority.HIGH,
                "frequency": "on_login",  # on_login, hourly, daily
                "response_type": ResponseType.EXPLORER,
                "cache_keys": [
                    "user_resources_overview",
                    "database_summary",
                    "application_summary",
                    "exploration_suggestions"
                ]
            },
            "fallback_responses": {
                "priority": PreGenerationPriority.HIGH,
                "frequency": "on_login",
                "response_type": ResponseType.FALLBACK,
                "cache_keys": [
                    "ambiguous_intent_fallback",
                    "error_fallback",
                    "general_help_fallback"
                ]
            },
            "guided_responses": {
                "priority": PreGenerationPriority.MEDIUM,
                "frequency": "hourly",
                "response_type": ResponseType.GUIDED,
                "cache_keys": [
                    "common_actions",
                    "sql_templates",
                    "execution_plans"
                ]
            },
            "transition_responses": {
                "priority": PreGenerationPriority.MEDIUM,
                "frequency": "hourly",
                "response_type": ResponseType.TRANSITION,
                "cache_keys": [
                    "explorer_to_guided",
                    "guided_to_explorer",
                    "mode_confirmation"
                ]
            }
        }
    
    async def start_pre_generation(self, trigger: str = "manual") -> Dict[str, Any]:
        """
        🚀 Inicia el proceso de pre-generación
        
        Args:
            trigger: Causa del inicio (manual, on_login, scheduled, etc.)
            
        Returns:
            Estadísticas de la pre-generación
        """
        try:
            if self._is_running:
                logger.info("[ResponsePreGenerationService] ⚠️ Pre-generación ya está ejecutándose")
                return {"status": "already_running", "stats": self._generation_stats}
            
            self._is_running = True
            start_time = time.time()
            
            logger.info(f"[ResponsePreGenerationService] 🔥 Iniciando pre-generación (trigger: {trigger})")
            
            # Limpiar estadísticas
            self._generation_stats = {
                "total_generated": 0,
                "successful": 0,
                "failed": 0,
                "last_run": datetime.utcnow().isoformat(),
                "average_generation_time": 0.0
            }
            
            # Ejecutar pre-generación por prioridad
            await self._execute_pre_generation_by_priority()
            
            # Calcular estadísticas finales
            total_time = time.time() - start_time
            self._generation_stats["average_generation_time"] = total_time / max(self._generation_stats["total_generated"], 1)
            
            logger.info(f"[ResponsePreGenerationService] ✅ Pre-generación completada en {total_time:.2f}s")
            logger.info(f"[ResponsePreGenerationService] 📊 Estadísticas: {self._generation_stats}")
            
            return {
                "status": "completed",
                "execution_time": total_time,
                "stats": self._generation_stats
            }
            
        except Exception as e:
            logger.exception(f"[ResponsePreGenerationService] ❌ Error en pre-generación: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            self._is_running = False
    
    async def _execute_pre_generation_by_priority(self):
        """Ejecuta pre-generación ordenada por prioridad"""
        try:
            # Ordenar patrones por prioridad
            priority_order = [PreGenerationPriority.HIGH, PreGenerationPriority.MEDIUM, PreGenerationPriority.LOW]
            
            for priority in priority_order:
                patterns = [
                    (name, config) for name, config in self._pre_generation_patterns.items()
                    if config["priority"] == priority
                ]
                
                if patterns:
                    logger.info(f"[ResponsePreGenerationService] 🎯 Procesando prioridad {priority.value}")
                    await self._process_priority_patterns(patterns)
                    
                    # Pequeña pausa entre prioridades
                    await asyncio.sleep(1)
            
        except Exception as e:
            logger.exception(f"[ResponsePreGenerationService] ❌ Error ejecutando por prioridad: {e}")
    
    async def _process_priority_patterns(self, patterns: List[tuple]):
        """Procesa patrones de una prioridad específica"""
        try:
            # Crear tareas para cada patrón
            tasks = []
            for pattern_name, pattern_config in patterns:
                task = asyncio.create_task(
                    self._generate_pattern_responses(pattern_name, pattern_config)
                )
                tasks.append(task)
                self._active_tasks.add(task)
            
            # Ejecutar tareas concurrentemente
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Procesar resultados
                for i, result in enumerate(results):
                    pattern_name = patterns[i][0]
                    if isinstance(result, Exception):
                        logger.error(f"[ResponsePreGenerationService] ❌ Error en patrón {pattern_name}: {result}")
                        self._generation_stats["failed"] += 1
                    else:
                        self._generation_stats["successful"] += 1
                        self._generation_stats["total_generated"] += result.get("generated", 0)
            
        except Exception as e:
            logger.exception(f"[ResponsePreGenerationService] ❌ Error procesando patrones: {e}")
        finally:
            # Limpiar tareas activas
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
            self._active_tasks.clear()
    
    async def _generate_pattern_responses(self, pattern_name: str, pattern_config: Dict[str, Any]) -> Dict[str, Any]:
        """Genera respuestas para un patrón específico"""
        try:
            start_time = time.time()
            generated_count = 0
            
            logger.info(f"[ResponsePreGenerationService] 🔧 Generando respuestas para patrón: {pattern_name}")
            
            # Generar respuestas para cada cache key del patrón
            for cache_key in pattern_config["cache_keys"]:
                try:
                    # Generar respuesta específica
                    response = await self._generate_specific_response(
                        cache_key, 
                        pattern_config["response_type"]
                    )
                    
                    if response:
                        # Cachear respuesta
                        success = await self.cache_service.cache_response(
                            cache_key,
                            response,
                            pattern_config["response_type"],
                            self.user_id
                        )
                        
                        if success:
                            generated_count += 1
                            logger.debug(f"[ResponsePreGenerationService] ✅ Respuesta generada y cacheada: {cache_key}")
                        else:
                            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error cacheando respuesta: {cache_key}")
                    
                    # Pequeña pausa entre generaciones
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando {cache_key}: {e}")
                    continue
            
            generation_time = time.time() - start_time
            logger.info(f"[ResponsePreGenerationService] ✅ Patrón {pattern_name} completado: {generated_count} respuestas en {generation_time:.2f}s")
            
            return {
                "pattern": pattern_name,
                "generated": generated_count,
                "execution_time": generation_time
            }
            
        except Exception as e:
            logger.exception(f"[ResponsePreGenerationService] ❌ Error generando patrón {pattern_name}: {e}")
            return {"pattern": pattern_name, "generated": 0, "error": str(e)}
    
    async def _generate_specific_response(self, cache_key: str, response_type: ResponseType) -> Optional[Dict[str, Any]]:
        """Genera una respuesta específica basada en la clave del cache"""
        try:
            if cache_key == "user_resources_overview":
                return await self._generate_user_resources_overview()
            elif cache_key == "database_summary":
                return await self._generate_database_summary()
            elif cache_key == "application_summary":
                return await self._generate_application_summary()
            elif cache_key == "exploration_suggestions":
                return await self._generate_exploration_suggestions()
            elif cache_key == "ambiguous_intent_fallback":
                return await self._generate_ambiguous_fallback()
            elif cache_key == "error_fallback":
                return await self._generate_error_fallback()
            elif cache_key == "common_actions":
                return await self._generate_common_actions()
            elif cache_key == "sql_templates":
                return await self._generate_sql_templates()
            elif cache_key == "execution_plans":
                return await self._generate_execution_plans()
            else:
                # Respuesta genérica
                return await self._generate_generic_response(cache_key, response_type)
                
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando respuesta específica {cache_key}: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   Generadores de respuestas específicas
    # ─────────────────────────────────────────────
    
    async def _generate_user_resources_overview(self) -> Dict[str, Any]:
        """Genera resumen general de recursos del usuario"""
        try:
            # TODO: Implementar generación real con AI
            return {
                "type": "explorer",
                "content": "Resumen de tus recursos disponibles",
                "generated_at": datetime.utcnow().isoformat(),
                "resources": {
                    "databases": "X bases de datos conectadas",
                    "applications": "Y aplicaciones integradas",
                    "strategies": "Z estrategias de negocio"
                },
                "suggestions": [
                    "Explora tus bases de datos para entender su estructura",
                    "Revisa las funciones disponibles en tus aplicaciones",
                    "Analiza las estrategias implementadas"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando overview: {e}")
            return None
    
    async def _generate_database_summary(self) -> Dict[str, Any]:
        """Genera resumen de bases de datos"""
        try:
            return {
                "type": "explorer",
                "content": "Resumen de tus bases de datos",
                "generated_at": datetime.utcnow().isoformat(),
                "summary": "Información detallada de cada base de datos conectada"
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando DB summary: {e}")
            return None
    
    async def _generate_application_summary(self) -> Dict[str, Any]:
        """Genera resumen de aplicaciones"""
        try:
            return {
                "type": "explorer",
                "content": "Resumen de tus aplicaciones",
                "generated_at": datetime.utcnow().isoformat(),
                "summary": "Funciones y capacidades de cada aplicación integrada"
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando app summary: {e}")
            return None
    
    async def _generate_exploration_suggestions(self) -> Dict[str, Any]:
        """Genera sugerencias de exploración"""
        try:
            return {
                "type": "explorer",
                "content": "Sugerencias para explorar tus recursos",
                "generated_at": datetime.utcnow().isoformat(),
                "suggestions": [
                    "Pregunta por la estructura de una base de datos específica",
                    "Solicita un análisis de rendimiento de tus aplicaciones",
                    "Explora las relaciones entre diferentes recursos"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando sugerencias: {e}")
            return None
    
    async def _generate_ambiguous_fallback(self) -> Dict[str, Any]:
        """Genera respuesta de fallback para intenciones ambiguas"""
        try:
            return {
                "type": "fallback",
                "content": "No estoy seguro de lo que quieres hacer. ¿Puedes ser más específico?",
                "generated_at": datetime.utcnow().isoformat(),
                "options": [
                    "Explorar recursos disponibles",
                    "Ejecutar una acción específica",
                    "Obtener ayuda general"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando fallback ambiguo: {e}")
            return None
    
    async def _generate_error_fallback(self) -> Dict[str, Any]:
        """Genera respuesta de fallback para errores"""
        try:
            return {
                "type": "fallback",
                "content": "Ha ocurrido un error. ¿Puedes reformular tu pregunta?",
                "generated_at": datetime.utcnow().isoformat(),
                "suggestions": [
                    "Usa comandos más simples",
                    "Especifica qué recurso quieres usar",
                    "Proporciona más contexto"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando fallback de error: {e}")
            return None
    
    async def _generate_common_actions(self) -> Dict[str, Any]:
        """Genera acciones comunes disponibles"""
        try:
            return {
                "type": "guided",
                "content": "Acciones comunes que puedes ejecutar",
                "generated_at": datetime.utcnow().isoformat(),
                "actions": [
                    "Analizar datos de una tabla",
                    "Crear consultas SQL personalizadas",
                    "Ejecutar funciones de aplicación",
                    "Generar reportes"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando acciones comunes: {e}")
            return None
    
    async def _generate_sql_templates(self) -> Dict[str, Any]:
        """Genera plantillas SQL comunes"""
        try:
            return {
                "type": "guided",
                "content": "Plantillas SQL comunes para usar",
                "generated_at": datetime.utcnow().isoformat(),
                "templates": [
                    "SELECT * FROM table_name LIMIT 10",
                    "SELECT COUNT(*) FROM table_name",
                    "SELECT column1, column2 FROM table_name WHERE condition"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando plantillas SQL: {e}")
            return None
    
    async def _generate_execution_plans(self) -> Dict[str, Any]:
        """Genera planes de ejecución comunes"""
        try:
            return {
                "type": "guided",
                "content": "Planes de ejecución predefinidos",
                "generated_at": datetime.utcnow().isoformat(),
                "plans": [
                    "Análisis de rendimiento de base de datos",
                    "Auditoría de seguridad de aplicaciones",
                    "Generación de reportes automáticos"
                ]
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando planes: {e}")
            return None
    
    async def _generate_generic_response(self, cache_key: str, response_type: ResponseType) -> Dict[str, Any]:
        """Genera respuesta genérica para claves no específicas"""
        try:
            return {
                "type": response_type.value,
                "content": f"Respuesta pre-generada para: {cache_key}",
                "generated_at": datetime.utcnow().isoformat(),
                "cache_key": cache_key
            }
        except Exception as e:
            logger.warning(f"[ResponsePreGenerationService] ⚠️ Error generando respuesta genérica: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   Métodos de control y monitoreo
    # ─────────────────────────────────────────────
    
    async def stop_pre_generation(self) -> bool:
        """🛑 Detiene la pre-generación en curso"""
        try:
            if not self._is_running:
                return True
            
            logger.info("[ResponsePreGenerationService] 🛑 Deteniendo pre-generación...")
            
            # Cancelar tareas activas
            for task in self._active_tasks:
                if not task.done():
                    task.cancel()
            
            # Esperar a que se cancelen
            if self._active_tasks:
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
                self._active_tasks.clear()
            
            self._is_running = False
            logger.info("[ResponsePreGenerationService] ✅ Pre-generación detenida")
            return True
            
        except Exception as e:
            logger.exception(f"[ResponsePreGenerationService] ❌ Error deteniendo pre-generación: {e}")
            return False
    
    def is_running(self) -> bool:
        """Verifica si la pre-generación está ejecutándose"""
        return self._is_running
    
    async def get_generation_stats(self) -> Dict[str, Any]:
        """📊 Obtiene estadísticas de pre-generación"""
        try:
            return {
                "user_id": str(self.user_id),
                "is_running": self._is_running,
                "active_tasks": len(self._active_tasks),
                "stats": self._generation_stats.copy(),
                "config": self._pre_generation_config.copy(),
                "patterns": {
                    name: {
                        "priority": config["priority"].value,
                        "frequency": config["frequency"],
                        "response_type": config["response_type"].value,
                        "cache_keys_count": len(config["cache_keys"])
                    }
                    for name, config in self._pre_generation_patterns.items()
                }
            }
        except Exception as e:
            logger.error(f"[ResponsePreGenerationService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def update_config(self, new_config: Dict[str, Any]) -> bool:
        """Actualiza la configuración del servicio"""
        try:
            # Validar configuración
            if "max_concurrent_tasks" in new_config:
                if new_config["max_concurrent_tasks"] < 1 or new_config["max_concurrent_tasks"] > 10:
                    raise ValueError("max_concurrent_tasks debe estar entre 1 y 10")
            
            # Aplicar cambios
            self._pre_generation_config.update(new_config)
            
            logger.info(f"[ResponsePreGenerationService] ✅ Configuración actualizada: {new_config}")
            return True
            
        except Exception as e:
            logger.error(f"[ResponsePreGenerationService] ❌ Error actualizando configuración: {e}")
            return False


# Función helper para dependency injection
def get_response_pre_generation_service(factory) -> ResponsePreGenerationService:
    """Obtiene una instancia del Response Pre-generation Service"""
    return ResponsePreGenerationService(factory)
