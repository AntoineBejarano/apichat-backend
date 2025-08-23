import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage
from app.models.app_model import App
from app.models.function_model import Function
from ..state.exploration_state import ExplorationState
from ..cache.schema_cache import SchemaCache
from ..cache.service_cache import ServiceCache
from ..cache.database_connection_cache import get_database_connection_cache
from ..utils.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class ResourceInferenceNode:
    """Nodo para inferir bases de datos, aplicaciones y funciones"""
    
    def __init__(self, factory: ServiceFactory, schema_cache: SchemaCache, service_cache: ServiceCache):
        self.factory = factory
        self.schema_cache = schema_cache
        self.service_cache = service_cache
        
        # 🔧 NUEVO: Cache singleton para conexiones de BD
        self.db_connection_cache = get_database_connection_cache()
        logger.info("[ResourceInferenceNode] 🔗 Cache de conexiones BD inicializado")
    
    async def run(self, state: ExplorationState, performance_metrics: PerformanceMetrics) -> ExplorationState:
        """Ejecuta la inferencia de recursos"""
        node_start_time = time.time()
        
        message: ChatMessage = state["message"]
        
        # Si ya vienen db_ids/apps en el state, procesarlos directamente
        if state.get("db_ids") or state.get("apps"):
            logger.info("[ResourceInferenceNode] 📥 Recursos ya proporcionados en state, procesando esquemas directamente")
            db_candidates = [(db_id, 1.0) for db_id in state.get("db_ids", [])]
            app_candidates = [(app_id, 1.0) for app_id in state.get("apps", [])]
        else:
            logger.info("[ResourceInferenceNode] 🎯 Iniciando selección automática por descripciones")
            db_candidates, app_candidates = await self._select_candidates_by_description(message)
        
        # Procesar bases de datos
        db_ids, db_conns, db_dialect, compact_schemas, cache_status = await self._process_databases(db_candidates)
        
        # Procesar aplicaciones
        apps, functions, proxy_id = await self._process_applications(app_candidates)
        
        # Log resumen
        logger.info(f"[ResourceInferenceNode] 🎯 Selección completada: {len(db_ids)} DBs, {len(apps)} apps, {len(functions)} functions")
        
        if compact_schemas:
            total_chars = sum(len(schema) for schema in compact_schemas.values())
            logger.info(f"[ResourceInferenceNode] 📋 Schemas listos: {total_chars} chars total")
        
        # Registrar métricas
        node_time = time.time() - node_start_time
        performance_metrics.record_node_time("init", node_time)
        
        return {
            **state,
            "db_ids": db_ids,
            "db_conns": db_conns,
            "db_dialect": db_dialect,
            "apps": apps,
            "functions": functions,
            "proxy_id": proxy_id,
            "compact_schemas": compact_schemas,
            "cache_status": cache_status,
        }
    
    async def _select_candidates_by_description(self, message: ChatMessage) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
        """Selecciona candidatos usando DescriptionSelectorService"""
        try:
            selector = self.factory.get_description_selector_service()
            picks = selector.select(message.content, top_k=2, threshold=0.55)
            
            db_candidates = picks.get("db_candidates", [])
            app_candidates = picks.get("app_candidates", [])
            
            # Ordenar candidatos por score descendente para orden estable
            db_candidates.sort(key=lambda x: x[1], reverse=True)
            app_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Corte explícito tras ordenar para asegurar top-k
            TOP_K_LIMIT = 2
            db_candidates = db_candidates[:TOP_K_LIMIT]
            app_candidates = app_candidates[:TOP_K_LIMIT]
            
            logger.info(f"[ResourceInferenceNode] 📋 Candidatos (top-{TOP_K_LIMIT}): {len(db_candidates)} DBs, {len(app_candidates)} apps")
            if db_candidates:
                logger.info(f"[ResourceInferenceNode] 🗄️ Top DB scores: {[(db_id[:8], f'{score:.3f}') for db_id, score in db_candidates[:3]]}")
            if app_candidates:
                logger.info(f"[ResourceInferenceNode] 📱 Top App scores: {[(app_id, f'{score:.3f}') for app_id, score in app_candidates[:3]]}")
            
            return db_candidates, app_candidates
            
        except Exception as e:
            logger.exception(f"[ResourceInferenceNode] ❌ Error en selección automática: {e}")
            return [], []
    
    async def _process_databases(self, db_candidates: List[Tuple[str, float]]) -> Tuple[List[str], List[Dict[str, Any]], Optional[str], Dict[str, str], Dict[str, str]]:
        """Procesa las bases de datos candidatas"""
        db_ids: List[str] = []
        db_conns: List[Dict[str, Any]] = []
        db_dialect: Optional[str] = None
        compact_schemas: Dict[str, str] = {}
        cache_status: Dict[str, str] = {}
        
        # Obtener servicios
        database_service = self._get_service_lazy("database_service", self.factory.get_database_service)
        cache_service = self._get_service_lazy("detailed_schema_cache_service", self.factory.get_detailed_schema_cache_service)
        
        for db_id_str, score in db_candidates:
            try:
                db_id_uuid = UUID(db_id_str)
                
                # Warm-up del schema con cache inteligente
                logger.info(f"[ResourceInferenceNode] 🔥 Warm-up schema para DB {db_id_str[:8]}... (score: {score:.3f})")
                
                # Verificar si necesitamos actualizar el schema
                if self.schema_cache.needs_schema_update(self.factory.user.id, db_id_str):
                    cache_entry = await cache_service.get_schema_cache(self.factory.user.id, db_id_uuid)
                    self.schema_cache.update_schema_check_timestamp(self.factory.user.id, db_id_str)
                    logger.info(f"[ResourceInferenceNode] 🔄 Schema actualizado para DB {db_id_str[:8]}")
                else:
                    # Reutilizar schema del cache
                    compact_schema = self.schema_cache.get_cleaned_schema(self.factory.user.id, db_id_str)
                    if compact_schema:
                        cache_entry = None
                        logger.info(f"[ResourceInferenceNode] 🚀 Schema reutilizado del cache para DB {db_id_str[:8]}")
                    else:
                        cache_entry = await cache_service.get_schema_cache(self.factory.user.id, db_id_uuid)
                
                # Verificar esquemas compactos válidos
                compact_schema = self._extract_compact_schema(cache_entry, db_id_str)
                
                if compact_schema:
                    # Schema válido - incluir esta DB
                    db_ids.append(db_id_str)
                    compact_schemas[db_id_str] = compact_schema
                    
                    # Procesar instancia SQL (solo información básica, no el objeto completo)
                    sql_info, db_dialect = await self._process_sql_instance(db_id_str, db_id_uuid, database_service, db_dialect)
                    if sql_info:
                        db_conns.append(sql_info)
                    
                    logger.info(f"[ResourceInferenceNode] ✅ DB {db_id_str[:8]} ready (schema: {len(compact_schema)} chars)")
                
            except Exception as e:
                logger.exception(f"[ResourceInferenceNode] ❌ Error procesando DB {db_id_str[:8]}: {e}")
                cache_status[db_id_str] = "processing_error"
        
        return db_ids, db_conns, db_dialect, compact_schemas, cache_status
    
    def _extract_compact_schema(self, cache_entry, db_id_str: str) -> Optional[str]:
        """Extrae el schema compacto de la entrada del cache"""
        if cache_entry and cache_entry.compact:
            if isinstance(cache_entry.compact, str) and cache_entry.compact.strip():
                logger.info(f"[ResourceInferenceNode] ✅ Esquema compacto válido para DB {db_id_str}")
                return cache_entry.compact
            elif isinstance(cache_entry.compact, dict) and cache_entry.compact.get("compact"):
                compact_value = cache_entry.compact.get("compact")
                if isinstance(compact_value, str) and compact_value.strip():
                    logger.info(f"[ResourceInferenceNode] ✅ Esquema compacto válido para DB {db_id_str} (desde dict)")
                    return compact_value
        return None
    
    async def _process_sql_instance(self, db_id_str: str, db_id_uuid: UUID, database_service, db_dialect: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Procesa la instancia SQL de la base de datos usando cache singleton (devuelve info serializable)"""
        try:
            # 🔧 NUEVO: Usar cache singleton para conexiones de BD
            # Esto evita recrear SQLDatabase en cada llamada
            sql_database = self.db_connection_cache.get_connection(
                str(self.factory.user.id), 
                db_id_str, 
                database_service
            )
            
            if sql_database:
                # Actualizar estadísticas de acceso
                self.db_connection_cache.update_access(str(self.factory.user.id), db_id_str)
                
                # Inferir dialecto si no lo tenemos
                if not db_dialect:
                    try:
                        db_dialect = database_service.get_dialect_name(db_id_uuid)
                        if db_dialect:
                            logger.info(f"[ResourceInferenceNode] 🧪 Dialecto inferido: {db_dialect}")
                        else:
                            db_dialect = "postgresql"
                            logger.info(f"[ResourceInferenceNode] 🧪 Dialecto por defecto: {db_dialect}")
                    except Exception as de:
                        logger.debug(f"[ResourceInferenceNode] No se pudo inferir dialecto: {de}")
                        db_dialect = "postgresql"
                
                # Retornar información serializable en lugar del objeto completo
                sql_info = {
                    "db_id": db_id_str,
                    "type": "sql_database",
                    "has_engine": hasattr(sql_database, 'engine'),
                    "dialect": db_dialect,
                    "cached": True,
                    "cache_source": "singleton_cache"
                }
                
                logger.info(f"[ResourceInferenceNode] ✅ Instancia SQL procesada para DB {db_id_str[:8]} (cache HIT)")
                return sql_info, db_dialect
            else:
                logger.warning(f"[ResourceInferenceNode] ⚠️ No se pudo obtener conexión para DB {db_id_str[:8]}")
                return None, db_dialect
                
        except Exception as e:
            logger.exception(f"[ResourceInferenceNode] ❌ Error procesando instancia SQL para DB {db_id_str[:8]}: {e}")
            return None, db_dialect
    
    async def _process_applications(self, app_candidates: List[Tuple[str, float]]) -> Tuple[List[App], List[Function], Optional[str]]:
        """Procesa las aplicaciones candidatas"""
        apps: List[App] = []
        functions: List[Function] = []
        proxy_id: Optional[str] = None
        
        # Obtener servicios
        app_service = self._get_service_lazy("app_service", self.factory.get_app_service)
        function_service = self._get_service_lazy("function_service", self.factory.get_function_service)
        
        for app_id_str, score in app_candidates:
            try:
                # Convertir app_id a UUID
                try:
                    app_id = UUID(app_id_str) if isinstance(app_id_str, str) else app_id_str
                except ValueError:
                    logger.warning(f"[ResourceInferenceNode] ⚠️ Invalid app_id UUID format: {app_id_str}")
                    continue
                
                app = app_service.get_by_id(app_id)
                if app:
                    apps.append(app)
                    
                    # Cargar functions de esta app
                    app_functions = function_service.get_by_app(app.id)
                    functions.extend(app_functions)
                    
                    # Conservar proxy_id si aplica
                    if app.proxy_id and not proxy_id:
                        proxy_id = app.proxy_id
                    
                    logger.info(f"[ResourceInferenceNode] ✅ App {app.name} loaded (score: {score:.3f}, functions: {len(app_functions)})")
                    
            except Exception as e:
                logger.warning(f"[ResourceInferenceNode] ⚠️ Error cargando app {app_id_str[:8]}: {e}")
        
        return apps, functions, proxy_id
    
    def _get_service_lazy(self, service_name: str, service_factory_method):
        """Obtiene un servicio solo cuando se necesita, cacheando la instancia"""
        # Verificar si ya tenemos el servicio en cache
        service_instance = self.service_cache.get_service(service_name)
        if service_instance:
            return service_instance
        
        # Crear nueva instancia
        try:
            service_instance = service_factory_method()
            if service_instance:
                # Usar register_service en lugar de set_service
                if hasattr(self.service_cache, 'register_service'):
                    self.service_cache.register_service(service_name, lambda: service_instance)
                else:
                    logger.warning(f"[ResourceInferenceNode] ⚠️ Cache no soporta register_service para {service_name}")
                
                logger.info(f"[ResourceInferenceNode] 🆕 Cache MISS: {service_name} inicializado")
                return service_instance
            else:
                logger.warning(f"[ResourceInferenceNode] ⚠️ {service_name} no disponible")
                return None
                
        except Exception as e:
            logger.error(f"[ResourceInferenceNode] ❌ Error inicializando {service_name}: {e}")
            return None
