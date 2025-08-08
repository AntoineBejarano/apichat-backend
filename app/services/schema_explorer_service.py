# app/services/schema_explorer_service.py
"""
SchemaExplorerService - Nivel Unicornio 🦄
───────────────────────────────────────────
Servicio para explorar y cachear esquemas de base de datos con información completa.
Integra con DetailedSchemaCache para mantener esquemas detallados actualizados.
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from sqlalchemy import inspect, text, MetaData
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from dataclasses import asdict

from app.services.cache_service import CacheService
from app.services.database_service import DatabaseService
from app.services.detailed_schema_cache import DetailedSchemaCache, DatabaseSchema, TableInfo, ColumnInfo, ColumnType

logger = logging.getLogger(__name__)


class SchemaExplorerService:
    """
    Servicio para explorar y cachear esquemas de base de datos con información completa.
    """
    
    def __init__(self, cache_service: CacheService, database_service: DatabaseService):
        self.cache_service = cache_service
        self.database_service = database_service
        self.detailed_cache = DetailedSchemaCache()
        logger.info("[SchemaExplorerService] 🦄 Inicializado con cache detallado")
    
    def get_schema_for_user_dbs(
        self, 
        user_id: UUID, 
        db_ids: List[UUID]
    ) -> Dict[UUID, List[Dict[str, Any]]]:
        """
        Obtener esquemas para las bases de datos de un usuario.
        Combina cache y exploración en tiempo real.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos
            
        Returns:
            Diccionario con esquemas: {db_id: [tables]}
        """
        if not db_ids:
            logger.info("[SchemaExplorerService] 📭 No hay bases de datos para explorar")
            return {}
        
        # 1. Intentar obtener desde cache detallado
        detailed_schemas = {}
        schemas_to_explore = []
        
        for db_id in db_ids:
            detailed_schema = self.detailed_cache.get_detailed_schema(db_id)
            if detailed_schema:
                detailed_schemas[db_id] = detailed_schema
                logger.info(f"[SchemaExplorerService] 🦄 Cache detallado hit: {db_id}")
            else:
                schemas_to_explore.append(db_id)
        
        # 2. Explorar las que no están cacheadas
        if schemas_to_explore:
            logger.info(f"[SchemaExplorerService] 🔍 Explorando {len(schemas_to_explore)} DBs en tiempo real")
            explored_schemas = self._explore_detailed_schemas(user_id, schemas_to_explore)
            
            # Combinar cache + exploración
            all_schemas = {**detailed_schemas, **explored_schemas}
        else:
            all_schemas = detailed_schemas
        
        logger.info(f"[SchemaExplorerService] ✅ Esquemas obtenidos: {len(all_schemas)}/{len(db_ids)} DBs")
        return all_schemas
    
    def get_schema_for_query(
        self, 
        user_id: UUID, 
        db_id: UUID, 
        user_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtener esquema optimizado para una query específica.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            user_query: Query del usuario
            
        Returns:
            Esquema optimizado para la query
        """
        return self.detailed_cache.get_schema_for_query(db_id, user_query)
    
    def _explore_detailed_schemas(
        self, 
        user_id: UUID, 
        db_ids: List[UUID]
    ) -> Dict[UUID, DatabaseSchema]:
        """
        Explorar esquemas detallados de bases de datos en tiempo real.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos a explorar
            
        Returns:
            Diccionario con esquemas explorados: {db_id: DatabaseSchema}
        """
        explored_schemas = {}
        
        for db_id in db_ids:
            try:
                logger.info(f"[SchemaExplorerService] 🔍 Explorando DB detallado: {db_id}")
                schema = self._explore_single_db_detailed_schema(db_id)
                
                if schema:
                    # Cachear el esquema explorado
                    self.detailed_cache.cache_detailed_schema(db_id, schema)
                    explored_schemas[db_id] = schema
                    logger.info(f"[SchemaExplorerService] ✅ Explorado detallado: {len(schema.tables)} tablas en DB {db_id}")
                else:
                    logger.warning(f"[SchemaExplorerService] ⚠️ No se encontraron tablas en DB {db_id}")
                    
            except Exception as e:
                logger.error(f"[SchemaExplorerService] ❌ Error explorando DB {db_id}: {e}")
                # No cachear en caso de error
                continue
        
        return explored_schemas
    
    def _explore_single_db_detailed_schema(self, db_id: UUID) -> Optional[DatabaseSchema]:
        """
        Explorar esquema detallado de una base de datos específica.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Esquema detallado con información completa
        """
        try:
            # Obtener conexión SQL
            db_instance = self.database_service.get_sql_instance(db_id)
            
            # Crear metadata para reflection
            metadata = MetaData()
            metadata.reflect(bind=db_instance.engine)
            
            tables = {}
            relationships = {}
            
            # Obtener lista de tablas
            try:
                table_names = db_instance.get_usable_table_names()
            except AttributeError:
                table_names = db_instance.get_table_names()
            
            logger.info(f"[SchemaExplorerService] 📋 Encontradas {len(table_names)} tablas en DB {db_id}")
            
            for table_name in table_names:
                try:
                    # Explorar tabla detallada
                    table_info = self._explore_table_detailed(db_instance, table_name, metadata)
                    if table_info:
                        tables[table_name] = table_info
                        
                        # Explorar relaciones
                        relationships[table_name] = self._explore_table_relationships(table_name, metadata)
                        
                except Exception as e:
                    logger.warning(f"[SchemaExplorerService] ⚠️ Error explorando tabla {table_name}: {e}")
                    continue
            
            # Crear esquema detallado
            schema = DatabaseSchema(
                db_id=db_id,
                tables=tables,
                relationships=relationships,
                last_updated=datetime.now(),
                schema_hash=self._generate_schema_hash(tables),
                version="1.0"
            )
            
            logger.info(f"[SchemaExplorerService] 📊 Exploradas {len(tables)} tablas detalladas en DB {db_id}")
            return schema
            
        except SQLAlchemyError as e:
            logger.error(f"[SchemaExplorerService] ❌ Error de SQLAlchemy explorando DB {db_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error inesperado explorando DB {db_id}: {e}")
            raise
    
    def _explore_table_detailed(
        self, 
        db_instance, 
        table_name: str, 
        metadata: MetaData
    ) -> Optional[TableInfo]:
        """
        Explorar tabla con información detallada.
        
        Args:
            db_instance: Instancia de la base de datos
            table_name: Nombre de la tabla
            metadata: Metadata de SQLAlchemy
            
        Returns:
            Información detallada de la tabla
        """
        try:
            # Obtener información de la tabla desde metadata
            table = metadata.tables.get(table_name)
            if not table:
                return None
            
            columns = {}
            primary_keys = []
            foreign_keys = []
            indexes = []
            
            # Explorar columnas detalladas
            for column in table.columns:
                # Inferir tipo semántico
                semantic_type = self.detailed_cache._infer_semantic_type(column.name, str(column.type))
                
                # Información de foreign key
                foreign_key_info = None
                referenced_table = None
                referenced_column = None
                
                if column.foreign_keys:
                    fk = list(column.foreign_keys)[0]
                    foreign_key_info = f"{fk.column.table.name}.{fk.column.name}"
                    referenced_table = fk.column.table.name
                    referenced_column = fk.column.name
                
                # Crear información detallada de columna
                column_info = ColumnInfo(
                    name=column.name,
                    type=str(column.type),
                    nullable=column.nullable,
                    default=str(column.default) if column.default else None,
                    primary_key=column.primary_key,
                    unique=column.unique,
                    foreign_key=foreign_key_info,
                    referenced_table=referenced_table,
                    referenced_column=referenced_column,
                    semantic_type=semantic_type,
                    description=None
                )
                
                columns[column.name] = column_info
                
                # Recolectar primary keys
                if column.primary_key:
                    primary_keys.append(column.name)
                
                # Recolectar foreign keys
                if foreign_key_info:
                    foreign_keys.append({
                        "column": column.name,
                        "referenced_table": referenced_table,
                        "referenced_column": referenced_column
                    })
            
            # Explorar índices
            try:
                inspector = inspect(db_instance.engine)
                table_indexes = inspector.get_indexes(table_name)
                indexes = table_indexes
            except Exception as e:
                logger.debug(f"[SchemaExplorerService] ⚠️ No se pudieron obtener índices para {table_name}: {e}")
                indexes = []
            
            # Obtener row count (opcional)
            row_count = None
            try:
                result = db_instance.run(f"SELECT COUNT(*) FROM {table_name}")
                if result and isinstance(result, list) and len(result) > 0:
                    row_count = result[0].get('count', 0) if isinstance(result[0], dict) else result[0]
            except Exception as e:
                logger.debug(f"[SchemaExplorerService] ⚠️ No se pudo obtener row count para {table_name}: {e}")
            
            return TableInfo(
                name=table_name,
                columns=columns,
                primary_keys=primary_keys,
                foreign_keys=foreign_keys,
                indexes=indexes,
                row_count=row_count,
                description=None
            )
            
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error explorando tabla detallada {table_name}: {e}")
            return None
    
    def _explore_table_relationships(self, table_name: str, metadata: MetaData) -> List[str]:
        """
        Explorar relaciones de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            metadata: Metadata de SQLAlchemy
            
        Returns:
            Lista de tablas relacionadas
        """
        try:
            table = metadata.tables.get(table_name)
            if not table:
                return []
            
            related_tables = set()
            
            # Buscar tablas relacionadas por foreign keys
            for column in table.columns:
                if column.foreign_keys:
                    for fk in column.foreign_keys:
                        related_tables.add(fk.column.table.name)
            
            # Buscar tablas que referencian esta tabla
            for other_table in metadata.tables.values():
                for column in other_table.columns:
                    if column.foreign_keys:
                        for fk in column.foreign_keys:
                            if fk.column.table.name == table_name:
                                related_tables.add(other_table.name)
            
            return list(related_tables)
            
        except Exception as e:
            logger.debug(f"[SchemaExplorerService] ⚠️ Error explorando relaciones de {table_name}: {e}")
            return []
    
    def _generate_schema_hash(self, tables: Dict[str, TableInfo]) -> str:
        """Generar hash del esquema para detectar cambios"""
        import hashlib
        import json
        
        # Crear representación serializable de las tablas
        schema_data = {}
        for table_name, table_info in tables.items():
            schema_data[table_name] = {
                "columns": {col.name: str(col.type) for col in table_info.columns.values()},
                "primary_keys": table_info.primary_keys,
                "foreign_keys": table_info.foreign_keys
            }
        
        schema_str = json.dumps(schema_data, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()
    
    def get_table_info(self, db_id: UUID, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información detallada de una tabla específica.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            
        Returns:
            Información detallada de la tabla o None si no existe
        """
        schema = self.detailed_cache.get_detailed_schema(db_id)
        if not schema:
            return None
        
        table_info = schema.tables.get(table_name)
        if not table_info:
            return None
        
        return {
            "name": table_info.name,
            "columns": {name: asdict(col) for name, col in table_info.columns.items()},
            "primary_keys": table_info.primary_keys,
            "foreign_keys": table_info.foreign_keys,
            "indexes": table_info.indexes,
            "row_count": table_info.row_count,
            "description": table_info.description
        }
    
    def validate_table_exists(self, db_id: UUID, table_name: str) -> bool:
        """
        Validar si una tabla existe en la base de datos.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            
        Returns:
            True si la tabla existe, False en caso contrario
        """
        schema = self.detailed_cache.get_detailed_schema(db_id)
        if not schema:
            return False
        
        return table_name in schema.tables
    
    def get_table_sample_data(self, db_id: UUID, table_name: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener datos de muestra de una tabla.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            limit: Número máximo de filas a obtener
            
        Returns:
            Lista de filas de muestra o None si hay error
        """
        try:
            db_instance = self.database_service.get_sql_instance(db_id)
            
            # Query para obtener datos de muestra
            query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
            result = db_instance.run(query)
            
            # Convertir a formato de diccionario
            if result and isinstance(result, list):
                return result
            else:
                return []
                
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error obteniendo datos de muestra de {table_name}: {e}")
            return None
    
    def refresh_schema_cache(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Forzar refresco del cache de esquema para una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            True si se refrescó correctamente, False en caso contrario
        """
        try:
            # Invalidar cache existente
            self.detailed_cache.invalidate_cache(db_id)
            
            # Explorar y cachear nuevo esquema
            schema = self._explore_single_db_detailed_schema(db_id)
            if schema:
                self.detailed_cache.cache_detailed_schema(db_id, schema)
                logger.info(f"[SchemaExplorerService] 🔄 Cache detallado refrescado: {len(schema.tables)} tablas en DB {db_id}")
                return True
            else:
                logger.warning(f"[SchemaExplorerService] ⚠️ No se pudieron explorar tablas en DB {db_id}")
                return False
                
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error refrescando cache para DB {db_id}: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache detallado"""
        return self.detailed_cache.get_cache_stats()
