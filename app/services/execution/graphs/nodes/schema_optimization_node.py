import time
import logging
from typing import Dict, Any, List
from sqlalchemy.engine import Engine

from app.core.service_factory import ServiceFactory
from ..state.exploration_state import ExplorationState
from ..cache.schema_cache import SchemaCache
from ..cache.optimized_schema_cache import OptimizedSchemaCache
from ..cache.schema_compressor import SchemaCompressor
from ..cache.service_cache import ServiceCache
from ..cache.database_connection_cache import get_database_connection_cache
from ..utils.performance_metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class SchemaOptimizationNode:
    """Nodo para optimizar y estructurar esquemas de base de datos"""
    
    def __init__(self, factory: ServiceFactory, schema_cache: SchemaCache, 
                 optimized_schema_cache: OptimizedSchemaCache, service_cache: ServiceCache):
        self.factory = factory
        self.schema_cache = schema_cache
        self.optimized_schema_cache = optimized_schema_cache
        self.service_cache = service_cache
        self._processed_schemas_cache = {}
        
        # 🔧 NUEVO: Cache singleton para conexiones de BD
        self.db_connection_cache = get_database_connection_cache()
        
        # Inicializar compresor de esquemas
        self.schema_compressor = SchemaCompressor()
        logger.info("[SchemaOptimizationNode] 🗜️ Compresor de esquemas inicializado")
        logger.info("[SchemaOptimizationNode] 🔗 Cache de conexiones BD inicializado")
    
    async def run(self, state: ExplorationState, performance_metrics: PerformanceMetrics) -> ExplorationState:
        """Optimiza esquemas solo cuando es necesario - NO en cada mensaje"""
        node_start_time = time.time()
        
        try:
            # 🔧 OPTIMIZACIÓN: Solo ejecutar si realmente es necesario
            if not state.get("db_ids"):
                logger.info("[SchemaOptimizationNode] ℹ️ No hay bases de datos para optimizar")
                return state
            
            # 🔧 OPTIMIZACIÓN: Verificar si ya tenemos schemas optimizados
            existing_optimized = state.get("optimized_schemas", {})
            if existing_optimized and len(existing_optimized) == len(state["db_ids"]):
                logger.info("[SchemaOptimizationNode] 🔥 Cache HIT: Schemas ya optimizados, saltando optimización")
                return state
            
            # 🔧 OPTIMIZACIÓN: Verificar si los schemas han cambiado
            compact_schemas = state.get("compact_schemas", {})
            if not compact_schemas:
                logger.info("[SchemaOptimizationNode] ℹ️ No hay schemas compactos para optimizar")
                return state
            
            # 🔧 OPTIMIZACIÓN: Solo optimizar schemas nuevos o modificados
            schemas_to_optimize = {}
            for db_id in state["db_ids"]:
                if db_id in compact_schemas:
                    # Verificar si ya está optimizado y no ha cambiado
                    if db_id in existing_optimized:
                        logger.info(f"[SchemaOptimizationNode] 🔥 Schema ya optimizado para DB {db_id}")
                        continue
                    else:
                        schemas_to_optimize[db_id] = compact_schemas[db_id]
                        logger.info(f"[SchemaOptimizationNode] 🆕 Schema nuevo para optimizar: DB {db_id}")
            
            if not schemas_to_optimize:
                logger.info("[SchemaOptimizationNode] ℹ️ Todos los schemas ya están optimizados")
                return state
            
            logger.info(f"[SchemaOptimizationNode] 🚀 Optimizando {len(schemas_to_optimize)} schemas nuevos...")
            
            # Obtener servicios necesarios
            database_service = self._get_service_lazy("database_service", self.factory.get_database_service)
            if not database_service:
                logger.error("[SchemaOptimizationNode] ❌ DatabaseService no disponible")
                return state
            
            # Procesar solo los schemas que necesitan optimización
            optimized_schemas = existing_optimized.copy()  # Mantener los existentes
            optimization_stats = {
                "total_processed": 0,
                "cache_hits": len(existing_optimized),
                "cache_misses": len(schemas_to_optimize),
                "optimization_errors": 0,
                "compression_ratios": []
            }
            
            for db_id, schema in schemas_to_optimize.items():
                try:
                    # Verificar si ya tenemos el esquema optimizado en cache
                    if self.optimized_schema_cache.has_optimized_schema(self.factory.user.id, db_id):
                        logger.info(f"[SchemaOptimizationNode] 🔥 Cache HIT para DB {db_id}")
                        optimized_schema = self.optimized_schema_cache.get_optimized_schema(self.factory.user.id, db_id)
                        if optimized_schema:
                            optimized_schemas[db_id] = optimized_schema
                            optimization_stats["cache_hits"] += 1
                            optimization_stats["cache_misses"] -= 1
                            continue
                    
                    # Cache MISS - necesitamos optimizar
                    logger.info(f"[SchemaOptimizationNode] ❄️ Cache MISS para DB {db_id}, optimizando...")
                    
                    # Obtener conexión a la base de datos
                    db_connection = await self._get_database_connection(database_service, db_id)
                    if not db_connection:
                        logger.warning(f"[SchemaOptimizationNode] ⚠️ No se pudo conectar a DB {db_id}")
                        continue
                    
                    # Validar que la conexión sea un Engine válido
                    if not hasattr(db_connection, 'dialect'):
                        logger.error(f"[SchemaOptimizationNode] ❌ Conexión no es un Engine válido: {type(db_connection)}")
                        continue
                    
                    # Optimizar esquema
                    from ..cache.schema_optimizer import SchemaOptimizer
                    optimizer = SchemaOptimizer()
                    
                    logger.info(f"[SchemaOptimizationNode] 🚀 Iniciando optimización para DB {db_id} con Engine {type(db_connection)}")
                    
                    optimized_schema = await optimizer.optimize_schema(db_connection, db_id)
                    
                    if "error" not in optimized_schema:
                        # Aplicar compresión adicional al esquema
                        compressed_schema = self._apply_schema_compression(optimized_schema)
                        
                        # Guardar en cache optimizado
                        success = self.optimized_schema_cache.set_optimized_schema(
                            self.factory.user.id, db_id, compressed_schema
                        )
                        
                        if success:
                            optimized_schemas[db_id] = compressed_schema
                            optimization_stats["total_processed"] += 1
                            
                            # Calcular ratio de compresión
                            compression_stats = self._calculate_compression_stats(optimized_schema, compressed_schema)
                            optimization_stats["compression_ratios"].append(compression_stats["compression_ratio_percent"])
                            
                            logger.info(f"[SchemaOptimizationNode] ✅ Esquema optimizado y comprimido para DB {db_id}")
                            logger.info(f"[SchemaOptimizationNode] 🗜️ Compresión: {compression_stats['compression_ratio_percent']:.1f}% ({compression_stats['space_saved_kb']:.1f}KB ahorrados)")
                        else:
                            logger.error(f"[SchemaOptimizationNode] ❌ Error guardando esquema optimizado para DB {db_id}")
                            optimization_stats["optimization_errors"] += 1
                    else:
                        logger.error(f"[SchemaOptimizationNode] ❌ Error optimizando esquema para DB {db_id}: {optimized_schema['error']}")
                        optimization_stats["optimization_errors"] += 1
                
                except Exception as e:
                    logger.error(f"[SchemaOptimizationNode] ❌ Error procesando DB {db_id}: {e}")
                    optimization_stats["optimization_errors"] += 1
            
            # Preparar respuesta
            final_response = {
                **state,
                "optimized_schemas": optimized_schemas,
                "optimization_stats": optimization_stats,
                "schema_optimization_complete": True
            }
            
            # Log de estadísticas
            self._log_optimization_stats(optimization_stats)
            
            # Registrar métricas
            node_time = time.time() - node_start_time
            performance_metrics.record_node_time("schema_optimization", node_time)
            performance_metrics.calculate_total_time()
            performance_metrics.log_breakdown()
            
            final_response["performance_metrics"] = performance_metrics.get_metrics()
            
            return final_response
            
        except Exception as e:
            logger.exception(f"[SchemaOptimizationNode] ❌ Error en optimización de esquemas: {e}")
            return {
                **state,
                "error": f"Error optimizando esquemas: {str(e)}",
                "schema_optimization_complete": False
            }
    
    async def _get_database_connection(self, database_service, db_id: str) -> Engine:
        """Obtiene una conexión a la base de datos usando cache singleton - SIEMPRE retorna Engine de SQLAlchemy"""
        try:
            # 🔧 NUEVO: Usar cache singleton para conexiones de BD
            # Esto evita recrear SQLDatabase en cada llamada
            engine = self.db_connection_cache.get_engine(
                str(self.factory.user.id), 
                db_id, 
                database_service
            )
            
            if engine:
                # Actualizar estadísticas de acceso
                self.db_connection_cache.update_access(str(self.factory.user.id), db_id)
                logger.info(f"[SchemaOptimizationNode] 🔥 Cache HIT para DB {db_id}: Engine obtenido")
                return engine
            else:
                logger.error(f"[SchemaOptimizationNode] ❌ No se pudo obtener Engine para DB {db_id}")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaOptimizationNode] ❌ Error obteniendo conexión para DB {db_id}: {e}")
            return None
    
    def _apply_schema_compression(self, optimized_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica compresión adicional al esquema optimizado"""
        try:
            # Convertir esquema a texto para compresión
            schema_text = self._schema_to_text(optimized_schema)
            
            # Comprimir usando el compresor
            compressed_text = self.schema_compressor.compress_schema(schema_text, target_size_kb=3.0)
            
            # Crear esquema comprimido
            compressed_schema = {
                **optimized_schema,
                "compressed_schema": compressed_text,
                "compression_applied": True,
                "original_size_chars": len(schema_text),
                "compressed_size_chars": len(compressed_text)
            }
            
            return compressed_schema
            
        except Exception as e:
            logger.warning(f"[SchemaOptimizationNode] ⚠️ Error aplicando compresión: {e}")
            return optimized_schema  # Retornar original si falla
    
    def _schema_to_text(self, schema: Dict[str, Any]) -> str:
        """Convierte el esquema optimizado a texto para compresión"""
        try:
            lines = []
            tables = schema.get("tables", {})
            
            for table_name, table_info in tables.items():
                lines.append(f"📋 {table_name} ({len(table_info.get('columns', []))} cols)")
                
                for column in table_info.get("columns", []):
                    constraints = []
                    if column.get("primary_key"):
                        constraints.append("NOT NULL PRIMARY KEY")
                    elif not column.get("nullable", True):
                        constraints.append("NOT NULL")
                    if column.get("unique"):
                        constraints.append("UNIQUE")
                    if column.get("index"):
                        constraints.append("INDEX")
                    
                    constraint_str = f" {', '.join(constraints)}" if constraints else ""
                    lines.append(f"  • {column['name']}: {column['type']}{constraint_str}")
                
                lines.append("")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning(f"[SchemaOptimizationNode] ⚠️ Error convirtiendo esquema a texto: {e}")
            return str(schema)
    
    def _calculate_compression_stats(self, original_schema: Dict[str, Any], compressed_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Calcula estadísticas detalladas de compresión"""
        try:
            # Tamaños en caracteres
            original_size = compressed_schema.get("original_size_chars", 0)
            compressed_size = compressed_schema.get("compressed_size_chars", 0)
            
            if original_size > 0:
                # Usar el compresor para estadísticas detalladas
                return self.schema_compressor.get_compression_stats(original_size, compressed_size)
            else:
                # Fallback a cálculo básico
                import json
                original_json = len(json.dumps(original_schema))
                compressed_json = len(json.dumps(compressed_schema))
                
                compression_ratio = (1 - compressed_json / original_json) * 100
                return {
                    'original_size_bytes': original_json,
                    'compressed_size_bytes': compressed_json,
                    'compression_ratio_percent': round(compression_ratio, 1),
                    'space_saved_bytes': original_json - compressed_json,
                    'space_saved_kb': round((original_json - compressed_json) / 1024, 1)
                }
            
        except Exception as e:
            logger.warning(f"[SchemaOptimizationNode] ⚠️ Error calculando estadísticas de compresión: {e}")
            return {
                'original_size_bytes': 0,
                'compressed_size_bytes': 0,
                'compression_ratio_percent': 0.0,
                'space_saved_bytes': 0,
                'space_saved_kb': 0.0
            }
    
    def _log_optimization_stats(self, stats: Dict[str, Any]):
        """Registra las estadísticas de optimización"""
        total_processed = stats["total_processed"]
        cache_hits = stats["cache_hits"]
        cache_misses = stats["cache_misses"]
        errors = stats["optimization_errors"]
        
        logger.info(f"[SchemaOptimizationNode] 📊 === ESTADÍSTICAS DE OPTIMIZACIÓN ===")
        logger.info(f"[SchemaOptimizationNode] 📊 Total procesadas: {total_processed}")
        logger.info(f"[SchemaOptimizationNode] 📊 Cache hits: {cache_hits}")
        logger.info(f"[SchemaOptimizationNode] 📊 Cache misses: {cache_misses}")
        logger.info(f"[SchemaOptimizationNode] 📊 Errores: {errors}")
        
        if stats["compression_ratios"]:
            avg_compression = sum(stats["compression_ratios"]) / len(stats["compression_ratios"])
            logger.info(f"[SchemaOptimizationNode] 📊 Compresión promedio: {avg_compression:.1f}%")
        
        # Calcular hit ratio
        total_requests = cache_hits + cache_misses
        if total_requests > 0:
            hit_ratio = (cache_hits / total_requests) * 100
            logger.info(f"[SchemaOptimizationNode] 📊 Hit ratio: {hit_ratio:.1f}%")
        
        logger.info(f"[SchemaOptimizationNode] 📊 === FIN ESTADÍSTICAS ===")
    
    def _get_service_lazy(self, service_name: str, service_factory_method):
        """Obtiene un servicio solo cuando se necesita"""
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
                    logger.warning(f"[SchemaOptimizationNode] ⚠️ Cache no soporta register_service para {service_name}")
                
                logger.info(f"[SchemaOptimizationNode] 🆕 Cache MISS: {service_name} inicializado")
                return service_instance
            else:
                logger.warning(f"[SchemaOptimizationNode] ⚠️ {service_name} no disponible")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaOptimizationNode] ❌ Error inicializando {service_name}: {e}")
            return None
    
    def get_optimization_summary(self, state: ExplorationState) -> str:
        """Genera un resumen de la optimización de esquemas"""
        optimized_schemas = state.get("optimized_schemas", {})
        optimization_stats = state.get("optimization_stats", {})
        
        if not optimized_schemas:
            return "❌ No se pudieron optimizar esquemas de base de datos"
        
        summary = f"✅ **ESQUEMAS OPTIMIZADOS** - {len(optimized_schemas)} bases de datos\n\n"
        
        # Estadísticas generales
        stats = optimization_stats
        summary += f"📊 **ESTADÍSTICAS**:\n"
        summary += f"  • Total procesadas: {stats.get('total_processed', 0)}\n"
        summary += f"  • Cache hits: {stats.get('cache_hits', 0)}\n"
        summary += f"  • Cache misses: {stats.get('cache_misses', 0)}\n"
        summary += f"  • Errores: {stats.get('optimization_errors', 0)}\n"
        
        # Resumen de cada esquema optimizado
        summary += f"\n🏗️ **ESQUEMAS OPTIMIZADOS**:\n"
        for db_id, schema in optimized_schemas.items():
            if "error" not in schema:
                tables_count = len(schema.get("tables", {}))
                relations_count = len(schema.get("relations", []))
                dialect = schema.get("dialect", "unknown")
                
                summary += f"  • **DB {db_id[:8]}...** ({dialect}): {tables_count} tablas, {relations_count} relaciones\n"
            else:
                summary += f"  • **DB {db_id[:8]}...**: ❌ Error - {schema['error']}\n"
        
        return summary
    
    def get_connection_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache de conexiones de BD"""
        try:
            return self.db_connection_cache.get_cache_stats()
        except Exception as e:
            logger.error(f"[SchemaOptimizationNode] ❌ Error obteniendo estadísticas del cache: {e}")
            return {}
