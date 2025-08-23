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
    """Tipos de intenciones soportadas - Optimizado"""
    DB_QUERY = "db_query"                    # 🔍 Consultas de base de datos
    API_FUNCTION = "api_function"            # 🚀 APIs + MCP + Funciones (unificado)
    CHAT_GENERAL = "chat_general"            # 💬 Conversación general
    SCHEMA_ANALYSIS = "schema_analysis"      # 📊 Análisis de esquemas
    SYSTEM_COMMAND = "system_command"        # ⚙️ Comandos del sistema
    UNKNOWN = "unknown"                      # ❓ Intención no determinada


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
    """Resultado de clasificación de intención"""
    intent_id: str
    query: str
    intent_type: IntentType
    confidence_score: float
    routing_path: str
    suggested_actions: List[str]
    metadata: Dict[str, Any]
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
    Clasifica en: db_query | api_function | chat_general | schema_analysis | system_command
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
        
        logger.info("[IntentRouterService] 🧠 Servicio de clasificación de intenciones optimizado inicializado")

    def set_redis_cache(self, redis_cache):
        """Configura Redis cache para persistencia"""
        self._redis_cache = redis_cache
        self._redis_connected = True
        logger.info("[IntentRouterService] 🔗 Redis cache configurado")

    async def classify_intent(self, query: str, context: Dict[str, Any] = None,
                             user_id: Optional[UUID] = None, session_id: Optional[str] = None,
                             force_refresh: bool = False) -> IntentResult:
        """
        Clasifica la intención de una consulta del usuario
        
        Args:
            query: Consulta del usuario
            context: Contexto adicional
            user_id: ID del usuario
            session_id: ID de sesión
            force_refresh: Forzar refresco del cache
            
        Returns:
            IntentResult con la clasificación
        """
        start_time = time.time()
        
        try:
            # Validar parámetros
            if not query or not isinstance(query, str):
                raise ValueError("Query debe ser un string no vacío")
            
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
            
            # Clasificar con modelo o palabras clave
            if self._classification_model_enabled:
                intent_type, confidence_score, metadata = await self._classify_with_model(request)
            else:
                intent_type, confidence_score, metadata = self._classify_by_keywords(query, context)
            
            # Determinar ruta de enrutamiento
            routing_path, suggested_actions = self._determine_routing_path(intent_type, metadata)
            
            # Crear resultado
            intent_result = IntentResult(
                intent_id=self._generate_intent_id(request),
                query=query,
                intent_type=intent_type,
                confidence_score=confidence_score,
                routing_path=routing_path,
                suggested_actions=suggested_actions,
                metadata=metadata,
                created_at=datetime.now(),
                processing_time_ms=(time.time() - start_time) * 1000
            )
            
            # Cachear resultado
            await self._cache_intent_result(intent_result)
            
            # Actualizar estadísticas
            self._stats['total_requests'] += 1
            self._stats['classifications'] += 1
            self._stats['routing_decisions'] += 1
            
            # Calcular promedio de confianza
            total_confidence = self._stats['avg_confidence'] * (self._stats['classifications'] - 1) + confidence_score
            self._stats['avg_confidence'] = total_confidence / self._stats['classifications']
            
            logger.info(f"[IntentRouterService] 🎯 Intención clasificada: {intent_type.value} (confianza: {confidence_score:.2f})")
            
            return intent_result
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"[IntentRouterService] ❌ Error clasificando intención ({processing_time:.1f}ms): {e}")
            
            # Retornar resultado de fallback
            return IntentResult(
                intent_id=f"fallback_{int(time.time())}",
                query=query,
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                routing_path="fallback_service",
                suggested_actions=["clarification_request"],
                metadata={"error": str(e), "fallback": True},
                created_at=datetime.now(),
                processing_time_ms=processing_time
            )

    def _generate_cache_key(self, request: IntentRequest) -> str:
        """Genera clave de cache única para la request"""
        # Crear string combinado para hash
        combined = f"{request.query}:{request.user_id}:{request.session_id}:{json.dumps(request.context, sort_keys=True)}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

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
        """Clasifica intención usando modelo de ML (simulado por ahora)"""
        try:
            # Por ahora, usar clasificación por palabras clave
            # En el futuro, aquí se integraría un modelo real
            return self._classify_by_keywords(request.query, request.context)
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error en clasificación con modelo: {e}")
            return IntentType.UNKNOWN, 0.0, {"error": str(e)}

    def _classify_by_keywords(self, query: str, context: Dict[str, Any]) -> Tuple[IntentType, float, Dict[str, Any]]:
        """Clasifica intención basándose en palabras clave optimizadas"""
        query_lower = query.lower()
        
        # Palabras clave optimizadas para cada tipo de intención
        db_keywords = ["select", "from", "where", "database", "table", "query", "sql", "mostrar", "obtener", "contar", "cuántos", "cuántas"]
        api_keywords = ["api", "function", "call", "execute", "endpoint", "llamar", "ejecutar", "función", "mcp", "tool", "herramienta", "integración", "plugin"]
        schema_keywords = ["schema", "structure", "columns", "relationships", "esquema", "estructura", "columnas", "relaciones", "constraints"]
        system_keywords = ["system", "config", "settings", "status", "sistema", "configuración", "estado", "ajustes", "parámetros"]
        
        # Contar coincidencias
        scores = {
            IntentType.DB_QUERY: sum(1 for kw in db_keywords if kw in query_lower),
            IntentType.API_FUNCTION: sum(1 for kw in api_keywords if kw in query_lower),
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
        
        # Metadata adicional con información específica del tipo
        metadata = {
            "method": "keyword_classification",
            "keyword_scores": scores,
            "context_keys": list(context.keys()),
            "query_length": len(query)
        }
        
        # Añadir metadata específica para API_FUNCTION (MCP, REST, etc.)
        if intent_type == IntentType.API_FUNCTION:
            metadata.update(self._detect_api_type(query_lower))
        
        return intent_type, confidence_score, metadata

    def _detect_api_type(self, query_lower: str) -> Dict[str, Any]:
        """Detecta el tipo específico de API (MCP, REST, GraphQL, etc.)"""
        api_metadata = {
            "api_type": "general",
            "tool_category": None,
            "protocol": None
        }
        
        # Detectar MCP
        if any(word in query_lower for word in ["mcp", "tool", "herramienta"]):
            api_metadata["api_type"] = "mcp"
            api_metadata["protocol"] = "mcp_v1"
            
            # Detectar categoría de herramienta
            if "calendario" in query_lower or "calendar" in query_lower:
                api_metadata["tool_category"] = "calendar"
            elif "archivo" in query_lower or "file" in query_lower:
                api_metadata["tool_category"] = "file_system"
            elif "web" in query_lower or "navegador" in query_lower:
                api_metadata["tool_category"] = "web_browser"
            elif "terminal" in query_lower or "comando" in query_lower:
                api_metadata["tool_category"] = "terminal"
        
        # Detectar REST API
        elif any(word in query_lower for word in ["rest", "http", "endpoint", "url"]):
            api_metadata["api_type"] = "rest"
            api_metadata["protocol"] = "http"
        
        # Detectar GraphQL
        elif "graphql" in query_lower:
            api_metadata["api_type"] = "graphql"
            api_metadata["protocol"] = "graphql"
        
        return api_metadata

    def _determine_routing_path(self, intent_type: IntentType, metadata: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Determina la ruta de enrutamiento y acciones sugeridas"""
        try:
            # Obtener reglas para el tipo de intención
            rules = self._routing_rules.get(intent_type, [])
            
            if not rules:
                # Fallback si no hay reglas específicas
                return self._get_fallback_routing(intent_type)
            
            # Ordenar reglas por prioridad (mayor primero)
            sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)
            
            # Buscar la primera regla que cumpla las condiciones
            for rule in sorted_rules:
                if self._evaluate_conditions(rule.conditions, metadata):
                    return rule.target_service, rule.actions
            
            # Si ninguna regla cumple las condiciones, usar la primera
            first_rule = sorted_rules[0]
            return first_rule.target_service, first_rule.actions
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error determinando ruta: {e}")
            return "fallback_service", ["error_handling"]

    def _get_fallback_routing(self, intent_type: IntentType) -> Tuple[str, List[str]]:
        """Obtiene enrutamiento de fallback para un tipo de intención"""
        fallback_routes = {
            IntentType.DB_QUERY: ("database_service", ["query_execution"]),
            IntentType.API_FUNCTION: ("function_service", ["function_execution"]),
            IntentType.CHAT_GENERAL: ("chat_service", ["conversation_flow"]),
            IntentType.SCHEMA_ANALYSIS: ("schema_service", ["schema_exploration"]),
            IntentType.SYSTEM_COMMAND: ("system_service", ["command_execution"]),
            IntentType.UNKNOWN: ("fallback_service", ["clarification_request"])
        }
        
        return fallback_routes.get(intent_type, ("fallback_service", ["error_handling"]))

    def _evaluate_conditions(self, conditions: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
        """Evalúa si se cumplen las condiciones de una regla"""
        try:
            for key, expected_value in conditions.items():
                if key not in metadata:
                    return False
                
                actual_value = metadata[key]
                
                # Comparación simple por ahora
                if actual_value != expected_value:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"[IntentRouterService] ❌ Error evaluando condiciones: {e}")
            return False

    def _initialize_default_routing_rules(self):
        """Inicializa reglas de enrutamiento por defecto optimizadas"""
        self._routing_rules = {
            IntentType.DB_QUERY: [
                RoutingRule(
                    intent_type=IntentType.DB_QUERY,
                    priority=100,
                    target_service="database_service",
                    conditions={"requires_schema": True},
                    actions=["query_execution", "schema_validation"],
                    fallback_service="fallback_service"
                )
            ],
            
            IntentType.API_FUNCTION: [
                # Regla para MCP
                RoutingRule(
                    intent_type=IntentType.API_FUNCTION,
                    priority=90,
                    target_service="mcp_service",
                    conditions={"api_type": "mcp"},
                    actions=["tool_discovery", "integration_setup"],
                    fallback_service="function_service"
                ),
                # Regla para funciones API generales
                RoutingRule(
                    intent_type=IntentType.API_FUNCTION,
                    priority=80,
                    target_service="function_service",
                    conditions={},
                    actions=["function_execution", "parameter_validation"],
                    fallback_service="fallback_service"
                )
            ],
            
            IntentType.SCHEMA_ANALYSIS: [
                RoutingRule(
                    intent_type=IntentType.SCHEMA_ANALYSIS,
                    priority=85,
                    target_service="schema_service",
                    conditions={},
                    actions=["schema_exploration", "relationship_mapping"],
                    fallback_service="database_service"
                )
            ],
            
            IntentType.SYSTEM_COMMAND: [
                RoutingRule(
                    intent_type=IntentType.SYSTEM_COMMAND,
                    priority=95,
                    target_service="system_service",
                    conditions={},
                    actions=["configuration_update", "system_status"],
                    fallback_service="fallback_service"
                )
            ],
            
            IntentType.CHAT_GENERAL: [
                RoutingRule(
                    intent_type=IntentType.CHAT_GENERAL,
                    priority=50,
                    target_service="chat_service",
                    conditions={},
                    actions=["conversation_flow", "context_management"],
                    fallback_service="fallback_service"
                )
            ]
        }
        
        logger.info("[IntentRouterService] ✅ Reglas de enrutamiento optimizadas inicializadas")

    def _generate_query_hash(self, query: str) -> str:
        """Genera hash de la query para indexación"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    async def _get_from_redis(self, cache_key: str) -> Optional[IntentResult]:
        """Obtiene resultado desde Redis"""
        try:
            if not self._redis_cache:
                return None
            
            # Intentar obtener desde Redis
            redis_data = await self._redis_cache.get(cache_key)
            if redis_data:
                # Convertir de vuelta a IntentResult
                return IntentResult(**json.loads(redis_data))
            
            return None
            
        except Exception as e:
            logger.warning(f"[IntentRouterService] ⚠️ Error obteniendo desde Redis: {e}")
            return None

    async def _store_in_redis(self, cache_key: str, result: IntentResult):
        """Almacena resultado en Redis"""
        try:
            if not self._redis_cache:
                return
            
            # Convertir a JSON para almacenar en Redis
            result_dict = asdict(result)
            result_dict['created_at'] = result_dict['created_at'].isoformat()
            
            # Almacenar en Redis con TTL
            await self._redis_cache.set(cache_key, json.dumps(result_dict), ttl=3600)  # 1 hora
            
        except Exception as e:
            logger.warning(f"[IntentRouterService] ⚠️ Error almacenando en Redis: {e}")

    def add_routing_rule(self, rule: RoutingRule):
        """Añade una nueva regla de enrutamiento"""
        if rule.intent_type not in self._routing_rules:
            self._routing_rules[rule.intent_type] = []
        
        self._routing_rules[rule.intent_type].append(rule)
        logger.info(f"[IntentRouterService] ✅ Regla añadida para {rule.intent_type.value}")

    def remove_routing_rule(self, intent_type: IntentType, target_service: str):
        """Elimina una regla de enrutamiento"""
        if intent_type in self._routing_rules:
            self._routing_rules[intent_type] = [
                rule for rule in self._routing_rules[intent_type]
                if rule.target_service != target_service
            ]
            logger.info(f"[IntentRouterService] ✅ Regla eliminada para {intent_type.value} -> {target_service}")

    def get_routing_rules(self, intent_type: IntentType = None) -> Dict[IntentType, List[RoutingRule]]:
        """Obtiene reglas de enrutamiento"""
        if intent_type:
            return {intent_type: self._routing_rules.get(intent_type, [])}
        return self._routing_rules.copy()

    def get_intent_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del servicio"""
        return {
            'total_requests': self._stats['total_requests'],
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': f"{(self._stats['cache_hits'] / max(1, self._stats['total_requests'])) * 100:.1f}%",
            'classifications': self._stats['classifications'],
            'routing_decisions': self._stats['routing_decisions'],
            'avg_confidence': f"{self._stats['avg_confidence']:.2f}",
            'total_time_saved_ms': self._stats['total_time_saved_ms'],
            'query_index_size': len(self._query_index),
            'cached_intents': len(self._intent_cache)
        }

    def clear_cache(self):
        """Limpia el cache local"""
        self._intent_cache.clear()
        self._query_index.clear()
        logger.info("[IntentRouterService] 🧹 Cache local limpiado")

    def get_supported_intent_types(self) -> List[str]:
        """Obtiene lista de tipos de intención soportados"""
        return [intent_type.value for intent_type in IntentType]

    def get_intent_type_description(self, intent_type: IntentType) -> str:
        """Obtiene descripción de un tipo de intención"""
        descriptions = {
            IntentType.DB_QUERY: "Consultas de base de datos (SELECT, COUNT, etc.)",
            IntentType.API_FUNCTION: "Llamadas a APIs, funciones y herramientas MCP",
            IntentType.CHAT_GENERAL: "Conversación general y preguntas conceptuales",
            IntentType.SCHEMA_ANALYSIS: "Análisis de estructura y esquemas de BD",
            IntentType.SYSTEM_COMMAND: "Comandos de configuración y estado del sistema",
            IntentType.UNKNOWN: "Intención no determinada o ambigua"
        }
        return descriptions.get(intent_type, "Tipo de intención no documentado")
