import asyncio
import logging
import time
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from uuid import UUID
from enum import Enum

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """Tipos de intenciones soportadas"""
    DB_QUERY = "db_query"
    API_FUNCTION = "api_function"
    MCP_INTEGRATION = "mcp_integration"
    CHAT_GENERAL = "chat_general"
    SCHEMA_ANALYSIS = "schema_analysis"
    DATA_VISUALIZATION = "data_visualization"
    SYSTEM_COMMAND = "system_command"
    UNKNOWN = "unknown"


@dataclass
class IntentRequest:
    """Request de clasificación de intención"""
    query: str
    context: Dict[str, Any]
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class IntentResult:
    """Resultado de la clasificación de intención"""
    intent_id: str
    query: str
    intent_type: IntentType
    confidence_score: float
    metadata: Dict[str, Any]
    suggested_actions: List[str]
    routing_path: str
    created_at: datetime
    processing_time_ms: float


@dataclass
class RoutingRule:
    """Regla de enrutamiento para un tipo de intención"""
    intent_type: IntentType
    priority: int
    target_service: str
    conditions: Dict[str, Any]
    actions: List[str]
    fallback_service: Optional[str] = None


class IntentRouterService:
    """
    Servicio de clasificación de intenciones y enrutamiento inteligente
    Clasifica en: db_query | api_function | mcp_integration | chat_general
    """
    
    def __init__(self):
        # Cache de intenciones
        self._intent_cache: Dict[str, IntentResult] = {}
        self._query_index: Dict[str, List[str]] = {}  # query_hash -> [intent_ids]
        
        # Reglas de enrutamiento
        self._routing_rules: Dict[IntentType, List[RoutingRule]] = {}
        
        # Modelo de clasificación (simulado por ahora)
        self._classification_model_enabled = True
        self._confidence_threshold = 0.6
        
        # Redis cache (se configura externamente)
        self._redis_cache = None
        self._redis_connected = False
        
        # Estadísticas
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'classifications': 0,
            'routing_decisions': 0,
            'avg_confidence': 0.0,
            'total_time_saved_ms': 0
        }
        
        # Inicializar reglas de enrutamiento por defecto
        self._initialize_default_routing_rules()
        
        logger.info("[IntentRouterService] 🧠 Servicio de clasificación de intenciones inicializado")
    
    def set_redis_cache(self, redis_cache):
        """Configura Redis cache para persistencia"""
        self._redis_cache = redis_cache
        self._redis_connected = True
        logger.info("[IntentRouterService] 🔗 Redis cache configurado")
    
    async def classify_intent(self, query: str, context: Dict[str, Any] = None,
                             user_id: Optional[UUID] = None, session_id: Optional[str] = None,
                             force_refresh: bool = False) -> IntentResult:
        """
        Clasifica la intención de una consulta
        
        Args:
            query: Consulta del usuario
            context: Contexto adicional
            user_id: ID del usuario
            session_id: ID de sesión
            force_refresh: Si forzar refresco del cache
            
        Returns:
            Resultado de la clasificación con intención detectada
        """
        start_time = time.time()
        
        try:
            # Validar parámetros
            context = context or {}
            
            # Crear request
            request = IntentRequest(
                query=query,
                context=context,
                user_id=user_id,
                session_id=session_id
            )
            
            # Generar cache key
            cache_key = self._generate_cache_key(request)
            
            # Verificar cache si no se fuerza refresco
            if not force_refresh:
                cached_result = await self._get_cached_intent(cache_key)
                if cached_result:
                    self._stats['cache_hits'] += 1
                    cache_time = (time.time() - start_time) * 1000
                    self._stats['total_time_saved_ms'] += cache_time
                    
                    logger.debug(f"[IntentRouterService] 🔥 Cache HIT: intención en {cache_time:.1f}ms")
                    return cached_result
            
            # Cache MISS - clasificar nueva intención
            self._stats['cache_misses'] += 1
            logger.debug(f"[IntentRouterService] ❌ Cache MISS para: {query[:50]}...")
            
            # Clasificar intención con modelo
            intent_type, confidence_score, metadata = await self._classify_with_model(request)
            
            # Determinar ruta de enrutamiento
            routing_path, suggested_actions = self._determine_routing_path(intent_type, metadata)
            
            # Crear resultado
            intent_result = IntentResult(
                intent_id=self._generate_intent_id(request),
                query=query,
                intent_type=intent_type,
                confidence_score=confidence_score,
                metadata=metadata,
                suggested_actions=suggested_actions,
                routing_path=routing_path,
                created_at=datetime.now(),
                processing_time_ms=(time.time() - start_time) * 1000
            )
            
            # Cachear resultado
            await self._cache_intent_result(intent_result)
            
            # Actualizar estadísticas
            self._stats['classifications'] += 1
            self._stats['routing_decisions'] += 1
            self._update_confidence_stats(confidence_score)
            
            classification_time = (time.time() - start_time) * 1000
            logger.info(f"[IntentRouterService] ✅ Intención clasificada: {intent_type.value} en {classification_time:.1f}ms (confianza: {confidence_score:.2f})")
            
            return intent_result
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error clasificando intención: {e}")
            # Fallback: intención desconocida
            return IntentResult(
                intent_id=f"fallback_{int(time.time())}",
                query=query,
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                metadata={"error": str(e)},
                suggested_actions=["fallback_processing"],
                routing_path="fallback",
                created_at=datetime.now(),
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    async def batch_classify(self, queries: List[Dict[str, Any]]) -> List[IntentResult]:
        """
        Clasificación en batch para múltiples consultas
        
        Args:
            queries: Lista de consultas con metadatos
            
        Returns:
            Lista de resultados de clasificación
        """
        start_time = time.time()
        
        try:
            # Procesar consultas en paralelo
            tasks = []
            for query_data in queries:
                task = self.classify_intent(
                    query=query_data['query'],
                    context=query_data.get('context', {}),
                    user_id=query_data.get('user_id'),
                    session_id=query_data.get('session_id')
                )
                tasks.append(task)
            
            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filtrar errores
            valid_results = []
            for result in results:
                if isinstance(result, IntentResult):
                    valid_results.append(result)
                else:
                    logger.error(f"[IntentRouterService] ❌ Error en batch classify: {result}")
            
            batch_time = (time.time() - start_time) * 1000
            logger.info(f"[IntentRouterService] 📦 Batch completado: {len(valid_results)}/{len(queries)} en {batch_time:.1f}ms")
            
            return valid_results
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error en batch classify: {e}")
            return []
    
    def add_routing_rule(self, rule: RoutingRule):
        """Agrega una nueva regla de enrutamiento"""
        try:
            if rule.intent_type not in self._routing_rules:
                self._routing_rules[rule.intent_type] = []
            
            # Insertar por prioridad (mayor prioridad primero)
            rules = self._routing_rules[rule.intent_type]
            insert_index = 0
            for i, existing_rule in enumerate(rules):
                if existing_rule.priority < rule.priority:
                    insert_index = i
                    break
                insert_index = i + 1
            
            rules.insert(insert_index, rule)
            
            logger.info(f"[IntentRouterService] ✅ Regla de enrutamiento agregada: {rule.intent_type.value} -> {rule.target_service}")
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error agregando regla de enrutamiento: {e}")
    
    def remove_routing_rule(self, intent_type: IntentType, target_service: str):
        """Remueve una regla de enrutamiento específica"""
        try:
            if intent_type in self._routing_rules:
                rules = self._routing_rules[intent_type]
                rules[:] = [rule for rule in rules if rule.target_service != target_service]
                
                logger.info(f"[IntentRouterService] ✅ Regla de enrutamiento removida: {intent_type.value} -> {target_service}")
                
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error removiendo regla de enrutamiento: {e}")
    
    def get_routing_rules(self, intent_type: IntentType = None) -> Dict[IntentType, List[RoutingRule]]:
        """Obtiene las reglas de enrutamiento"""
        if intent_type:
            return {intent_type: self._routing_rules.get(intent_type, [])}
        return self._routing_rules.copy()
    
    def get_similar_intents(self, query: str, limit: int = 5) -> List[Tuple[IntentResult, float]]:
        """Obtiene intenciones similares para una consulta"""
        try:
            similar_results = []
            query_hash = self._generate_query_hash(query)
            
            # Buscar en índice
            if query_hash in self._query_index:
                for intent_id in self._query_index[query_hash]:
                    if intent_id in self._intent_cache:
                        result = self._intent_cache[intent_id]
                        similarity = self._calculate_similarity(query, result.query)
                        if similarity > 0.6:  # Umbral de similitud
                            similar_results.append((result, similarity))
            
            # Ordenar por similitud
            similar_results.sort(key=lambda x: x[1], reverse=True)
            return similar_results[:limit]
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error obteniendo intenciones similares: {e}")
            return []
    
    def get_intent_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de intenciones por tipo"""
        intent_counts = {}
        for intent_type in IntentType:
            intent_counts[intent_type.value] = 0
        
        for result in self._intent_cache.values():
            intent_counts[result.intent_type.value] += 1
        
        return {
            **self._stats,
            'cached_intents': len(self._intent_cache),
            'query_index_size': len(self._query_index),
            'intent_distribution': intent_counts,
            'routing_rules_count': sum(len(rules) for rules in self._routing_rules.values())
        }
    
    # ==================== MÉTODOS PRIVADOS ====================
    
    def _initialize_default_routing_rules(self):
        """Inicializa reglas de enrutamiento por defecto"""
        try:
            # Reglas para DB_QUERY
            self.add_routing_rule(RoutingRule(
                intent_type=IntentType.DB_QUERY,
                priority=100,
                target_service="database_service",
                conditions={"requires_schema": True},
                actions=["query_execution", "schema_validation"],
                fallback_service="fallback_service"
            ))
            
            # Reglas para API_FUNCTION
            self.add_routing_rule(RoutingRule(
                intent_type=IntentType.API_FUNCTION,
                priority=90,
                target_service="api_service",
                conditions={"requires_authentication": True},
                actions=["function_call", "parameter_validation"],
                fallback_service="fallback_service"
            ))
            
            # Reglas para MCP_INTEGRATION
            self.add_routing_rule(RoutingRule(
                intent_type=IntentType.MCP_INTEGRATION,
                priority=80,
                target_service="mcp_service",
                conditions={"requires_tools": True},
                actions=["tool_execution", "result_formatting"],
                fallback_service="fallback_service"
            ))
            
            # Reglas para CHAT_GENERAL
            self.add_routing_rule(RoutingRule(
                intent_type=IntentType.CHAT_GENERAL,
                priority=70,
                target_service="chat_service",
                conditions={"requires_context": True},
                actions=["conversation_flow", "response_generation"],
                fallback_service="fallback_service"
            ))
            
            # Reglas para SCHEMA_ANALYSIS
            self.add_routing_rule(RoutingRule(
                intent_type=IntentType.SCHEMA_ANALYSIS,
                priority=95,
                target_service="schema_service",
                conditions={"requires_analysis": True},
                actions=["schema_inspection", "relationship_analysis"],
                fallback_service="database_service"
            ))
            
            logger.info("[IntentRouterService] ✅ Reglas de enrutamiento por defecto inicializadas")
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error inicializando reglas por defecto: {e}")
    
    def _generate_cache_key(self, request: IntentRequest) -> str:
        """Genera clave de cache para el request"""
        # Formato: intent:{query_hash}:{user_id}:{session_id}
        query_hash = self._generate_query_hash(request.query)
        user_part = str(request.user_id) if request.user_id else "anonymous"
        session_part = request.session_id or "no_session"
        return f"intent:{query_hash}:{user_part}:{session_part}"
    
    def _generate_query_hash(self, query: str) -> str:
        """Genera hash de la consulta"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def _generate_intent_id(self, request: IntentRequest) -> str:
        """Genera ID único para la intención"""
        combined = f"{request.query}:{request.user_id}:{request.session_id}:{int(time.time())}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    async def _get_cached_intent(self, cache_key: str) -> Optional[IntentResult]:
        """Obtiene intención del cache"""
        # Cache local
        if cache_key in self._intent_cache:
            return self._intent_cache[cache_key]
        
        # Redis cache
        if self._redis_connected:
            redis_result = await self._get_from_redis(cache_key)
            if redis_result:
                # Cargar en cache local
                self._intent_cache[cache_key] = redis_result
                return redis_result
        
        return None
    
    async def _cache_intent_result(self, result: IntentResult):
        """Cachea resultado de la intención"""
        # Cache local
        cache_key = f"intent:{result.intent_id}"
        self._intent_cache[cache_key] = result
        
        # Actualizar índice
        query_hash = self._generate_query_hash(result.query)
        if query_hash not in self._query_index:
            self._query_index[query_hash] = []
        if result.intent_id not in self._query_index[query_hash]:
            self._query_index[query_hash].append(result.intent_id)
        
        # Redis cache
        if self._redis_connected:
            await self._store_in_redis(cache_key, result)
    
    async def _classify_with_model(self, request: IntentRequest) -> Tuple[IntentType, float, Dict[str, Any]]:
        """Clasifica intención usando modelo de IA"""
        try:
            if not self._classification_model_enabled:
                # Fallback sin modelo
                return IntentType.CHAT_GENERAL, 0.5, {"method": "fallback"}
            
            # Simular llamada al modelo de clasificación
            await asyncio.sleep(0.03)  # Simular latencia
            
            # Lógica de clasificación basada en palabras clave y contexto
            intent_type, confidence_score, metadata = self._classify_by_keywords(request.query, request.context)
            
            logger.debug(f"[IntentRouterService] 🤖 Modelo clasificó: {intent_type.value} (confianza: {confidence_score:.2f})")
            
            return intent_type, confidence_score, metadata
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error en modelo de clasificación: {e}")
            return IntentType.UNKNOWN, 0.0, {"error": str(e)}
    
    def _classify_by_keywords(self, query: str, context: Dict[str, Any]) -> Tuple[IntentType, float, Dict[str, Any]]:
        """Clasifica intención basándose en palabras clave"""
        query_lower = query.lower()
        
        # Palabras clave para cada tipo de intención
        db_keywords = ["select", "from", "where", "database", "table", "query", "sql", "mostrar", "obtener", "contar"]
        api_keywords = ["api", "function", "call", "execute", "endpoint", "llamar", "ejecutar", "función"]
        mcp_keywords = ["tool", "mcp", "integration", "herramienta", "integración", "plugin"]
        schema_keywords = ["schema", "structure", "columns", "relationships", "esquema", "estructura", "columnas"]
        system_keywords = ["system", "config", "settings", "status", "sistema", "configuración", "estado"]
        
        # Contar coincidencias
        scores = {
            IntentType.DB_QUERY: sum(1 for kw in db_keywords if kw in query_lower),
            IntentType.API_FUNCTION: sum(1 for kw in api_keywords if kw in query_lower),
            IntentType.MCP_INTEGRATION: sum(1 for kw in mcp_keywords if kw in query_lower),
            IntentType.SCHEMA_ANALYSIS: sum(1 for kw in schema_keywords if kw in query_lower),
            IntentType.SYSTEM_COMMAND: sum(1 for kw in system_keywords if kw in query_lower),
            IntentType.CHAT_GENERAL: 0
        }
        
        # Determinar tipo de intención
        max_score = max(scores.values())
        if max_score == 0:
            intent_type = IntentType.CHAT_GENERAL
            confidence_score = 0.3
        else:
            intent_type = max(scores, key=scores.get)
            confidence_score = min(1.0, max_score / 3.0)  # Normalizar score
        
        # Metadata adicional
        metadata = {
            "method": "keyword_classification",
            "keyword_scores": scores,
            "context_keys": list(context.keys()),
            "query_length": len(query)
        }
        
        return intent_type, confidence_score, metadata
    
    def _determine_routing_path(self, intent_type: IntentType, metadata: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Determina la ruta de enrutamiento para una intención"""
        try:
            if intent_type not in self._routing_rules:
                return "fallback", ["fallback_processing"]
            
            rules = self._routing_rules[intent_type]
            if not rules:
                return "fallback", ["fallback_processing"]
            
            # Aplicar reglas en orden de prioridad
            for rule in rules:
                if self._evaluate_rule_conditions(rule, metadata):
                    return rule.target_service, rule.actions
            
            # Si ninguna regla coincide, usar fallback de la primera regla
            first_rule = rules[0]
            return first_rule.fallback_service or "fallback", ["fallback_processing"]
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error determinando ruta: {e}")
            return "fallback", ["fallback_processing"]
    
    def _evaluate_rule_conditions(self, rule: RoutingRule, metadata: Dict[str, Any]) -> bool:
        """Evalúa si una regla de enrutamiento se cumple"""
        try:
            for condition_key, condition_value in rule.conditions.items():
                if condition_key == "requires_schema":
                    if condition_value and "schema" not in metadata.get("context_keys", []):
                        return False
                elif condition_key == "requires_authentication":
                    if condition_value and "user_id" not in metadata:
                        return False
                elif condition_key == "requires_tools":
                    if condition_value and "tools" not in metadata.get("context_keys", []):
                        return False
                elif condition_key == "requires_context":
                    if condition_value and len(metadata.get("context_keys", [])) < 2:
                        return False
                elif condition_key == "requires_analysis":
                    if condition_value and "analysis" not in metadata.get("context_keys", []):
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error evaluando condiciones: {e}")
            return False
    
    def _calculate_similarity(self, query1: str, query2: str) -> float:
        """Calcula similitud entre dos consultas"""
        try:
            words1 = set(query1.lower().split())
            words2 = set(query2.lower().split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = len(words1.intersection(words2))
            union = len(words1.union(words2))
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error calculando similitud: {e}")
            return 0.0
    
    def _update_confidence_stats(self, confidence: float):
        """Actualiza estadísticas de confianza"""
        if self._stats['avg_confidence'] == 0:
            self._stats['avg_confidence'] = confidence
        else:
            # Promedio móvil simple
            self._stats['avg_confidence'] = (
                self._stats['avg_confidence'] * 0.8 + confidence * 0.2
            )
    
    async def _get_from_redis(self, cache_key: str) -> Optional[IntentResult]:
        """Obtiene intención del cache Redis"""
        if not self._redis_cache:
            return None
        
        try:
            # Usar método específico del RedisCacheService si está disponible
            if hasattr(self._redis_cache, 'get_intent_cache'):
                redis_data = self._redis_cache.get_intent_cache(cache_key)
                if redis_data:
                    return IntentResult(**redis_data)
            else:
                # Fallback genérico
                redis_data = self._redis_cache.get(cache_key)
                if redis_data:
                    return IntentResult(**redis_data)
            
            return None
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error obteniendo de Redis: {e}")
            return None
    
    async def _store_in_redis(self, cache_key: str, result: IntentResult):
        """Almacena intención en Redis"""
        if not self._redis_cache:
            return
        
        try:
            # Preparar datos para Redis
            redis_data = asdict(result)
            
            # Usar método específico del RedisCacheService si está disponible
            if hasattr(self._redis_cache, 'set_intent_cache'):
                self._redis_cache.set_intent_cache(cache_key, redis_data, ttl=3600)  # 1 hora
            else:
                # Fallback genérico
                self._redis_cache.set(cache_key, redis_data, ttl=3600)
                
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error almacenando en Redis: {e}")
