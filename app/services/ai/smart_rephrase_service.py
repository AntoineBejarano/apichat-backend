import asyncio
import logging
import time
import hashlib
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class RephraseRequest:
    """Request de rephrase con metadatos"""
    original_query: str
    language: str
    domain: str
    context: Dict[str, Any]
    user_id: Optional[UUID] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class RephraseResult:
    """Resultado del rephrase con metadatos"""
    rephrase_id: str
    original_query: str
    normalized_query: str
    confidence_score: float
    language: str
    domain: str
    version: str
    cache_key: str
    created_at: datetime
    usage_count: int = 0
    last_used: datetime = None
    
    def __post_init__(self):
        if self.last_used is None:
            self.last_used = self.created_at


class SmartRephraseService:
    """
    Servicio de rephrase inteligente con mini-LLM y cache
    Normaliza/estandariza consultas para mejorar cache hit
    """
    
    def __init__(self):
        # Cache de rephrases
        self._rephrase_cache: Dict[str, RephraseResult] = {}
        self._query_index: Dict[str, List[str]] = {}  # original_query_hash -> [rephrase_ids]
        
        # Configuración
        self._current_version = "v1"
        self._supported_languages = ["es", "en", "auto"]
        self._supported_domains = ["general", "database", "api", "business", "technical"]
        
        # Mini-LLM (simulado por ahora)
        self._mini_llm_enabled = True
        self._confidence_threshold = 0.7
        
        # Redis cache (se configura externamente)
        self._redis_cache = None
        self._redis_connected = False
        
        # Estadísticas
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'llm_generated': 0,
            'avg_confidence': 0.0,
            'total_time_saved_ms': 0
        }
        
        logger.info("[SmartRephraseService] 🧠 Servicio de rephrase inteligente inicializado")
    
    def set_redis_cache(self, redis_cache):
        """Configura Redis cache para persistencia"""
        self._redis_cache = redis_cache
        self._redis_connected = True
        logger.info("[SmartRephraseService] 🔗 Redis cache configurado")
    
    async def rephrase_query(self, original_query: str, language: str = "auto", 
                           domain: str = "general", context: Dict[str, Any] = None,
                           user_id: Optional[UUID] = None, force_refresh: bool = False) -> RephraseResult:
        """
        Rephrase inteligente de una consulta para normalización
        
        Args:
            original_query: Consulta original del usuario
            language: Idioma de la consulta
            domain: Dominio de la consulta
            context: Contexto adicional
            user_id: ID del usuario
            force_refresh: Si forzar refresco del cache
            
        Returns:
            Resultado del rephrase con consulta normalizada
        """
        start_time = time.time()
        
        try:
            # Validar parámetros
            language = self._validate_language(language)
            domain = self._validate_domain(domain)
            context = context or {}
            
            # Crear request
            request = RephraseRequest(
                original_query=original_query,
                language=language,
                domain=domain,
                context=context,
                user_id=user_id
            )
            
            # Generar cache key
            cache_key = self._generate_cache_key(request)
            
            # Verificar cache si no se fuerza refresco
            if not force_refresh:
                cached_result = await self._get_cached_rephrase(cache_key)
                if cached_result:
                    self._stats['cache_hits'] += 1
                    cache_time = (time.time() - start_time) * 1000
                    self._stats['total_time_saved_ms'] += cache_time
                    
                    logger.debug(f"[SmartRephraseService] 🔥 Cache HIT: rephrase en {cache_time:.1f}ms")
                    return cached_result
            
            # Cache MISS - generar nuevo rephrase
            self._stats['cache_misses'] += 1
            logger.debug(f"[SmartRephraseService] ❌ Cache MISS para: {original_query[:50]}...")
            
            # Generar rephrase con mini-LLM
            normalized_query, confidence_score = await self._generate_rephrase_with_llm(request)
            
            # Crear resultado
            rephrase_result = RephraseResult(
                rephrase_id=self._generate_rephrase_id(request),
                original_query=original_query,
                normalized_query=normalized_query,
                confidence_score=confidence_score,
                language=language,
                domain=domain,
                version=self._current_version,
                cache_key=cache_key,
                created_at=datetime.now()
            )
            
            # Cachear resultado
            await self._cache_rephrase_result(rephrase_result)
            
            # Actualizar estadísticas
            self._stats['llm_generated'] += 1
            self._update_confidence_stats(confidence_score)
            
            generation_time = (time.time() - start_time) * 1000
            logger.info(f"[SmartRephraseService] ✅ Rephrase generado: {generation_time:.1f}ms (confianza: {confidence_score:.2f})")
            
            return rephrase_result
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error en rephrase: {e}")
            # Fallback: retornar query original
            return RephraseResult(
                rephrase_id=f"fallback_{int(time.time())}",
                original_query=original_query,
                normalized_query=original_query,
                confidence_score=1.0,
                language=language,
                domain=domain,
                version=self._current_version,
                cache_key="fallback",
                created_at=datetime.now()
            )
    
    async def batch_rephrase(self, queries: List[Dict[str, Any]]) -> List[RephraseResult]:
        """
        Rephrase en batch para múltiples consultas
        
        Args:
            queries: Lista de consultas con metadatos
            
        Returns:
            Lista de resultados de rephrase
        """
        start_time = time.time()
        
        try:
            results = []
            
            # Procesar consultas en paralelo
            tasks = []
            for query_data in queries:
                task = self.rephrase_query(
                    original_query=query_data['query'],
                    language=query_data.get('language', 'auto'),
                    domain=query_data.get('domain', 'general'),
                    context=query_data.get('context', {}),
                    user_id=query_data.get('user_id')
                )
                tasks.append(task)
            
            # Ejecutar en paralelo
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filtrar errores
            valid_results = []
            for result in results:
                if isinstance(result, RephraseResult):
                    valid_results.append(result)
                else:
                    logger.error(f"[SmartRephraseService] ❌ Error en batch rephrase: {result}")
            
            batch_time = (time.time() - start_time) * 1000
            logger.info(f"[SmartRephraseService] 📦 Batch completado: {len(valid_results)}/{len(queries)} en {batch_time:.1f}ms")
            
            return valid_results
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error en batch rephrase: {e}")
            return []
    
    def invalidate_cache_by_version(self, version: str):
        """Invalida cache por versión específica"""
        try:
            keys_to_remove = []
            for cache_key, result in self._rephrase_cache.items():
                if result.version == version:
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                del self._rephrase_cache[key]
            
            logger.info(f"[SmartRephraseService] 🗑️ Cache invalidado para versión {version}: {len(keys_to_remove)} entradas")
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error invalidando cache: {e}")
    
    def invalidate_cache_by_domain(self, domain: str):
        """Invalida cache por dominio específico"""
        try:
            keys_to_remove = []
            for cache_key, result in self._rephrase_cache.items():
                if result.domain == domain:
                    keys_to_remove.append(cache_key)
            
            for key in keys_to_remove:
                del self._rephrase_cache[key]
            
            logger.info(f"[SmartRephraseService] 🗑️ Cache invalidado para dominio {domain}: {len(keys_to_remove)} entradas")
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error invalidando cache: {e}")
    
    def get_similar_rephrases(self, query: str, limit: int = 5) -> List[Tuple[RephraseResult, float]]:
        """Obtiene rephrases similares para una consulta"""
        try:
            similar_results = []
            query_hash = self._generate_query_hash(query)
            
            # Buscar en índice
            if query_hash in self._query_index:
                for rephrase_id in self._query_index[query_hash]:
                    if rephrase_id in self._rephrase_cache:
                        result = self._rephrase_cache[rephrase_id]
                        similarity = self._calculate_similarity(query, result.original_query)
                        if similarity > 0.6:  # Umbral de similitud
                            similar_results.append((result, similarity))
            
            # Ordenar por similitud
            similar_results.sort(key=lambda x: x[1], reverse=True)
            return similar_results[:limit]
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error obteniendo rephrases similares: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        return {
            **self._stats,
            'cached_rephrases': len(self._rephrase_cache),
            'query_index_size': len(self._query_index),
            'cache_hit_rate': f"{self._stats['cache_hits'] / max(1, self._stats['cache_hits'] + self._stats['cache_misses']) * 100:.1f}%",
            'current_version': self._current_version,
            'supported_languages': self._supported_languages,
            'supported_domains': self._supported_domains
        }
    
    # ==================== MÉTODOS PRIVADOS ====================
    
    def _validate_language(self, language: str) -> str:
        """Valida y normaliza el idioma"""
        if language not in self._supported_languages:
            return "auto"
        return language
    
    def _validate_domain(self, domain: str) -> str:
        """Valida y normaliza el dominio"""
        if domain not in self._supported_domains:
            return "general"
        return domain
    
    def _generate_cache_key(self, request: RephraseRequest) -> str:
        """Genera clave de cache para el request"""
        # Formato: rephrase_v{n}:{lang}:{domain}:{query_hash}
        query_hash = self._generate_query_hash(request.original_query)
        return f"rephrase_{self._current_version}:{request.language}:{request.domain}:{query_hash}"
    
    def _generate_query_hash(self, query: str) -> str:
        """Genera hash de la consulta"""
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def _generate_rephrase_id(self, request: RephraseRequest) -> str:
        """Genera ID único para el rephrase"""
        combined = f"{request.original_query}:{request.language}:{request.domain}:{int(time.time())}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()
    
    async def _get_cached_rephrase(self, cache_key: str) -> Optional[RephraseResult]:
        """Obtiene rephrase del cache"""
        # Cache local
        if cache_key in self._rephrase_cache:
            result = self._rephrase_cache[cache_key]
            result.usage_count += 1
            result.last_used = datetime.now()
            return result
        
        # Redis cache
        if self._redis_connected:
            redis_result = await self._get_from_redis(cache_key)
            if redis_result:
                # Cargar en cache local
                self._rephrase_cache[cache_key] = redis_result
                return redis_result
        
        return None
    
    async def _cache_rephrase_result(self, result: RephraseResult):
        """Cachea resultado del rephrase"""
        # Cache local
        self._rephrase_cache[result.cache_key] = result
        
        # Actualizar índice
        query_hash = self._generate_query_hash(result.original_query)
        if query_hash not in self._query_index:
            self._query_index[query_hash] = []
        if result.rephrase_id not in self._query_index[query_hash]:
            self._query_index[query_hash].append(result.rephrase_id)
        
        # Redis cache
        if self._redis_connected:
            await self._store_in_redis(result)
    
    async def _generate_rephrase_with_llm(self, request: RephraseRequest) -> Tuple[str, float]:
        """Genera rephrase usando mini-LLM"""
        try:
            if not self._mini_llm_enabled:
                # Fallback sin LLM
                return request.original_query, 1.0
            
            # Simular llamada a mini-LLM
            await asyncio.sleep(0.05)  # Simular latencia
            
            # Lógica de rephrase basada en reglas y contexto
            normalized_query = self._apply_rephrase_rules(request.original_query, request.language, request.domain)
            
            # Calcular confianza basada en similitud y reglas aplicadas
            confidence_score = self._calculate_confidence(request.original_query, normalized_query, request.domain)
            
            logger.debug(f"[SmartRephraseService] 🤖 LLM generó rephrase: {normalized_query[:50]}... (confianza: {confidence_score:.2f})")
            
            return normalized_query, confidence_score
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error en LLM: {e}")
            return request.original_query, 0.5
    
    def _apply_rephrase_rules(self, query: str, language: str, domain: str) -> str:
        """Aplica reglas de rephrase basadas en dominio e idioma"""
        normalized = query.strip()
        
        # Normalización básica
        normalized = normalized.lower()
        
        # Reglas específicas por dominio
        if domain == "database":
            # Normalizar términos de base de datos
            db_terms = {
                "mostrar": "select", "seleccionar": "select", "obtener": "select",
                "contar": "count", "cuenta": "count", "número": "count",
                "usuarios": "users", "clubes": "clubs", "invitaciones": "invitations"
            }
            for es_term, en_term in db_terms.items():
                normalized = normalized.replace(es_term, en_term)
        
        elif domain == "api":
            # Normalizar términos de API
            api_terms = {
                "llamar": "call", "ejecutar": "execute", "obtener": "get",
                "crear": "create", "actualizar": "update", "eliminar": "delete"
            }
            for es_term, en_term in api_terms.items():
                normalized = normalized.replace(es_term, en_term)
        
        # Normalización de idioma
        if language == "es":
            # Mantener español pero normalizar
            pass
        elif language == "en":
            # Asegurar inglés
            pass
        else:  # auto
            # Detectar y normalizar automáticamente
            pass
        
        return normalized
    
    def _calculate_confidence(self, original: str, normalized: str, domain: str) -> float:
        """Calcula score de confianza del rephrase"""
        try:
            # Similitud básica
            similarity = self._calculate_similarity(original, normalized)
            
            # Bonus por dominio específico
            domain_bonus = 0.1 if domain != "general" else 0.0
            
            # Bonus por normalización efectiva
            normalization_bonus = 0.1 if original.lower() != normalized else 0.0
            
            confidence = min(1.0, similarity + domain_bonus + normalization_bonus)
            
            return max(0.0, confidence)
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error calculando confianza: {e}")
            return 0.5
    
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
            logger.error(f"[SmartRephraseService] ❌ Error calculando similitud: {e}")
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
    
    async def _get_from_redis(self, cache_key: str) -> Optional[RephraseResult]:
        """Obtiene rephrase del cache Redis"""
        if not self._redis_cache:
            return None
        
        try:
            # Usar método específico del RedisCacheService si está disponible
            if hasattr(self._redis_cache, 'get_rephrase_cache'):
                redis_data = self._redis_cache.get_rephrase_cache(cache_key)
                if redis_data:
                    return RephraseResult(**redis_data)
            else:
                # Fallback genérico
                redis_data = self._redis_cache.get(cache_key)
                if redis_data:
                    return RephraseResult(**redis_data)
            
            return None
            
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error obteniendo de Redis: {e}")
            return None
    
    async def _store_in_redis(self, result: RephraseResult):
        """Almacena rephrase en Redis"""
        if not self._redis_cache:
            return
        
        try:
            # Preparar datos para Redis
            redis_data = asdict(result)
            
            # Usar método específico del RedisCacheService si está disponible
            if hasattr(self._redis_cache, 'set_rephrase_cache'):
                self._redis_cache.set_rephrase_cache(result.cache_key, redis_data, ttl=86400)  # 24 horas
            else:
                # Fallback genérico
                self._redis_cache.set(result.cache_key, redis_data, ttl=86400)
                
        except Exception as e:
            logger.error(f"[SmartRephraseService] ❌ Error almacenando en Redis: {e}")
