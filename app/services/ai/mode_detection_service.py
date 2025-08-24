"""
🎯 Mode Detection Service: Detección automática de modo del usuario

Sistema inteligente que analiza el mensaje del usuario y el contexto para determinar
automáticamente si quiere explorar recursos (Explorer) o ejecutar acciones (Guided).
"""

import logging
import re
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from enum import Enum
import time

from app.services.ai.agent_router_service import AgentMode
from app.services.data.database_service import DatabaseService
from app.services.management.app_service import AppService

logger = logging.getLogger(__name__)


class DetectionConfidence(Enum):
    """Niveles de confianza en la detección"""
    HIGH = "high"      # >0.8
    MEDIUM = "medium"  # 0.5-0.8
    LOW = "low"        # <0.5
    AMBIGUOUS = "ambiguous"  # Necesita confirmación


class ModeDetectionService:
    """
    🎯 Servicio de detección automática de modo
    
    Funcionalidades:
    - Análisis de intención con NLP básico
    - Análisis de recursos disponibles
    - Cálculo de ambigüedad
    - Cache de decisiones para performance
    - Fallback inteligente
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.database_service = factory.get_database_service()
        self.app_service = factory.get_app_service()
        
        # Cache de decisiones para performance
        self._detection_cache = {}
        self._cache_ttl = 3600  # 1 hora
        
        # Patrones de detección
        self._explorer_patterns = self._init_explorer_patterns()
        self._guided_patterns = self._init_guided_patterns()
        self._transition_patterns = self._init_transition_patterns()
        
        logger.info(f"[ModeDetectionService] 🚀 Inicializado para usuario {self.user_id}")
    
    def _init_explorer_patterns(self) -> Dict[str, List[str]]:
        """Inicializa patrones para modo Explorer"""
        return {
            "exploration_keywords": [
                "qué", "que", "cuales", "cuáles", "muestra", "muéstrame", "explora", "explorar",
                "descubre", "descubrir", "encuentra", "encontrar", "busca", "buscar",
                "lista", "listar", "overview", "resumen", "summary", "qué hay", "que hay"
            ],
            "resource_questions": [
                "bases de datos", "databases", "apps", "aplicaciones", "recursos", "resources",
                "qué puedo hacer", "que puedo hacer", "opciones", "alternativas"
            ],
            "general_inquiry": [
                "hola", "hello", "ayuda", "help", "información", "information",
                "cómo funciona", "como funciona", "tutorial", "guía", "guia"
            ]
        }
    
    def _init_guided_patterns(self) -> Dict[str, List[str]]:
        """Inicializa patrones para modo Guided"""
        return {
            "action_keywords": [
                "ejecuta", "ejecutar", "execute", "run", "corre", "correr",
                "analiza", "analizar", "analyze", "crea", "crear", "create",
                "modifica", "modificar", "modify", "elimina", "eliminar", "delete",
                "inserta", "insertar", "insert", "actualiza", "actualizar", "update"
            ],
            "specific_requests": [
                "en la base de datos", "in the database", "en la app", "in the app",
                "con estos datos", "with this data", "usando", "using",
                "para", "for", "desde", "from", "hasta", "to"
            ],
            "sql_related": [
                "sql", "query", "consulta", "select", "insert", "update", "delete",
                "where", "join", "group by", "order by", "having"
            ]
        }
    
    def _init_transition_patterns(self) -> Dict[str, List[str]]:
        """Inicializa patrones para transiciones de modo"""
        return {
            "explorer_to_guided": [
                "selecciona", "seleccionar", "select", "elige", "elegir", "choose",
                "usa", "usar", "use", "aplica", "aplicar", "apply", "conecta", "conectar"
            ],
            "guided_to_explorer": [
                "explora", "explorar", "explore", "qué más", "que mas", "what else",
                "otras opciones", "other options", "cambia", "cambiar", "change"
            ]
        }
    

    
    def _analyze_intent(self, user_message: str) -> Dict[str, float]:
        """Analiza la intención del mensaje del usuario"""
        try:
            message_lower = user_message.lower().strip()
            
            # Puntuación para modo Explorer
            explorer_score = 0.0
            for category, patterns in self._explorer_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in message_lower:
                        if category == "exploration_keywords":
                            explorer_score += 0.3
                        elif category == "resource_questions":
                            explorer_score += 0.4
                        elif category == "general_inquiry":
                            explorer_score += 0.2
            
            # Puntuación para modo Guided
            guided_score = 0.0
            for category, patterns in self._guided_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in message_lower:
                        if category == "action_keywords":
                            guided_score += 0.4
                        elif category == "specific_requests":
                            guided_score += 0.3
                        elif category == "sql_related":
                            guided_score += 0.3
            
            # Normalizar puntuaciones
            explorer_score = min(explorer_score, 1.0)
            guided_score = min(guided_score, 1.0)
            
            # Detectar transiciones
            transition_detected = self._detect_transition_intent(message_lower)
            
            return {
                "explorer_score": explorer_score,
                "guided_score": guided_score,
                "transition_detected": transition_detected,
                "message_complexity": self._calculate_message_complexity(user_message)
            }
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error analizando intención: {e}")
            return {
                "explorer_score": 0.0,
                "guided_score": 0.0,
                "transition_detected": None,
                "message_complexity": 0.0
            }
    
    async def _analyze_resources(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Analiza los recursos disponibles en el contexto"""
        try:
            resource_score = {
                "databases_available": 0.0,
                "apps_available": 0.0,
                "resources_selected": 0.0,
                "context_richness": 0.0
            }
            
            # Verificar bases de datos disponibles
            if self.database_service:
                try:
                    user_dbs = await self.database_service.get_user_databases(self.user_id)
                    resource_score["databases_available"] = min(len(user_dbs) * 0.2, 1.0)
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ Error obteniendo DBs: {e}")
            
            # Verificar aplicaciones disponibles
            if self.app_service:
                try:
                    user_apps = await self.app_service.get_user_apps(self.user_id)
                    resource_score["apps_available"] = min(len(user_apps) * 0.2, 1.0)
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ Error obteniendo apps: {e}")
            
            # Verificar recursos seleccionados en contexto
            db_ids = context.get("db_ids", [])
            app_ids = context.get("app_ids", [])
            if db_ids or app_ids:
                resource_score["resources_selected"] = 0.8
            
            # Calcular riqueza del contexto
            context_keys = len([k for k, v in context.items() if v])
            resource_score["context_richness"] = min(context_keys * 0.1, 1.0)
            
            return resource_score
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error analizando recursos: {e}")
            return {
                "databases_available": 0.0,
                "apps_available": 0.0,
                "resources_selected": 0.0,
                "context_richness": 0.0
            }
    
    async def _analyze_historical_context(
        self, 
        chat_id: Optional[UUID], 
        context: Dict[str, Any]
    ) -> Dict[str, float]:
        """Analiza el contexto histórico del chat"""
        try:
            historical_score = {
                "previous_mode": 0.0,
                "conversation_length": 0.0,
                "mode_consistency": 0.0
            }
            
            # TODO: Implementar análisis de historial del chat
            # Por ahora, valores por defecto
            historical_score["previous_mode"] = 0.5
            historical_score["conversation_length"] = 0.3
            historical_score["mode_consistency"] = 0.7
            
            return historical_score
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error analizando contexto histórico: {e}")
            return {
                "previous_mode": 0.0,
                "conversation_length": 0.0,
                "mode_consistency": 0.0
            }
    
    def _calculate_ambiguity(
        self, 
        intent_score: Dict[str, float], 
        resource_score: Dict[str, float],
        historical_score: Dict[str, float]
    ) -> float:
        """Calcula el nivel de ambigüedad en la detección"""
        try:
            # Diferencia entre puntuaciones de modo
            mode_difference = abs(
                intent_score.get("explorer_score", 0.0) - 
                intent_score.get("guided_score", 0.0)
            )
            
            # Si la diferencia es pequeña, hay ambigüedad
            if mode_difference < 0.2:
                return 0.8  # Alta ambigüedad
            elif mode_difference < 0.4:
                return 0.5  # Media ambigüedad
            else:
                return 0.1  # Baja ambigüedad
                
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error calculando ambigüedad: {e}")
            return 0.5  # Ambigüedad media por defecto
    
    def _make_decision(
        self,
        intent_score: Dict[str, float],
        resource_score: Dict[str, Any],
        historical_score: Dict[str, float],
        ambiguity_score: float,
        user_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Toma la decisión final sobre el modo"""
        try:
            explorer_score = intent_score.get("explorer_score", 0.0)
            guided_score = intent_score.get("guided_score", 0.0)
            
            # Factor de recursos seleccionados
            if resource_score.get("resources_selected", 0.0) > 0.5:
                guided_score += 0.3
            
            # Factor de transición detectada
            transition = intent_score.get("transition_detected")
            if transition:
                if transition == "explorer_to_guided":
                    guided_score += 0.4
                elif transition == "guided_to_explorer":
                    explorer_score += 0.4
            
            # Decisión final
            if ambiguity_score > 0.7:
                detected_mode = "ambiguous"
                confidence_score = 0.3
                needs_confirmation = True
            elif explorer_score > guided_score:
                detected_mode = "explorer"
                confidence_score = min(explorer_score, 0.95)
                needs_confirmation = False
            elif guided_score > explorer_score:
                detected_mode = "guided"
                confidence_score = min(guided_score, 0.95)
                needs_confirmation = False
            else:
                detected_mode = "auto"
                confidence_score = 0.5
                needs_confirmation = True
            
            # Determinar nivel de confianza
            if confidence_score > 0.8:
                confidence_level = DetectionConfidence.HIGH
            elif confidence_score > 0.5:
                confidence_level = DetectionConfidence.MEDIUM
            else:
                confidence_level = DetectionConfidence.LOW
            
            return {
                "detected_mode": detected_mode,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level.value,
                "needs_confirmation": needs_confirmation,
                "detection_metadata": {
                    "intent_scores": intent_score,
                    "resource_scores": resource_score,
                    "historical_scores": historical_score,
                    "ambiguity_score": ambiguity_score,
                    "message_hash": self._hash_message(user_message),
                    "execution_time_ms": 0  # Se actualiza después
                },
                "fallback_used": False,
                "context": context
            }
            
        except Exception as e:
            logger.error(f"[ModeDetectionService] ❌ Error en decisión final: {e}")
            return self._build_fallback_result(user_message, context, str(e))
    
    def _detect_transition_intent(self, message_lower: str) -> Optional[str]:
        """Detecta si el usuario quiere cambiar de modo"""
        try:
            # Explorer → Guided
            for pattern in self._transition_patterns["explorer_to_guided"]:
                if pattern.lower() in message_lower:
                    return "explorer_to_guided"
            
            # Guided → Explorer
            for pattern in self._transition_patterns["guided_to_explorer"]:
                if pattern.lower() in message_lower:
                    return "guided_to_explorer"
            
            return None
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error detectando transición: {e}")
            return None
    
    def _calculate_message_complexity(self, message: str) -> float:
        """Calcula la complejidad del mensaje"""
        try:
            # Contar palabras
            word_count = len(message.split())
            
            # Contar caracteres especiales
            special_chars = len(re.findall(r'[^a-zA-Z0-9\s]', message))
            
            # Contar números
            numbers = len(re.findall(r'\d+', message))
            
            # Calcular complejidad
            complexity = (word_count * 0.1) + (special_chars * 0.05) + (numbers * 0.1)
            
            return min(complexity, 1.0)
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error calculando complejidad: {e}")
            return 0.5
    
    def _generate_cache_key(self, user_message: str, context: Dict[str, Any]) -> str:
        """Genera una clave única para el cache"""
        try:
            # Hash del mensaje + contexto relevante
            context_str = str(sorted(context.items()))
            combined = f"{user_message}:{context_str}"
            return hashlib.md5(combined.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error generando cache key: {e}")
            return hashlib.md5(user_message.encode()).hexdigest()
    
    def _get_cached_detection(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obtiene resultado desde cache si está disponible"""
        try:
            if cache_key in self._detection_cache:
                cached_item = self._detection_cache[cache_key]
                if time.time() - cached_item["timestamp"] < self._cache_ttl:
                    return cached_item["result"]
                else:
                    # Expiró, eliminar del cache
                    del self._detection_cache[cache_key]
            return None
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error obteniendo cache: {e}")
            return None
    
    def _cache_detection(self, cache_key: str, result: Dict[str, Any]):
        """Cachea el resultado de la detección"""
        try:
            self._detection_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            # Limpiar cache si es muy grande
            if len(self._detection_cache) > 1000:
                self._cleanup_cache()
                
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error cacheando resultado: {e}")
    
    def _cleanup_cache(self):
        """Limpia el cache expirado"""
        try:
            current_time = time.time()
            expired_keys = [
                key for key, item in self._detection_cache.items()
                if current_time - item["timestamp"] > self._cache_ttl
            ]
            
            for key in expired_keys:
                del self._detection_cache[key]
                
            logger.info(f"[ModeDetectionService] 🧹 Cache limpiado: {len(expired_keys)} entradas expiradas")
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error limpiando cache: {e}")
    
    def _hash_message(self, message: str) -> str:
        """Genera hash del mensaje para deduplicación"""
        try:
            return hashlib.sha256(message.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error generando hash: {e}")
            return ""
    
    def _build_fallback_result(
        self, 
        user_message: str, 
        context: Dict[str, Any], 
        error: str
    ) -> Dict[str, Any]:
        """Construye resultado de fallback cuando hay error"""
        return {
            "detected_mode": "auto",
            "confidence_score": 0.1,
            "confidence_level": DetectionConfidence.LOW.value,
            "needs_confirmation": True,
            "detection_metadata": {
                "intent_scores": {"explorer_score": 0.0, "guided_score": 0.0},
                "resource_scores": {},
                "historical_scores": {},
                "ambiguity_score": 0.9,
                "message_hash": self._hash_message(user_message),
                "execution_time_ms": 0,
                "error": error
            },
            "fallback_used": True,
            "context": context
        }
    
    async def get_detection_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de detección"""
        try:
            return {
                "cache_size": len(self._detection_cache),
                "cache_ttl_seconds": self._cache_ttl,
                "patterns_loaded": {
                    "explorer": len(self._explorer_patterns),
                    "guided": len(self._guided_patterns),
                    "transition": len(self._transition_patterns)
                },
                "user_id": str(self.user_id)
            }
        except Exception as e:
            logger.error(f"[ModeDetectionService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def clear_cache(self):
        """Limpia el cache de detección"""
        try:
            self._detection_cache.clear()
            logger.info("[ModeDetectionService] 🧹 Cache de detección limpiado")
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error limpiando cache: {e}")
    
    async def detect_mode(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        force_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        🎯 Detecta el modo del usuario basado en el mensaje y contexto
        
        Args:
            message: Mensaje del usuario
            context: Contexto adicional (recursos, historial, etc.)
            force_mode: Modo forzado (para testing o override)
        
        Returns:
            Dict con modo detectado, confianza y metadatos
        """
        start_time = time.time()
        context = context or {}
        
        # Si hay modo forzado, usarlo directamente
        if force_mode:
            result = {
                "mode": force_mode,
                "confidence": 1.0,
                "detection_type": "forced",
                "reason": f"Modo forzado: {force_mode}",
                "processing_time_ms": 0
            }
            
            # Log de decisión forzada
            await self._log_mode_decision(message, force_mode, 1.0, context, "forced_mode")
            return result
        
        # Verificar cache primero
        cache_key = self._generate_cache_key(message, context)
        cached_result = self._get_cached_detection(cache_key)
        if cached_result:
            logger.debug(f"[ModeDetectionService] Cache hit para: {message[:50]}...")
            
            # Log de cache hit
            await self._log_mode_decision(message, cached_result["detected_mode"], 
                                       cached_result["confidence_score"], context, "cache_hit")
            return cached_result
        
        # Análisis de intención
        intent_analysis = self._analyze_intent(message)
        
        # Análisis de recursos
        resource_analysis = await self._analyze_resources(context)
        
        # Análisis histórico (si hay chat_id)
        chat_id = context.get("chat_id")
        historical_analysis = await self._analyze_historical_context(chat_id, context)
        
        # Cálculo de ambigüedad
        ambiguity_score = self._calculate_ambiguity(intent_analysis, resource_analysis, historical_analysis)
        
        # Toma de decisión
        decision_result = self._make_decision(
            intent_analysis, resource_analysis, historical_analysis, 
            ambiguity_score, message, context
        )
        
        # Actualizar tiempo de ejecución
        decision_result["detection_metadata"]["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        # Guardar en cache
        self._cache_detection(cache_key, decision_result)
        
        # Log de decisión automática
        await self._log_mode_decision(
            message, 
            decision_result["detected_mode"], 
            decision_result["confidence_score"], 
            context, 
            "automatic_detection"
        )
        
        logger.info(f"[ModeDetectionService] Modo detectado: {decision_result['detected_mode']} (confianza: {decision_result['confidence_score']:.2f})")
        return decision_result
    
    async def _log_mode_decision(
        self,
        message: str,
        detected_mode: str,
        confidence: float,
        context: Dict[str, Any],
        decision_type: str
    ):
        """Registra la decisión de modo usando el logger"""
        try:
            # Obtener el logger de modo de forma lazy
            if not hasattr(self, '_mode_logger'):
                try:
                    self._mode_logger = self.factory.get_mode_detection_logger()
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ No se pudo obtener el logger: {e}")
                    return
            
            if self._mode_logger:
                await self._mode_logger.log_mode_decision(
                    user_id=self.user_id,
                    decision_type=decision_type,
                    input_text=message,
                    detected_mode=detected_mode,
                    confidence=confidence,
                    context=context
                )
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error registrando decisión: {e}")
    
    async def get_personalized_prompt(
        self,
        message: str,
        detected_mode: str,
        context: Dict[str, Any]
    ) -> str:
        """Obtiene un prompt personalizado basado en el modo detectado"""
        try:
            # Obtener el prompt builder de forma lazy
            if not hasattr(self, '_prompt_builder'):
                try:
                    self._prompt_builder = self.factory.get_prompt_builder_service()
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ No se pudo obtener el prompt builder: {e}")
                    return self._get_fallback_prompt(detected_mode)
            
            if self._prompt_builder:
                # Obtener el usuario desde el factory
                user = self.factory.user
                return await self._prompt_builder.build_user_profile_prompt(user, detected_mode, context)
            else:
                return self._get_fallback_prompt(detected_mode)
                
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error obteniendo prompt personalizado: {e}")
            return self._get_fallback_prompt(detected_mode)
    
    def _get_fallback_prompt(self, mode: str) -> str:
        """Prompt de fallback cuando no hay prompt builder disponible"""
        if mode == "explorer":
            return "Eres un asistente experto en exploración de recursos. Ayuda al usuario a descubrir y entender qué está disponible."
        elif mode == "guided":
            return "Eres un asistente experto en ejecución guiada. Ayuda al usuario a ejecutar acciones específicas paso a paso."
        else:
            return "Eres un asistente inteligente. Analiza la intención del usuario y proporciona la mejor ayuda posible."
    
    async def get_prioritized_resources(
        self,
        query_type: str,
        available_resources: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Obtiene recursos priorizados usando el ResourcePriorityService"""
        try:
            # Obtener el resource priority service de forma lazy
            if not hasattr(self, '_resource_priority'):
                try:
                    self._resource_priority = self.factory.get_resource_priority_service()
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ No se pudo obtener el resource priority service: {e}")
                    return self._sort_resources_fallback(available_resources)
            
            if self._resource_priority:
                from app.services.ai.resource_priority_service import QueryType
                
                # Mapear query_type a QueryType enum
                if query_type == "data_query":
                    query_type_enum = QueryType.DATA_QUERY
                elif query_type == "operation_query":
                    query_type_enum = QueryType.OPERATION_QUERY
                elif query_type == "analysis_query":
                    query_type_enum = QueryType.ANALYSIS_QUERY
                else:
                    query_type_enum = QueryType.DATA_QUERY
                
                return await self._resource_priority.prioritize_resources(
                    user_id=self.user_id,
                    query_type=query_type_enum,
                    available_resources=available_resources,
                    context=context
                )
            else:
                return self._sort_resources_fallback(available_resources)
                
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error priorizando recursos: {e}")
            return self._sort_resources_fallback(available_resources)
    
    def _sort_resources_fallback(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ordenamiento de fallback cuando no hay resource priority service"""
        try:
            # Ordenar por tipo: DB > App > Strategy
            type_priority = {
                "database": 3,
                "application": 2,
                "strategy": 1
            }
            
            def get_priority(resource):
                resource_type = resource.get("type", "unknown")
                return type_priority.get(resource_type, 0)
            
            return sorted(resources, key=get_priority, reverse=True)
            
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error en ordenamiento de fallback: {e}")
            return resources
    
    async def get_mode_indicators(
        self,
        active_mode: str,
        style: str = "modern",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Obtiene indicadores visuales del modo activo"""
        try:
            # Obtener el mode indicator service de forma lazy
            if not hasattr(self, '_mode_indicator'):
                try:
                    self._mode_indicator = self.factory.get_mode_indicator_service()
                except Exception as e:
                    logger.warning(f"[ModeDetectionService] ⚠️ No se pudo obtener el mode indicator service: {e}")
                    return self._get_fallback_indicators(active_mode)
            
            if self._mode_indicator:
                from app.services.ai.mode_indicator_service import VisualStyle
                
                # Mapear style a VisualStyle enum
                if style == "modern":
                    visual_style = VisualStyle.MODERN
                elif style == "classic":
                    visual_style = VisualStyle.CLASSIC
                elif style == "colorful":
                    visual_style = VisualStyle.COLORFUL
                elif style == "dark":
                    visual_style = VisualStyle.DARK
                elif style == "light":
                    visual_style = VisualStyle.LIGHT
                else:
                    visual_style = VisualStyle.MODERN
                
                return await self._mode_indicator.get_mode_indicator(
                    user_id=self.user_id,
                    active_mode=active_mode,
                    style=visual_style,
                    context=context
                )
            else:
                return self._get_fallback_indicators(active_mode)
                
        except Exception as e:
            logger.warning(f"[ModeDetectionService] ⚠️ Error obteniendo indicadores: {e}")
            return self._get_fallback_indicators(active_mode)
    
    def _get_fallback_indicators(self, active_mode: str) -> Dict[str, Any]:
        """Indicadores de fallback cuando no hay mode indicator service"""
        return {
            "mode": active_mode,
            "badge": {
                "text": active_mode.upper(),
                "color": "blue" if active_mode == "explorer" else "green",
                "style": "simple"
            },
            "status": "active",
            "tips": [
                f"Modo {active_mode} activo",
                "Usa comandos específicos para este modo"
            ]
        }


# Función helper para dependency injection
def get_mode_detection_service(factory) -> ModeDetectionService:
    """Obtiene una instancia del Mode Detection Service"""
    return ModeDetectionService(factory)
