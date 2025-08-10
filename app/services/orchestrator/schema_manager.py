"""
SchemaManager - Manejo de Esquemas de Base de Datos
────────────────────────────────────────────────────
Módulo especializado para:
- Carga de esquemas de base de datos
- Introspección de esquemas
- Conversión de formatos
- Validación de esquemas
- Optimización de esquemas
"""

import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context

logger = logging.getLogger(__name__)


class SchemaManager:
    """Maneja todas las operaciones relacionadas con esquemas de base de datos"""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        
    @monitor_performance("load_database_schemas")
    @profile_function("load_database_schemas")
    async def load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """Carga esquemas de base de datos de forma asíncrona"""
        try:
            # 🔒 CONTROL DE TOKENS - Usar sesión específica para esquemas
            with performance_context("db_schema_loading"):
                schemas = {}
                
                for db_id in db_ids:
                    try:
                        # Intentar cargar desde cache primero
                        cached_schema = await self._load_cached_schema(db_id)
                        if cached_schema:
                            schemas[db_id] = cached_schema
                            continue
                            
                        # Si no hay cache, cargar desde la base
                        schema = await self._load_schema_from_database(db_id)
                        if schema:
                            schemas[db_id] = schema
                            
                    except Exception as e:
                        logger.error(f"Error cargando schema para DB {db_id}: {e}")
                        # Intentar con introspección mínima como fallback
                        fallback_schema = self._introspect_minimal_schema(db_id)
                        if fallback_schema:
                            schemas[db_id] = fallback_schema
                
                return schemas
                
        except Exception as e:
            logger.error(f"Error en load_database_schemas_async: {e}")
            return {}
    
    async def _load_cached_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Carga esquema desde cache si está disponible"""
        try:
            # Aquí implementarías la lógica de cache
            # Por ahora retornamos None para forzar carga desde DB
            return None
        except Exception as e:
            logger.warning(f"Error cargando cache para DB {db_id}: {e}")
            return None
    
    async def _load_schema_from_database(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Carga esquema directamente desde la base de datos"""
        try:
            # Obtener conexión a la base de datos
            db_connection = await self._get_database_connection(db_id)
            if not db_connection:
                return None
                
            # Cargar esquema usando la conexión
            schema = await self._introspect_database_schema(db_connection, db_id)
            return schema
            
        except Exception as e:
            logger.error(f"Error cargando schema desde DB {db_id}: {e}")
            return None
    
    async def _get_database_connection(self, db_id: UUID) -> Optional[Any]:
        """Obtiene conexión a la base de datos específica"""
        try:
            # Implementar lógica para obtener conexión
            # Por ahora retornamos None
            return None
        except Exception as e:
            logger.error(f"Error obteniendo conexión para DB {db_id}: {e}")
            return None
    
    async def _introspect_database_schema(self, connection: Any, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección del esquema de la base de datos"""
        try:
            # Implementar introspección real
            # Por ahora retornamos un esquema de ejemplo
            return {
                "tables": [],
                "views": [],
                "procedures": []
            }
        except Exception as e:
            logger.error(f"Error en introspección para DB {db_id}: {e}")
            return None
    
    def _introspect_minimal_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección mínima del esquema como fallback"""
        try:
            # 🔒 CONTROL DE TOKENS - Esquema mínimo para fallback
            minimal_schema = {
                "db_id": str(db_id),
                "tables": [],
                "schema_type": "minimal_fallback",
                "warning": "Schema loaded with minimal introspection due to errors"
            }
            
            logger.info(f"Usando esquema mínimo para DB {db_id}")
            return minimal_schema
            
        except Exception as e:
            logger.error(f"Error en introspección mínima para DB {db_id}: {e}")
            return None
    
    def _convert_snapshot_to_legacy(self, snapshot_tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convierte esquema de snapshot al formato legacy"""
        try:
            legacy_tables = []
            
            for table_name, table_info in snapshot_tables.items():
                if isinstance(table_info, dict) and 'columns' in table_info:
                    legacy_table = {
                        'table_name': table_name,
                        'columns': []
                    }
                    
                    # Convertir columnas
                    for col_name, col_info in table_info['columns'].items():
                        if isinstance(col_info, dict):
                            legacy_column = {
                                'column_name': col_name,
                                'data_type': col_info.get('type', 'unknown'),
                                'is_nullable': col_info.get('nullable', True),
                                'column_default': col_info.get('default'),
                                'character_maximum_length': col_info.get('length')
                            }
                            legacy_table['columns'].append(legacy_column)
                    
                    legacy_tables.append(legacy_table)
            
            return legacy_tables
            
        except Exception as e:
            logger.error(f"Error convirtiendo snapshot a legacy: {e}")
            return []
    
    def _optimize_schema_with_search_results(
        self, 
        schema: List[Dict[str, Any]], 
        search_results: List[Any]
    ) -> Dict[str, Any]:
        """Optimiza esquema basado en resultados de búsqueda"""
        try:
            if not schema or not search_results:
                return {"optimized_schema": schema, "optimization_applied": False}
            
            # 🔒 CONTROL DE TOKENS - Optimización inteligente
            optimized_tables = []
            relevance_scores = {}
            
            # Calcular scores de relevancia
            for table in schema:
                table_name = table.get('table_name', '').lower()
                score = 0
                
                for result in search_results:
                    result_text = str(result).lower()
                    if table_name in result_text:
                        score += 1
                    # Buscar coincidencias en nombres de columnas
                    for column in table.get('columns', []):
                        col_name = column.get('column_name', '').lower()
                        if col_name in result_text:
                            score += 0.5
                
                relevance_scores[table_name] = score
            
            # Ordenar por relevancia y limitar
            sorted_tables = sorted(
                schema, 
                key=lambda x: relevance_scores.get(x.get('table_name', ''), 0),
                reverse=True
            )
            
            # 🔒 CONTROL DE TOKENS - Limitar tablas optimizadas
            max_optimized_tables = 5
            optimized_tables = sorted_tables[:max_optimized_tables]
            
            return {
                "optimized_schema": optimized_tables,
                "optimization_applied": True,
                "relevance_scores": relevance_scores,
                "original_count": len(schema),
                "optimized_count": len(optimized_tables)
            }
            
        except Exception as e:
            logger.error(f"Error optimizando schema: {e}")
            return {"optimized_schema": schema, "optimization_applied": False}
    
    def validate_schema_completeness(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Valida la completitud del esquema"""
        try:
            validation_result = {
                "is_valid": True,
                "warnings": [],
                "errors": [],
                "completeness_score": 0
            }
            
            if not schema:
                validation_result["is_valid"] = False
                validation_result["errors"].append("Schema is empty")
                return validation_result
            
            # Validar estructura básica
            required_keys = ["tables", "db_id"]
            for key in required_keys:
                if key not in schema:
                    validation_result["warnings"].append(f"Missing key: {key}")
            
            # Validar tablas
            tables = schema.get("tables", [])
            if not tables:
                validation_result["warnings"].append("No tables found in schema")
            
            # Calcular score de completitud
            total_checks = 3
            passed_checks = 0
            
            if schema.get("tables"):
                passed_checks += 1
            if schema.get("db_id"):
                passed_checks += 1
            if len(tables) > 0:
                passed_checks += 1
            
            validation_result["completeness_score"] = (passed_checks / total_checks) * 100
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validando schema: {e}")
            return {
                "is_valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "completeness_score": 0
            }
