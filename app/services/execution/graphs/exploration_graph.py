import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state.exploration_state import ExplorationState

from .nodes.resource_inference import ResourceInferenceNode
from .nodes.planning_node import PlanningNode
from .nodes.execution_node import ExecutionNode
from .nodes.schema_optimization_node import SchemaOptimizationNode
from .nodes.schema_optimization_node_v3 import SchemaOptimizationNodeV3
from .nodes.smart_ai_node import SmartAINode  # 🧠 NUEVO: Smart AI Node
from .cache.optimized_schema_cache import OptimizedSchemaCache
from ...data.redis_cache_service import RedisCacheService
from ...data.connection_pool_service import ConnectionPoolService
from ...data.persistent_service_cache import PersistentServiceCache

logger = logging.getLogger(__name__)


class ExplorationGraph:
    """ExplorationGraph optimizado con ejecución paralela y lazy loading"""
    
    def __init__(self, factory=None):
        # Guardar referencia al factory
        self.factory = factory
        
        # Inicializar caches y servicios críticos en paralelo
        self._init_critical_services()
        
        # Inicializar nodos (lazy loading)
        self._nodes_initialized = False
        self._nodes = {}
        
        # Cache de esquemas optimizados
        self.optimized_schema_cache = OptimizedSchemaCache()
        
        # Nota: schema_optimization_node se inicializará en lazy loading con factory
        
        # Métricas de rendimiento
        self.performance_metrics = {}
        
        # Configuración de optimizaciones por fases
        self._phase3_enabled = False  # FASE 3: Schema Processing optimizado
        
        # 🧠 Smart AI System habilitado por defecto
        self._smart_ai_enabled = True
        
        logger.info("[ExplorationGraph] 🚀 Inicialización completada con Smart AI System")
    
    def _create_schema_optimization_node(self):
        """Crea el nodo de optimización según la configuración de fases"""
        if self._phase3_enabled:
            logger.info("[ExplorationGraph] 🚀 Creando Schema Optimization Node FASE 3")
            node = SchemaOptimizationNodeV3(
                factory=self.factory,
                schema_cache=self.schema_cache,
                optimized_schema_cache=self.optimized_schema_cache,
                service_cache=self.service_cache
            )
            
            # Configurar Redis cache si está disponible
            if hasattr(self, 'redis_cache') and self.redis_cache:
                node.set_redis_cache(self.redis_cache)
                logger.info("[ExplorationGraph] 🔗 Redis cache configurado para FASE 3")
            
            return node
        else:
            logger.info("[ExplorationGraph] 📋 Creando Schema Optimization Node tradicional")
            return SchemaOptimizationNode(
                factory=self.factory,
                schema_cache=self.schema_cache,
                optimized_schema_cache=self.optimized_schema_cache,
                service_cache=self.service_cache
            )
    
    def enable_phase3_optimizations(self, enabled: bool = True):
        """Habilita/deshabilita optimizaciones de FASE 3"""
        self._phase3_enabled = enabled
        
        # Si ya están inicializados los nodos, reinicializar el nodo de optimización
        if self._nodes_initialized and 'schema_optimization' in self._nodes:
            logger.info(f"[ExplorationGraph] 🔄 Reconfigurando Schema Optimization para FASE 3: {enabled}")
            self._nodes['schema_optimization'] = self._create_schema_optimization_node()
        
        logger.info(f"[ExplorationGraph] ⚙️ FASE 3 Schema Processing: {'HABILITADA' if enabled else 'DESHABILITADA'}")
    
    def get_phase3_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de FASE 3 si está habilitada"""
        if not self._phase3_enabled or 'schema_optimization' not in self._nodes:
            return {"phase3_enabled": False}
        
        node = self._nodes['schema_optimization']
        if hasattr(node, 'get_optimization_stats'):
            return node.get_optimization_stats()
        
        return {"phase3_enabled": True, "stats_available": False}
    
    def _init_critical_services(self):
        """Inicializa servicios críticos en paralelo"""
        logger.info("[ExplorationGraph] 🔧 Inicializando servicios críticos...")
        
        # Inicializar servicios críticos de forma lazy (se inicializarán cuando se necesiten)
        self._services_initialized = False
        
        # Inicializar caches básicos
        try:
            from .cache.schema_cache import SchemaCache
            from ...data.persistent_service_cache import PersistentServiceCache
            self.schema_cache = SchemaCache()
            self.service_cache = PersistentServiceCache()
        except ImportError as e:
            logger.warning(f"[ExplorationGraph] ⚠️ No se pudieron inicializar algunos caches: {e}")
            self.schema_cache = None
            self.service_cache = None
    
    async def _init_services_async(self):
        """Inicializa servicios críticos de forma asíncrona"""
        try:
            # Inicializar servicios en paralelo
            tasks = [
                self._init_redis_cache(),
                self._init_connection_pool(),
                self._init_service_cache()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verificar resultados
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[ExplorationGraph] ❌ Error inicializando servicio {i}: {result}")
                else:
                    logger.info(f"[ExplorationGraph] ✅ Servicio {i} inicializado correctamente")
                    
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error en inicialización asíncrona: {e}")
    
    async def _init_redis_cache(self):
        """Inicializa Redis cache"""
        try:
            self.redis_cache = RedisCacheService()
            logger.info("[ExplorationGraph] ✅ Redis cache inicializado")
            return True
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error inicializando Redis: {e}")
            return False
    
    async def _init_connection_pool(self):
        """Inicializa pool de conexiones"""
        try:
            self.connection_pool = ConnectionPoolService()
            
            # 🔧 FASE 2: Inicializar DatabaseConnectionCache unificado
            from .cache.database_connection_cache import get_database_connection_cache
            self.db_connection_cache = get_database_connection_cache()
            
            # 🔧 FASE 2: Configurar el cache unificado con el pool
            self.db_connection_cache.set_connection_pool_service(self.connection_pool)
            
            logger.info("[ExplorationGraph] ✅ Connection pool y DatabaseConnectionCache unificado inicializados")
            return True
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error inicializando connection pool: {e}")
            return False
    
    async def _init_service_cache(self):
        """Inicializa cache de servicios"""
        try:
            self.service_cache = PersistentServiceCache()
            logger.info("[ExplorationGraph] ✅ Service cache inicializado")
            return True
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error inicializando service cache: {e}")
            return False
    
    async def _ensure_services_initialized(self):
        """Asegura que los servicios asíncronos estén inicializados"""
        if not self._services_initialized:
            logger.info("[ExplorationGraph] 🔧 Inicializando servicios asíncronos...")
            await self._init_services_async()
            self._services_initialized = True
    
    def _ensure_nodes_initialized(self):
        """Asegura que los nodos estén inicializados (lazy loading)"""
        if not self._nodes_initialized:
            logger.info("[ExplorationGraph] 🔧 Inicializando nodos...")
            
            if not self.factory:
                logger.error("[ExplorationGraph] ❌ Factory no disponible para inicializar nodos")
                logger.error("[ExplorationGraph] ❌ Los nodos no se pueden inicializar sin factory")
                return
            
            # Verificar que los caches estén disponibles
            if not self.schema_cache or not self.service_cache:
                logger.error("[ExplorationGraph] ❌ Caches no disponibles para inicializar nodos")
                return
            
            # IMPORTANTE: Registrar factories ANTES de inicializar nodos
            self._register_service_factories()
            
            # 🔧 NUEVO: Conectar Redis al SchemaCache con verificación robusta
            if hasattr(self, 'redis_cache') and self.redis_cache:
                # Intentar conectar Redis con retry
                redis_connected = self._ensure_redis_connection()
                if redis_connected:
                    self.schema_cache.set_redis_cache(self.redis_cache)
                    logger.info("[ExplorationGraph] 🔗 Redis conectado al SchemaCache para persistencia")
                else:
                    logger.warning("[ExplorationGraph] ⚠️ Redis no disponible - usando solo cache local")
            else:
                logger.warning("[ExplorationGraph] ⚠️ Redis cache no configurado - usando solo cache local")
            
            # Inicializar nodos solo cuando se necesiten
            self._nodes = {
                'smart_ai': SmartAINode(factory=self.factory),  # 🧠 NUEVO: Smart AI Node
                'resource_inference': ResourceInferenceNode(
                    factory=self.factory,
                    schema_cache=self.schema_cache,
                    service_cache=self.service_cache
                ),
                'planning': PlanningNode(factory=self.factory),
                'execution': ExecutionNode(
                    factory=self.factory,
                    schema_cache=self.schema_cache,
                    service_cache=self.service_cache
                ),
                'schema_optimization': self._create_schema_optimization_node()
            }
            
            self._nodes_initialized = True
            logger.info("[ExplorationGraph] ✅ Nodos inicializados")
    
    def _get_node(self, node_name: str):
        """Obtiene un nodo específico (lazy loading)"""
        self._ensure_nodes_initialized()
        return self._nodes.get(node_name)
    
    def _register_service_factories(self):
        """Registra las funciones factory para servicios en el cache"""
        if not self.factory or not self.service_cache:
            logger.warning("[ExplorationGraph] ⚠️ No se pueden registrar factories - factory o service_cache no disponible")
            return
        
        try:
            # Registrar factories para servicios principales
            self.service_cache.register_service("database_service", self.factory.get_database_service)
            self.service_cache.register_service("detailed_schema_cache_service", self.factory.get_detailed_schema_cache_service)
            self.service_cache.register_service("app_service", self.factory.get_app_service)
            self.service_cache.register_service("function_service", self.factory.get_function_service)
            
            # Registrar factories para servicios de ejecución
            self.service_cache.register_service("execution_engine_service", self.factory.get_execution_engine_service)
            self.service_cache.register_service("openai_service", self.factory.get_openai_service)
            
            # Registrar factories para otros servicios que puedan necesitar los nodos
            if hasattr(self.factory, 'get_schema_cache_service'):
                self.service_cache.register_service("schema_cache_service", self.factory.get_schema_cache_service)
            if hasattr(self.factory, 'get_redis_cache_service'):
                self.service_cache.register_service("redis_cache_service", self.factory.get_redis_cache_service)
            if hasattr(self.factory, 'get_connection_pool_service'):
                self.service_cache.register_service("connection_pool_service", self.factory.get_connection_pool_service)
            
            logger.info("[ExplorationGraph] ✅ Factories de servicios registradas en cache")
            logger.info(f"[ExplorationGraph] 🔍 Servicios registrados: {list(self.service_cache._services.keys())}")
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error registrando factories: {e}")
            # Continuar sin fallar completamente
    
    def _ensure_redis_connection(self) -> bool:
        """Asegura que Redis esté conectado con retry y backoff"""
        if not hasattr(self, 'redis_cache') or not self.redis_cache:
            return False
        
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Intentar una operación simple de Redis
                if hasattr(self.redis_cache, 'ping'):
                    # Si tiene método ping, usarlo
                    ping_result = self.redis_cache.ping()
                    if ping_result:
                        logger.info(f"[ExplorationGraph] ✅ Redis conectado en intento {attempt + 1}")
                        return True
                else:
                    # Fallback: intentar obtener estadísticas
                    if hasattr(self.redis_cache, 'get_cache_stats'):
                        stats = self.redis_cache.get_cache_stats()
                        logger.info(f"[ExplorationGraph] ✅ Redis conectado en intento {attempt + 1} (via stats)")
                        return True
                
                # Si llegamos aquí, la conexión falló
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Backoff exponencial
                    logger.warning(f"[ExplorationGraph] ⚠️ Intento {attempt + 1} falló. Reintentando en {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"[ExplorationGraph] ❌ Redis no disponible después de {max_retries} intentos")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"[ExplorationGraph] ⚠️ Error Redis intento {attempt + 1}: {e}. Reintentando en {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"[ExplorationGraph] ❌ Error final Redis: {e}")
        
        return False
    
    def _clean_state_for_serialization(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Limpia el estado para que sea serializable con msgpack"""
        try:
            clean_state = {}
            
            for key, value in state.items():
                if self._is_serializable(value):
                    clean_state[key] = value
                else:
                    # Reemplazar objetos no serializables con información básica
                    clean_state[key] = self._convert_to_serializable(key, value)
                    logger.debug(f"[ExplorationGraph] 🔧 Objeto no serializable convertido: {key} -> {type(value).__name__}")
            
            logger.info(f"[ExplorationGraph] ✅ Estado limpiado para serialización: {len(clean_state)} campos")
            return clean_state
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error limpiando estado: {e}")
            # Retornar estado básico si falla la limpieza
            return {
                "chat_id": state.get("chat_id", "default"),
                "message": state.get("message", {}),
                "error": f"Error limpiando estado: {str(e)}"
            }
    
    def _is_serializable(self, obj) -> bool:
        """Verifica si un objeto es serializable con msgpack"""
        try:
            # Tipos básicos serializables
            if obj is None or isinstance(obj, (str, int, float, bool)):
                return True
            
            # Listas y diccionarios (recursivamente)
            if isinstance(obj, list):
                return all(self._is_serializable(item) for item in obj)
            
            if isinstance(obj, dict):
                return all(
                    isinstance(k, str) and self._is_serializable(v) 
                    for k, v in obj.items()
                )
            
            # Objetos específicos que sabemos que son serializables
            if hasattr(obj, '__dict__'):
                # Verificar si tiene método to_dict o similar
                if hasattr(obj, 'to_dict'):
                    return True
                if hasattr(obj, 'dict'):
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _convert_to_serializable(self, key: str, obj) -> Any:
        """Convierte un objeto no serializable a uno serializable"""
        try:
            # Casos específicos conocidos
            if key == "db_conns" and hasattr(obj, '__iter__'):
                # Convertir conexiones de BD a información básica
                return [{"type": "database_connection", "id": str(i)} for i, _ in enumerate(obj)]
            
            elif key == "db_conns" and hasattr(obj, 'engine'):
                # SQLDatabase individual
                return {"type": "sql_database", "has_engine": True}
            
            elif hasattr(obj, 'to_dict'):
                # Objetos con método to_dict
                return obj.to_dict()
            
            elif hasattr(obj, 'dict'):
                # Objetos con método dict (Pydantic)
                return obj.dict()
            
            elif hasattr(obj, '__dict__'):
                # Objetos con atributos
                return {
                    "type": obj.__class__.__name__,
                    "attributes": list(obj.__dict__.keys())
                }
            
            else:
                # Fallback genérico
                return {"type": str(type(obj)), "value": str(obj)}
                
        except Exception as e:
            logger.warning(f"[ExplorationGraph] ⚠️ Error convirtiendo {key}: {e}")
            return {"type": "conversion_error", "error": str(e)}
    
    async def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Ejecuta el grafo con optimizaciones de rendimiento"""
        start_time = time.time()
        
        try:
            # Inicializar servicios asíncronos si no están listos
            await self._ensure_services_initialized()
            
            # Inicializar nodos si no están listos
            self._ensure_nodes_initialized()
            
            # Limpiar el estado para que sea serializable
            clean_state = self._clean_state_for_serialization(state)
            
            # Crear grafo optimizado con Smart AI
            workflow = self._create_workflow_with_smart_ai()
            
            # Configurar checkpointer con claves obligatorias
            memory = MemorySaver()
            config = {
                "configurable": {
                    "thread_id": f"exploration_{clean_state.get('chat_id', 'default')}",
                    "checkpoint_ns": "exploration_workflow",
                    "checkpoint_id": f"checkpoint_{clean_state.get('chat_id', 'default')}"
                }
            }
            
            app = workflow.compile(checkpointer=memory)
            
            # Ejecutar el grafo con configuración
            result = await app.ainvoke(clean_state, config=config)
            
            # Calcular total de tokens al final
            if result and 'performance_metrics' in result:
                from .utils.performance_metrics import PerformanceMetrics
                perf_metrics = PerformanceMetrics()
                perf_metrics.token_metrics = result['performance_metrics'].get('tokens', {})
                total_tokens = perf_metrics.calculate_total_tokens()
                
                # Actualizar el resultado con el total de tokens
                result['performance_metrics']['tokens']['total_tokens'] = total_tokens
                logger.info(f"[ExplorationGraph] 🎯 Total de tokens calculado: {total_tokens}")
            
            # Registrar métricas de rendimiento
            execution_time = time.time() - start_time
            self.performance_metrics['last_execution_time'] = execution_time
            self.performance_metrics['total_executions'] = self.performance_metrics.get('total_executions', 0) + 1
            
            logger.info(f"[ExplorationGraph] ⚡ Ejecución completada en {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[ExplorationGraph] ❌ Error en ejecución ({execution_time:.2f}s): {e}")
            raise
    
    def _create_optimized_workflow(self) -> StateGraph:
        """Crea un workflow optimizado con ejecución paralela y Smart AI"""
        workflow = StateGraph(ExplorationState)
        
        # 🧠 NUEVO: Nodo de pre-procesamiento inteligente
        workflow.add_node("smart_ai_preprocessing", self._create_node_wrapper('smart_ai'))
        
        # Nodos existentes con wrappers que pasen performance_metrics
        workflow.add_node("infer_resources", self._create_node_wrapper('resource_inference'))
        workflow.add_node("optimize_schemas", self._create_node_wrapper('schema_optimization'))
        workflow.add_node("plan_or_reply", self._create_node_wrapper('planning'))
        workflow.add_node("execute_plan", self._create_node_wrapper('execution'))
        
        # 🚀 NUEVO FLUJO: Smart AI primero, luego flujo tradicional
        workflow.set_entry_point("smart_ai_preprocessing")
        workflow.add_edge("smart_ai_preprocessing", "infer_resources")
        workflow.add_edge("infer_resources", "optimize_schemas")
        workflow.add_edge("optimize_schemas", "plan_or_reply")
        workflow.add_edge("plan_or_reply", "execute_plan")
        workflow.add_edge("execute_plan", END)
        
        return workflow
    
    def _create_node_wrapper(self, node_name: str):
        """Crea un wrapper para un nodo que pase performance_metrics"""
        async def wrapper(state: ExplorationState):
            logger.info(f"[ExplorationGraph] 🚀 Ejecutando nodo: {node_name}")
            logger.info(f"[ExplorationGraph] 🔍 Estado recibido: {list(state.keys())}")
            
            node = self._get_node(node_name)
            if node:
                # Crear performance_metrics como dict serializable si no existe
                if 'performance_metrics' not in state:
                    state['performance_metrics'] = {
                        'performance': {
                            'init': 0.0,
                            'react_think': 0.0,
                            'schema_build': 0.0,
                            'openai_plan': 0.0,
                            'sql_exec': 0.0,
                            'total': 0.0
                        },
                        'tokens': {
                            'input_tokens': 0,
                            'output_tokens': 0,
                            'total_tokens': 0,
                            'schema_tokens': 0,
                            'prompt_tokens': 0,
                            'response_tokens': 0
                        }
                    }
                
                # Crear wrapper de PerformanceMetrics para el nodo
                from .utils.performance_metrics import PerformanceMetrics
                perf_metrics = PerformanceMetrics()
                perf_metrics.metrics = state['performance_metrics'].get('performance', {})
                perf_metrics.token_metrics = state['performance_metrics'].get('tokens', {})
                
                # Ejecutar el nodo y await el resultado
                try:
                    logger.info(f"[ExplorationGraph] 🔧 Ejecutando {node_name}.run()...")
                    result = await node.run(state, perf_metrics)
                    logger.info(f"[ExplorationGraph] 🔧 {node_name}.run() completado, resultado: {type(result)}")
                    
                    # Calcular total de tokens
                    perf_metrics.calculate_total_tokens()
                    
                    # Limpiar el resultado para que sea serializable
                    clean_result = self._clean_state_for_serialization(result) if result else state
                    
                    # Actualizar el estado con las métricas del nodo
                    if clean_result and 'performance_metrics' in clean_result:
                        state['performance_metrics'] = clean_result['performance_metrics']
                    else:
                        # Actualizar métricas en el estado
                        state['performance_metrics'] = perf_metrics.get_metrics()
                    
                    logger.info(f"[ExplorationGraph] ✅ Nodo {node_name} completado exitosamente")
                    return clean_result
                    
                except Exception as e:
                    logger.error(f"[ExplorationGraph] ❌ Error ejecutando nodo {node_name}: {e}")
                    logger.exception(f"[ExplorationGraph] ❌ Stack trace completo:")
                    # Retornar estado con error para que no falle el grafo
                    state['error'] = f"Error en nodo {node_name}: {str(e)}"
                    return state
            else:
                logger.error(f"[ExplorationGraph] ❌ Nodo {node_name} no encontrado")
                return state
        
        # Agregar logging de debug
        logger.info(f"[ExplorationGraph] 🔧 Wrapper creado para nodo: {node_name}")
        return wrapper
    
    async def _optimize_schemas_wrapper(self, state: ExplorationState) -> ExplorationState:
        """Wrapper para optimización de esquemas"""
        return await self.schema_optimization_node.run(state, {})
    
    # Métodos públicos para compatibilidad
    def get_optimized_schema(self, db_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene esquema optimizado del cache"""
        return self.optimized_schema_cache.get_optimized_schema(db_id)
    
    def has_optimized_schema(self, db_id: str) -> bool:
        """Verifica si existe esquema optimizado"""
        return self.optimized_schema_cache.has_optimized_schema(db_id)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de optimización"""
        return self.optimized_schema_cache.get_stats()
    
    def warm_up_optimized_cache(self, db_ids: List[str]):
        """Pre-calienta el cache de esquemas optimizados"""
        for db_id in db_ids:
            self.optimized_schema_cache.warm_up_cache(db_id)
    
    def clear_cache(self):
        """Limpia todos los caches"""
        if hasattr(self, 'optimized_schema_cache'):
            self.optimized_schema_cache.clear_cache()
        if hasattr(self, 'redis_cache'):
            self.redis_cache.clear_cache()
        if hasattr(self, 'service_cache'):
            self.service_cache.clear_cache()
        if hasattr(self, 'connection_pool'):
            self.connection_pool.clear_pool()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de todos los caches"""
        stats = {}
        
        if hasattr(self, 'optimized_schema_cache'):
            stats['optimized_schema'] = self.optimized_schema_cache.get_stats()
        if hasattr(self, 'redis_cache'):
            stats['redis'] = self.redis_cache.get_stats()
        if hasattr(self, 'service_cache'):
            stats['service'] = self.service_cache.get_cache_stats()
        if hasattr(self, 'connection_pool'):
            stats['connection_pool'] = self.connection_pool.get_pool_stats()
        
        return stats
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas de rendimiento"""
        return self.performance_metrics.copy()
    
    def get_cache_status(self) -> Dict[str, any]:
        """Obtiene el estado de todos los caches"""
        status = {
            "redis_available": hasattr(self, 'redis_cache') and self.redis_cache is not None,
            "schema_cache_status": {},
            "service_cache_status": {},
            "database_connection_cache_status": {}
        }
        
        # Estado del SchemaCache
        if hasattr(self, 'schema_cache') and self.schema_cache:
            status["schema_cache_status"] = self.schema_cache.get_cache_status()
        
        # Estado del ServiceCache
        if hasattr(self, 'service_cache') and self.service_cache:
            status["service_cache_status"] = {
                "total_services": len(self.service_cache._services),
                "registered_services": list(self.service_cache._services.keys())
            }
        
        # Estado del DatabaseConnectionCache
        if hasattr(self, 'db_connection_cache'):
            status["database_connection_cache_status"] = self.db_connection_cache.get_cache_stats()
        
        return status
    
    def force_redis_reconnection(self) -> bool:
        """Fuerza una nueva conexión a Redis"""
        logger.info("[ExplorationGraph] 🔄 Forzando reconexión Redis...")
        return self._ensure_redis_connection()

    # 🧠 MÉTODOS PARA SMART AI SYSTEM
    
    def enable_smart_ai(self, enabled: bool = True):
        """
        Habilita/deshabilita el Smart AI System.
        
        Args:
            enabled: True para habilitar, False para deshabilitar
        """
        if not hasattr(self, '_smart_ai_enabled'):
            self._smart_ai_enabled = True  # Por defecto habilitado
        
        self._smart_ai_enabled = enabled
        
        if self._smart_ai_enabled:
            logger.info("[ExplorationGraph] 🧠 Smart AI System HABILITADO")
        else:
            logger.info("[ExplorationGraph] 🧠 Smart AI System DESHABILITADO")
    
    def is_smart_ai_enabled(self) -> bool:
        """
        Verifica si el Smart AI System está habilitado.
        
        Returns:
            True si está habilitado, False en caso contrario
        """
        return getattr(self, '_smart_ai_enabled', True)
    
    def get_smart_ai_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del Smart AI System.
        
        Returns:
            Diccionario con estadísticas del Smart AI
        """
        try:
            if not self.is_smart_ai_enabled():
                return {"smart_ai_enabled": False}
            
            smart_ai_node = self._get_node('smart_ai')
            if smart_ai_node and hasattr(smart_ai_node, 'get_smart_ai_stats'):
                return smart_ai_node.get_smart_ai_stats()
            
            return {"smart_ai_enabled": True, "stats_available": False}
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error obteniendo estadísticas Smart AI: {e}")
            return {"smart_ai_enabled": True, "error": str(e)}
    
    async def warm_up_smart_ai_cache(self) -> bool:
        """
        Pre-calienta el cache del Smart AI System.
        
        Returns:
            True si el warm-up fue exitoso
        """
        try:
            if not self.is_smart_ai_enabled():
                logger.info("[ExplorationGraph] 🧠 Smart AI System deshabilitado - saltando warm-up")
                return False
            
            logger.info("[ExplorationGraph] 🔥 Iniciando warm-up del Smart AI cache...")
            
            smart_ai_node = self._get_node('smart_ai')
            if smart_ai_node and hasattr(smart_ai_node, 'warm_up_cache'):
                result = await smart_ai_node.warm_up_cache()
                if result:
                    logger.info("[ExplorationGraph] ✅ Warm-up del Smart AI cache completado")
                else:
                    logger.warning("[ExplorationGraph] ⚠️ Warm-up del Smart AI cache falló")
                return result
            
            logger.warning("[ExplorationGraph] ⚠️ Smart AI Node no disponible para warm-up")
            return False
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error en warm-up del Smart AI: {e}")
            return False
    
    def get_smart_ai_workflow_info(self) -> Dict[str, Any]:
        """
        Obtiene información del workflow del Smart AI System.
        
        Returns:
            Diccionario con información del workflow
        """
        try:
            if not self.is_smart_ai_enabled():
                return {"smart_ai_enabled": False}
            
            return {
                "smart_ai_enabled": True,
                "workflow": {
                    "entry_point": "smart_ai_preprocessing",
                    "flow": [
                        "smart_ai_preprocessing",
                        "infer_resources", 
                        "optimize_schemas",
                        "plan_or_reply",
                        "execute_plan"
                    ],
                    "smart_ai_position": "first",
                    "description": "Smart AI pre-procesa consultas antes de la inferencia de recursos"
                },
                "nodes": {
                    "smart_ai": "SmartAINode - Pre-procesamiento inteligente",
                    "resource_inference": "ResourceInferenceNode - Inferencia de recursos",
                    "schema_optimization": "SchemaOptimizationNode - Optimización de esquemas",
                    "planning": "PlanningNode - Generación de planes",
                    "execution": "ExecutionNode - Ejecución de planes"
                }
            }
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error obteniendo información del workflow: {e}")
            return {"smart_ai_enabled": True, "error": str(e)}
    
    def _create_workflow_with_smart_ai(self) -> StateGraph:
        """
        Crea workflow con Smart AI habilitado.
        
        Returns:
            StateGraph configurado con Smart AI
        """
        if self.is_smart_ai_enabled():
            return self._create_optimized_workflow()
        else:
            # Fallback a workflow sin Smart AI
            workflow = StateGraph(ExplorationState)
            
            workflow.add_node("infer_resources", self._create_node_wrapper('resource_inference'))
            workflow.add_node("optimize_schemas", self._create_node_wrapper('schema_optimization'))
            workflow.add_node("plan_or_reply", self._create_node_wrapper('planning'))
            workflow.add_node("execute_plan", self._create_node_wrapper('execution'))
            
            workflow.set_entry_point("infer_resources")
            workflow.add_edge("infer_resources", "optimize_schemas")
            workflow.add_edge("optimize_schemas", "plan_or_reply")
            workflow.add_edge("plan_or_reply", "execute_plan")
            workflow.add_edge("execute_plan", END)
            
            return workflow
