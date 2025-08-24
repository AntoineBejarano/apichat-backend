"""
🎯 Servicio de Pre-carga Inteligente para el Sistema Explorer/Guided

Este servicio implementa pre-carga inteligente para mejorar la experiencia del chat:
- Pre-carga de respuestas comunes en background
- Pre-computación de detección de modo
- Cache warming automático para patrones frecuentes
- Pre-generación de prompts personalizados
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import json

from app.core.service_factory import ServiceFactory
from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.prompt_builder_service import PromptBuilderService
from app.services.cache.response_cache_service import ResponseCacheService
from app.services.background.response_pre_generation_service import ResponsePreGenerationService

logger = logging.getLogger(__name__)


class PreloadPriority(Enum):
    """Prioridades de pre-carga"""
    CRITICAL = "critical"      # Respuestas esenciales (modo, agentes)
    HIGH = "high"              # Respuestas frecuentes
    MEDIUM = "medium"          # Respuestas moderadamente frecuentes
    LOW = "low"                # Respuestas ocasionales


class PreloadType(Enum):
    """Tipos de pre-carga"""
    MODE_DETECTION = "mode_detection"
    RESPONSE_CACHE = "response_cache"
    PROMPT_GENERATION = "prompt_generation"
    AGENT_ROUTING = "agent_routing"
    RESOURCE_PRIORITY = "resource_priority"


@dataclass
class PreloadTask:
    """Tarea de pre-carga"""
    task_id: str
    preload_type: PreloadType
    priority: PreloadPriority
    target_user_id: Optional[str]
    context: Dict[str, Any]
    created_at: datetime
    scheduled_for: datetime
    max_retries: int = 3
    retry_count: int = 0
    status: str = "pending"


class IntelligentPreloadService:
    """
    🚀 Servicio de Pre-carga Inteligente
    
    Implementa pre-carga automática para mejorar la experiencia del chat
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.user_id = None  # Se establece al inicializar
        self.preload_tasks: Dict[str, PreloadTask] = {}
        self.active_preloads: Set[str] = set()
        self.preload_patterns: Dict[str, Dict[str, Any]] = {}
        self.performance_metrics: Dict[str, List[float]] = {
            "mode_detection_ms": [],
            "prompt_generation_ms": [],
            "cache_warming_ms": [],
            "overall_preload_ms": []
        }
        
        # Configuración de pre-carga
        self.preload_config = {
            "max_concurrent_preloads": 5,
            "preload_batch_size": 10,
            "cache_warming_interval": 300,  # 5 minutos
            "mode_detection_ttl": 1800,      # 30 minutos
            "prompt_generation_ttl": 3600,   # 1 hora
            "max_preload_age": 7200,         # 2 horas
        }
        
        logger.info("[IntelligentPreloadService] 🚀 Servicio inicializado")
    
    async def initialize(self, user_id: str):
        """Inicializa el servicio para un usuario específico"""
        self.user_id = user_id
        logger.info(f"[IntelligentPreloadService] Inicializado para usuario: {user_id}")
        
        # Cargar patrones de pre-carga del usuario
        await self._load_user_preload_patterns()
        
        # Iniciar pre-carga inteligente
        await self._start_intelligent_preloading()
    
    async def _load_user_preload_patterns(self):
        """Carga patrones de pre-carga específicos del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, patrones por defecto
            self.preload_patterns = {
                "mode_detection": {
                    "patterns": [
                        "show my databases",
                        "explore resources",
                        "what can I do",
                        "help me with",
                        "create a plan"
                    ],
                    "frequency": "high",
                    "last_used": datetime.now()
                },
                "common_responses": {
                    "patterns": [
                        "database connection",
                        "api integration",
                        "schema analysis",
                        "performance optimization"
                    ],
                    "frequency": "medium",
                    "last_used": datetime.now()
                }
            }
            
            logger.info(f"[IntelligentPreloadService] Patrones cargados: {len(self.preload_patterns)}")
            
        except Exception as e:
            logger.warning(f"[IntelligentPreloadService] ⚠️ Error cargando patrones: {e}")
    
    async def _start_intelligent_preloading(self):
        """Inicia el proceso de pre-carga inteligente"""
        try:
            # Pre-carga crítica (modo, agentes)
            await self._preload_critical_components()
            
            # Pre-carga de patrones frecuentes
            await self._preload_frequent_patterns()
            
            # Cache warming automático
            await self._start_cache_warming()
            
            logger.info(f"[IntelligentPreloadService] ✅ Pre-carga inteligente iniciada")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error iniciando pre-carga: {e}")
    
    async def _preload_critical_components(self):
        """Pre-carga componentes críticos del sistema"""
        try:
            start_time = time.time()
            
            # 1. Pre-carga de detección de modo
            await self._preload_mode_detection()
            
            # 2. Pre-carga de agentes disponibles
            await self._preload_available_agents()
            
            # 3. Pre-carga de prompts base
            await self._preload_base_prompts()
            
            execution_time = (time.time() - start_time) * 1000
            self.performance_metrics["overall_preload_ms"].append(execution_time)
            
            logger.info(f"[IntelligentPreloadService] ✅ Componentes críticos pre-cargados en {execution_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando componentes críticos: {e}")
    
    async def _preload_mode_detection(self):
        """Pre-carga detección de modo para patrones comunes"""
        try:
            start_time = time.time()
            
            # Obtener servicio de detección de modo
            mode_service = self.factory.get_mode_detection_service()
            
            # Patrones comunes para pre-detección
            common_patterns = [
                "show my databases",
                "explore my resources",
                "create a plan for",
                "help me analyze",
                "what can I do with"
            ]
            
            for pattern in common_patterns:
                # Pre-detectar modo para cada patrón
                detection_result = await mode_service.detect_mode(
                    message=pattern,
                    context={"preload": True, "user_id": self.user_id}
                )
                
                # Guardar resultado en cache
                await self._cache_mode_detection(pattern, detection_result)
            
            execution_time = (time.time() - start_time) * 1000
            self.performance_metrics["mode_detection_ms"].append(execution_time)
            
            logger.info(f"[IntelligentPreloadService] ✅ Detección de modo pre-cargada en {execution_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando detección de modo: {e}")
    
    async def _preload_available_agents(self):
        """Pre-carga agentes disponibles para el usuario"""
        try:
            # Obtener servicio de agentes
            agent_service = self.factory.get_agent_service()
            
            # Pre-cargar agentes del usuario
            user_agents = await agent_service.get_agents_by_user(user_id=self.user_id)
            
            # Pre-cargar agentes genéricos del sistema
            system_user_id = "11111111-1111-1111-1111-111111111111"
            generic_agents = await agent_service.get_agents_by_user_and_generic(
                user_id=system_user_id,
                is_generic=True
            )
            
            # Guardar en cache
            all_agents = user_agents + generic_agents
            await self._cache_available_agents(all_agents)
            
            logger.info(f"[IntelligentPreloadService] ✅ {len(all_agents)} agentes pre-cargados")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando agentes: {e}")
    
    async def _preload_base_prompts(self):
        """Pre-carga prompts base personalizados"""
        try:
            start_time = time.time()
            
            # Obtener servicio de prompts
            prompt_service = self.factory.get_prompt_builder_service()
            
            # Pre-generar prompts para modos comunes
            modes = ["explorer", "guided", "auto"]
            contexts = [
                {"resource_type": "database", "action": "explore"},
                {"resource_type": "application", "action": "analyze"},
                {"resource_type": "strategy", "action": "plan"}
            ]
            
            for mode in modes:
                for context in contexts:
                    prompt = await prompt_service.build_prompt(
                        mode=mode,
                        user_context={"user_id": self.user_id},
                        resource_context=context
                    )
                    
                    # Guardar prompt en cache
                    await self._cache_generated_prompt(mode, context, prompt)
            
            execution_time = (time.time() - start_time) * 1000
            self.performance_metrics["prompt_generation_ms"].append(execution_time)
            
            logger.info(f"[IntelligentPreloadService] ✅ Prompts base pre-cargados en {execution_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando prompts: {e}")
    
    async def _preload_frequent_patterns(self):
        """Pre-carga patrones frecuentes del usuario"""
        try:
            # Obtener servicio de cache de respuestas
            response_cache = self.factory.get_response_cache_service()
            
            # Patrones frecuentes para pre-generar
            frequent_patterns = [
                "database overview",
                "resource summary",
                "connection status",
                "performance metrics"
            ]
            
            for pattern in frequent_patterns:
                # Crear tarea de pre-carga
                task = PreloadTask(
                    task_id=f"frequent_{pattern}_{int(time.time())}",
                    preload_type=PreloadType.RESPONSE_CACHE,
                    priority=PreloadPriority.HIGH,
                    target_user_id=self.user_id,
                    context={"pattern": pattern, "type": "frequent"},
                    created_at=datetime.now(),
                    scheduled_for=datetime.now()
                )
                
                # Ejecutar pre-carga
                await self._execute_preload_task(task)
            
            logger.info(f"[IntelligentPreloadService] ✅ Patrones frecuentes pre-cargados")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando patrones frecuentes: {e}")
    
    async def _start_cache_warming(self):
        """Inicia el proceso de cache warming automático"""
        try:
            # Crear tarea de cache warming
            task = PreloadTask(
                task_id=f"cache_warming_{int(time.time())}",
                preload_type=PreloadType.RESPONSE_CACHE,
                priority=PreloadPriority.MEDIUM,
                target_user_id=self.user_id,
                context={"type": "cache_warming", "interval": self.preload_config["cache_warming_interval"]},
                created_at=datetime.now(),
                scheduled_for=datetime.now() + timedelta(seconds=self.preload_config["cache_warming_interval"])
            )
            
            # Programar cache warming periódico
            asyncio.create_task(self._periodic_cache_warming(task))
            
            logger.info(f"[IntelligentPreloadService] ✅ Cache warming automático iniciado")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error iniciando cache warming: {e}")
    
    async def _periodic_cache_warming(self, task: PreloadTask):
        """Cache warming periódico"""
        while True:
            try:
                # Ejecutar cache warming
                await self._execute_cache_warming()
                
                # Esperar hasta la próxima ejecución
                await asyncio.sleep(self.preload_config["cache_warming_interval"])
                
            except Exception as e:
                logger.error(f"[IntelligentPreloadService] ❌ Error en cache warming periódico: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar
    
    async def _execute_cache_warming(self):
        """Ejecuta cache warming para respuestas comunes"""
        try:
            start_time = time.time()
            
            # Obtener servicio de pre-generación
            pregen_service = self.factory.get_response_pre_generation_service()
            
            # Patrones para cache warming
            warming_patterns = [
                "explorer_mode_intro",
                "guided_mode_intro",
                "auto_mode_intro",
                "resource_help",
                "mode_switching_help"
            ]
            
            for pattern in warming_patterns:
                await pregen_service.pre_generate_response(
                    pattern=pattern,
                    user_id=self.user_id,
                    priority="medium"
                )
            
            execution_time = (time.time() - start_time) * 1000
            self.performance_metrics["cache_warming_ms"].append(execution_time)
            
            logger.debug(f"[IntelligentPreloadService] Cache warming ejecutado en {execution_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error ejecutando cache warming: {e}")
    
    async def _execute_preload_task(self, task: PreloadTask):
        """Ejecuta una tarea de pre-carga específica"""
        try:
            if task.task_id in self.active_preloads:
                logger.debug(f"[IntelligentPreloadService] Tarea {task.task_id} ya en ejecución")
                return
            
            self.active_preloads.add(task.task_id)
            
            if task.preload_type == PreloadType.RESPONSE_CACHE:
                await self._preload_response_cache(task)
            elif task.preload_type == PreloadType.MODE_DETECTION:
                await self._preload_mode_detection_task(task)
            elif task.preload_type == PreloadType.PROMPT_GENERATION:
                await self._preload_prompt_generation(task)
            
            # Marcar tarea como completada
            task.status = "completed"
            logger.info(f"[IntelligentPreloadService] ✅ Tarea {task.task_id} completada")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error ejecutando tarea {task.task_id}: {e}")
            task.status = "failed"
            
            # Reintentar si es posible
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.scheduled_for = datetime.now() + timedelta(minutes=2 ** task.retry_count)
                logger.info(f"[IntelligentPreloadService] 🔄 Reintentando tarea {task.task_id} en {task.scheduled_for}")
            else:
                logger.error(f"[IntelligentPreloadService] ❌ Tarea {task.task_id} falló definitivamente")
        
        finally:
            self.active_preloads.discard(task.task_id)
    
    async def _preload_response_cache(self, task: PreloadTask):
        """Pre-carga cache de respuestas"""
        try:
            # Obtener servicio de pre-generación
            pregen_service = self.factory.get_response_pre_generation_service()
            
            pattern = task.context.get("pattern", "general")
            await pregen_service.pre_generate_response(
                pattern=pattern,
                user_id=self.user_id,
                priority="high"
            )
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando cache: {e}")
    
    async def _preload_mode_detection_task(self, task: PreloadTask):
        """Pre-carga detección de modo para una tarea específica"""
        try:
            # Obtener servicio de detección de modo
            mode_service = self.factory.get_mode_detection_service()
            
            pattern = task.context.get("pattern", "general")
            detection_result = await mode_service.detect_mode(
                message=pattern,
                context={"preload": True, "user_id": self.user_id}
            )
            
            # Guardar en cache
            await self._cache_mode_detection(pattern, detection_result)
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando detección de modo: {e}")
    
    async def _preload_prompt_generation(self, task: PreloadTask):
        """Pre-carga generación de prompts"""
        try:
            # Obtener servicio de prompts
            prompt_service = self.factory.get_prompt_builder_service()
            
            mode = task.context.get("mode", "auto")
            context = task.context.get("context", {})
            
            prompt = await prompt_service.build_prompt(
                mode=mode,
                user_context={"user_id": self.user_id},
                resource_context=context
            )
            
            # Guardar en cache
            await self._cache_generated_prompt(mode, context, prompt)
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error pre-cargando prompts: {e}")
    
    async def _cache_mode_detection(self, pattern: str, result: Dict[str, Any]):
        """Guarda resultado de detección de modo en cache"""
        try:
            # TODO: Implementar cache específico para detección de modo
            cache_key = f"mode_detection:{pattern}:{self.user_id}"
            # await self.redis_cache.set(cache_key, json.dumps(result), ex=self.preload_config["mode_detection_ttl"])
            
            logger.debug(f"[IntelligentPreloadService] Detección de modo cacheada: {pattern}")
            
        except Exception as e:
            logger.warning(f"[IntelligentPreloadService] ⚠️ Error cacheando detección: {e}")
    
    async def _cache_available_agents(self, agents: List[Any]):
        """Guarda agentes disponibles en cache"""
        try:
            # TODO: Implementar cache específico para agentes
            cache_key = f"available_agents:{self.user_id}"
            # await self.redis_cache.set(cache_key, json.dumps([str(a.id) for a in agents]), ex=3600)
            
            logger.debug(f"[IntelligentPreloadService] Agentes cacheados: {len(agents)}")
            
        except Exception as e:
            logger.warning(f"[IntelligentPreloadService] ⚠️ Error cacheando agentes: {e}")
    
    async def _cache_generated_prompt(self, mode: str, context: Dict[str, Any], prompt: str):
        """Guarda prompt generado en cache"""
        try:
            # TODO: Implementar cache específico para prompts
            context_hash = hash(json.dumps(context, sort_keys=True))
            cache_key = f"generated_prompt:{mode}:{context_hash}:{self.user_id}"
            # await self.redis_cache.set(cache_key, prompt, ex=self.preload_config["prompt_generation_ttl"])
            
            logger.debug(f"[IntelligentPreloadService] Prompt cacheado: {mode}")
            
        except Exception as e:
            logger.warning(f"[IntelligentPreloadService] ⚠️ Error cacheando prompt: {e}")
    
    async def get_preload_status(self) -> Dict[str, Any]:
        """Obtiene el estado actual de pre-carga"""
        return {
            "active_preloads": len(self.active_preloads),
            "total_tasks": len(self.preload_tasks),
            "performance_metrics": {
                "mode_detection_avg_ms": self._calculate_average("mode_detection_ms"),
                "prompt_generation_avg_ms": self._calculate_average("prompt_generation_ms"),
                "cache_warming_avg_ms": self._calculate_average("cache_warming_ms"),
                "overall_preload_avg_ms": self._calculate_average("overall_preload_ms")
            },
            "preload_patterns": len(self.preload_patterns),
            "cache_warming_active": "cache_warming" in [task.preload_type.value for task in self.preload_tasks.values()]
        }
    
    def _calculate_average(self, metric_key: str) -> float:
        """Calcula el promedio de una métrica"""
        values = self.performance_metrics.get(metric_key, [])
        return sum(values) / len(values) if values else 0.0
    
    async def cleanup(self):
        """Limpia recursos del servicio"""
        try:
            # Cancelar tareas activas
            self.active_preloads.clear()
            
            # Limpiar métricas antiguas
            for metric_key in self.performance_metrics:
                self.performance_metrics[metric_key] = self.performance_metrics[metric_key][-100:]  # Mantener solo las últimas 100
            
            logger.info(f"[IntelligentPreloadService] 🧹 Limpieza completada")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error en limpieza: {e}")
    
    async def force_preload(self, preload_type: PreloadType, context: Dict[str, Any] = None):
        """Fuerza una pre-carga específica"""
        try:
            task = PreloadTask(
                task_id=f"forced_{preload_type.value}_{int(time.time())}",
                preload_type=preload_type,
                priority=PreloadPriority.CRITICAL,
                target_user_id=self.user_id,
                context=context or {},
                created_at=datetime.now(),
                scheduled_for=datetime.now()
            )
            
            await self._execute_preload_task(task)
            logger.info(f"[IntelligentPreloadService] ✅ Pre-carga forzada ejecutada: {preload_type.value if hasattr(preload_type, 'value') else preload_type}")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error en pre-carga forzada: {e}")
    
    async def update_preload_patterns(self, new_patterns: Dict[str, Any]):
        """Actualiza patrones de pre-carga del usuario"""
        try:
            self.preload_patterns.update(new_patterns)
            
            # TODO: Persistir en base de datos
            logger.info(f"[IntelligentPreloadService] ✅ Patrones actualizados: {len(new_patterns)}")
            
        except Exception as e:
            logger.error(f"[IntelligentPreloadService] ❌ Error actualizando patrones: {e}")


# Factory function para crear el servicio
async def create_intelligent_preload_service(factory: ServiceFactory, user_id: str) -> IntelligentPreloadService:
    """Crea e inicializa el servicio de pre-carga inteligente"""
    service = IntelligentPreloadService(factory)
    await service.initialize(user_id)
    return service
