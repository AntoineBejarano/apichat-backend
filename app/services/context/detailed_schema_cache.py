# app/services/detailed_schema_cache.py
"""
DetailedSchemaCache - Nivel Unicornio 🦄
─────────────────────────────────────────
Cache detallado de esquemas de base de datos con información completa:
- Columnas con tipos de datos
- Relaciones (FK, PK)
- Constraints e índices
- Optimizaciones de velocidad
- Cache inteligente por capas
"""

import json
import logging
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from uuid import UUID
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ColumnType(Enum):
    """Tipos de columnas para mapeo semántico"""
    LOCATION = "location"
    NAME = "name"
    IDENTIFIER = "identifier"
    TEXT = "text"
    NUMERIC = "numeric"
    DATE = "date"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


@dataclass
class ColumnInfo:
    """Información detallada de una columna"""
    name: str
    type: str
    nullable: bool
    default: Optional[str]
    primary_key: bool
    unique: bool
    foreign_key: Optional[str]
    referenced_table: Optional[str]
    referenced_column: Optional[str]
    semantic_type: ColumnType
    description: Optional[str] = None


@dataclass
class TableInfo:
    """Información detallada de una tabla"""
    name: str
    columns: Dict[str, ColumnInfo]
    primary_keys: List[str]
    foreign_keys: List[Dict[str, str]]
    indexes: List[Dict[str, Any]]
    row_count: Optional[int]
    description: Optional[str] = None


@dataclass
class DatabaseSchema:
    """Esquema completo de una base de datos"""
    db_id: UUID
    tables: Dict[str, TableInfo]
    relationships: Dict[str, List[str]]
    last_updated: datetime
    schema_hash: str
    version: str = "1.0"


class DetailedSchemaCache:
    """
    Cache detallado de nivel unicornio para esquemas de base de datos.
    Incluye información completa de columnas, relaciones y optimizaciones.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.detailed_cache_file = self.cache_dir / "detailed_schema_cache.json"
        self.cache_ttl_hours = 24
        
        # Cache por capas para optimización
        self.l1_cache = {}  # Cache en memoria (1 min TTL)
        self.l2_cache = {}  # Cache de queries frecuentes (5 min TTL)
        self.l3_cache = {}  # Cache persistente (24 horas TTL)
        
        # Estadísticas de performance
        self.stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0,
            "total_queries": 0
        }
        
        # Cargar cache existente
        self._load_detailed_cache()
        logger.info(f"[DetailedSchemaCache] 🦄 Inicializado con TTL={self.cache_ttl_hours}h")
    
    def _load_detailed_cache(self) -> None:
        """Cargar cache detallado desde archivo JSON"""
        try:
            if self.detailed_cache_file.exists():
                with open(self.detailed_cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.l3_cache = cache_data.get("schemas", {})
                    self.stats = cache_data.get("stats", self.stats)
                logger.info(f"[DetailedSchemaCache] 📂 Cache detallado cargado: {len(self.l3_cache)} DBs")
            else:
                self.l3_cache = {}
                logger.info("[DetailedSchemaCache] 🆕 Cache detallado inicializado")
        except Exception as e:
            logger.error(f"[DetailedSchemaCache] ❌ Error cargando cache: {e}")
            self.l3_cache = {}
    
    def _save_detailed_cache(self) -> None:
        """Guardar cache detallado a archivo JSON"""
        try:
            cache_data = {
                "schemas": self.l3_cache,
                "stats": self.stats,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.detailed_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, default=str)
            logger.debug("[DetailedSchemaCache] 💾 Cache detallado guardado")
        except Exception as e:
            logger.error(f"[DetailedSchemaCache] ❌ Error guardando cache: {e}")
    
    def _generate_schema_hash(self, schema: DatabaseSchema) -> str:
        """Generar hash único del esquema para detectar cambios"""
        schema_str = json.dumps(asdict(schema), sort_keys=True, default=str)
        return hashlib.sha256(schema_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Verificar si el cache es válido (no expirado)"""
        if not cache_entry:
            return False
        
        last_updated = cache_entry.get("last_updated")
        if not last_updated:
            return False
        
        # Convertir string a datetime si es necesario
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        
        # Verificar TTL
        ttl = timedelta(hours=self.cache_ttl_hours)
        return datetime.now(last_updated.tzinfo) - last_updated < ttl
    
    def _infer_semantic_type(self, column_name: str, column_type: str) -> ColumnType:
        """Inferir tipo semántico de una columna basado en nombre y tipo"""
        column_lower = column_name.lower()
        
        # Patrones de ubicación
        location_patterns = ['address', 'city', 'country', 'location', 'place', 'street', 'zip', 'postal']
        if any(pattern in column_lower for pattern in location_patterns):
            return ColumnType.LOCATION
        
        # Patrones de nombre
        name_patterns = ['name', 'title', 'label', 'description']
        if any(pattern in column_lower for pattern in name_patterns):
            return ColumnType.NAME
        
        # Patrones de identificador
        id_patterns = ['id', 'uuid', 'key', 'code']
        if any(pattern in column_lower for pattern in id_patterns):
            return ColumnType.IDENTIFIER
        
        # Patrones de fecha
        date_patterns = ['date', 'time', 'created', 'updated', 'timestamp']
        if any(pattern in column_lower for pattern in date_patterns):
            return ColumnType.DATE
        
        # Patrones numéricos
        numeric_patterns = ['count', 'number', 'amount', 'price', 'quantity', 'size']
        if any(pattern in column_lower for pattern in numeric_patterns):
            return ColumnType.NUMERIC
        
        # Patrones booleanos
        boolean_patterns = ['is_', 'has_', 'active', 'enabled', 'valid']
        if any(pattern in column_lower for pattern in boolean_patterns):
            return ColumnType.BOOLEAN
        
        # Patrones de texto
        text_patterns = ['text', 'content', 'message', 'comment', 'note']
        if any(pattern in column_lower for pattern in text_patterns):
            return ColumnType.TEXT
        
        return ColumnType.UNKNOWN
    
    def get_detailed_schema(self, db_id: UUID) -> Optional[DatabaseSchema]:
        """
        Obtener esquema detallado de una base de datos.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Esquema detallado si está cacheado y válido, None en caso contrario
        """
        start_time = datetime.now()
        db_key = str(db_id)
        
        # L1 Cache (más rápido)
        if db_key in self.l1_cache:
            cache_entry = self.l1_cache[db_key]
            if self._is_cache_valid(cache_entry):
                self.stats["cache_hits"] += 1
                response_time = (datetime.now() - start_time).total_seconds()
                self._update_stats(response_time)
                logger.info(f"[DetailedSchemaCache] ⚡ L1 Cache hit: {db_id}")
                return self._deserialize_schema(cache_entry["schema"])
        
        # L2 Cache
        if db_key in self.l2_cache:
            cache_entry = self.l2_cache[db_key]
            if self._is_cache_valid(cache_entry):
                self.stats["cache_hits"] += 1
                response_time = (datetime.now() - start_time).total_seconds()
                self._update_stats(response_time)
                logger.info(f"[DetailedSchemaCache] 🚀 L2 Cache hit: {db_id}")
                return self._deserialize_schema(cache_entry["schema"])
        
        # L3 Cache (persistente)
        if db_key in self.l3_cache:
            cache_entry = self.l3_cache[db_key]
            if self._is_cache_valid(cache_entry):
                self.stats["cache_hits"] += 1
                response_time = (datetime.now() - start_time).total_seconds()
                self._update_stats(response_time)
                logger.info(f"[DetailedSchemaCache] 💾 L3 Cache hit: {db_id}")
                return self._deserialize_schema(cache_entry["schema"])
        
        # Cache miss
        self.stats["cache_misses"] += 1
        response_time = (datetime.now() - start_time).total_seconds()
        self._update_stats(response_time)
        logger.info(f"[DetailedSchemaCache] ❌ Cache miss: {db_id}")
        return None
    
    def _deserialize_schema(self, schema_dict: Dict[str, Any]) -> DatabaseSchema:
        """Deserializar esquema desde diccionario"""
        # Convertir columnas
        tables = {}
        for table_name, table_dict in schema_dict.get("tables", {}).items():
            columns = {}
            for col_name, col_dict in table_dict.get("columns", {}).items():
                # Convertir semantic_type de string a enum
                semantic_type_str = col_dict.get("semantic_type", "unknown")
                semantic_type = ColumnType(semantic_type_str)
                
                columns[col_name] = ColumnInfo(
                    name=col_dict["name"],
                    type=col_dict["type"],
                    nullable=col_dict["nullable"],
                    default=col_dict["default"],
                    primary_key=col_dict["primary_key"],
                    unique=col_dict["unique"],
                    foreign_key=col_dict["foreign_key"],
                    referenced_table=col_dict["referenced_table"],
                    referenced_column=col_dict["referenced_column"],
                    semantic_type=semantic_type,
                    description=col_dict.get("description")
                )
            
            tables[table_name] = TableInfo(
                name=table_dict["name"],
                columns=columns,
                primary_keys=table_dict["primary_keys"],
                foreign_keys=table_dict["foreign_keys"],
                indexes=table_dict["indexes"],
                row_count=table_dict["row_count"],
                description=table_dict.get("description")
            )
        
        # Convertir last_updated de string a datetime
        last_updated_str = schema_dict.get("last_updated")
        if isinstance(last_updated_str, str):
            last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
        else:
            last_updated = datetime.now()
        
        return DatabaseSchema(
            db_id=UUID(schema_dict["db_id"]),
            tables=tables,
            relationships=schema_dict.get("relationships", {}),
            last_updated=last_updated,
            schema_hash=schema_dict["schema_hash"],
            version=schema_dict.get("version", "1.0")
        )
    
    def cache_detailed_schema(self, db_id: UUID, schema: DatabaseSchema) -> None:
        """
        Cachear esquema detallado de una base de datos.
        
        Args:
            db_id: ID de la base de datos
            schema: Esquema detallado
        """
        db_key = str(db_id)
        schema_dict = self._serialize_schema(schema)
        
        # Actualizar L1 cache (1 min TTL)
        self.l1_cache[db_key] = {
            "schema": schema_dict,
            "last_updated": datetime.now().isoformat(),
            "ttl_minutes": 1
        }
        
        # Actualizar L2 cache (5 min TTL)
        self.l2_cache[db_key] = {
            "schema": schema_dict,
            "last_updated": datetime.now().isoformat(),
            "ttl_minutes": 5
        }
        
        # Actualizar L3 cache (persistente)
        self.l3_cache[db_key] = {
            "schema": schema_dict,
            "last_updated": datetime.now().isoformat(),
            "ttl_hours": self.cache_ttl_hours
        }
        
        # Guardar cache persistente
        self._save_detailed_cache()
        
        logger.info(f"[DetailedSchemaCache] 💾 Esquema cacheado: {db_id} ({len(schema.tables)} tablas)")
    
    def _serialize_schema(self, schema: DatabaseSchema) -> Dict[str, Any]:
        """Serializar esquema a diccionario"""
        schema_dict = asdict(schema)
        
        # Convertir UUID a string
        schema_dict["db_id"] = str(schema.db_id)
        
        # Convertir columnas
        for table_name, table_info in schema_dict["tables"].items():
            for col_name, col_info in table_info["columns"].items():
                # Convertir semantic_type enum a string
                col_info["semantic_type"] = col_info["semantic_type"].value
        
        return schema_dict
    
    def get_schema_for_query(self, db_id: UUID, user_query: str) -> Optional[Dict[str, Any]]:
        """
        Obtener esquema optimizado para una query específica.
        
        Args:
            db_id: ID de la base de datos
            user_query: Query del usuario
            
        Returns:
            Esquema optimizado para la query
        """
        schema = self.get_detailed_schema(db_id)
        if not schema:
            return None
        
        # Analizar query del usuario
        query_analysis = self._analyze_user_query(user_query)
        
        # Optimizar esquema para la query
        optimized_schema = self._optimize_schema_for_query(schema, query_analysis)
        
        return optimized_schema
    
    def _analyze_user_query(self, query: str) -> Dict[str, Any]:
        """Analizar query del usuario para identificar patrones"""
        query_lower = query.lower()
        
        analysis = {
            "location_terms": [],
            "name_terms": [],
            "table_terms": [],
            "action_terms": []
        }
        
        # Buscar términos de ubicación
        location_terms = ['madrid', 'barcelona', 'valencia', 'address', 'city', 'country']
        analysis["location_terms"] = [term for term in location_terms if term in query_lower]
        
        # Buscar términos de nombre
        name_terms = ['valhalla', 'club', 'name', 'title']
        analysis["name_terms"] = [term for term in name_terms if term in query_lower]
        
        # Buscar términos de tabla
        table_terms = ['clubs', 'invitations', 'users', 'members']
        analysis["table_terms"] = [term for term in table_terms if term in query_lower]
        
        # Buscar términos de acción
        action_terms = ['count', 'find', 'show', 'list', 'get']
        analysis["action_terms"] = [term for term in action_terms if term in query_lower]
        
        return analysis
    
    def _optimize_schema_for_query(self, schema: DatabaseSchema, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Optimizar esquema para una query específica"""
        optimized_tables = {}
        
        for table_name, table_info in schema.tables.items():
            # Verificar si la tabla es relevante para la query
            if self._is_table_relevant(table_name, query_analysis):
                optimized_columns = {}
                
                for col_name, col_info in table_info.columns.items():
                    # Verificar si la columna es relevante para la query
                    if self._is_column_relevant(col_info, query_analysis):
                        optimized_columns[col_name] = asdict(col_info)
                
                if optimized_columns:
                    optimized_tables[table_name] = {
                        "columns": optimized_columns,
                        "primary_keys": table_info.primary_keys,
                        "foreign_keys": table_info.foreign_keys,
                        "description": table_info.description
                    }
        
        return {
            "db_id": str(schema.db_id),
            "tables": optimized_tables,
            "query_analysis": query_analysis,
            "optimization_notes": self._generate_optimization_notes(query_analysis)
        }
    
    def _is_table_relevant(self, table_name: str, query_analysis: Dict[str, Any]) -> bool:
        """Verificar si una tabla es relevante para la query"""
        table_lower = table_name.lower()
        
        # Verificar términos de tabla en la query
        for term in query_analysis["table_terms"]:
            if term in table_lower:
                return True
        
        # Verificar términos de nombre
        for term in query_analysis["name_terms"]:
            if term in table_lower:
                return True
        
        return True  # Por defecto incluir todas las tablas
    
    def _is_column_relevant(self, column_info: ColumnInfo, query_analysis: Dict[str, Any]) -> bool:
        """Verificar si una columna es relevante para la query"""
        col_name_lower = column_info.name.lower()
        
        # Verificar términos de ubicación
        for term in query_analysis["location_terms"]:
            if term in col_name_lower or column_info.semantic_type == ColumnType.LOCATION:
                return True
        
        # Verificar términos de nombre
        for term in query_analysis["name_terms"]:
            if term in col_name_lower or column_info.semantic_type == ColumnType.NAME:
                return True
        
        # Siempre incluir primary keys y foreign keys
        if column_info.primary_key or column_info.foreign_key:
            return True
        
        return True  # Por defecto incluir todas las columnas
    
    def _generate_optimization_notes(self, query_analysis: Dict[str, Any]) -> List[str]:
        """Generar notas de optimización para la query"""
        notes = []
        
        if query_analysis["location_terms"]:
            notes.append(f"📍 Términos de ubicación detectados: {query_analysis['location_terms']}")
        
        if query_analysis["name_terms"]:
            notes.append(f"🏷️ Términos de nombre detectados: {query_analysis['name_terms']}")
        
        if query_analysis["table_terms"]:
            notes.append(f"📋 Tablas mencionadas: {query_analysis['table_terms']}")
        
        if query_analysis["action_terms"]:
            notes.append(f"⚡ Acciones detectadas: {query_analysis['action_terms']}")
        
        return notes
    
    def _update_stats(self, response_time: float) -> None:
        """Actualizar estadísticas de performance"""
        self.stats["total_queries"] += 1
        
        # Calcular tiempo promedio de respuesta
        current_avg = self.stats["avg_response_time"]
        total_queries = self.stats["total_queries"]
        
        self.stats["avg_response_time"] = (
            (current_avg * (total_queries - 1) + response_time) / total_queries
        )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        return {
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "hit_rate": self.stats["cache_hits"] / max(self.stats["total_queries"], 1),
            "avg_response_time": self.stats["avg_response_time"],
            "total_queries": self.stats["total_queries"],
            "l1_cache_size": len(self.l1_cache),
            "l2_cache_size": len(self.l2_cache),
            "l3_cache_size": len(self.l3_cache)
        }
    
    def invalidate_cache(self, db_id: UUID) -> None:
        """Invalidar cache de una base de datos"""
        db_key = str(db_id)
        
        # Limpiar todos los niveles de cache
        self.l1_cache.pop(db_key, None)
        self.l2_cache.pop(db_key, None)
        self.l3_cache.pop(db_key, None)
        
        # Guardar cache actualizado
        self._save_detailed_cache()
        
        logger.info(f"[DetailedSchemaCache] 🗑️ Cache invalidado: {db_id}")
    
    def clear_all_cache(self) -> None:
        """Limpiar todo el cache"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.l3_cache.clear()
        self._save_detailed_cache()
        
        logger.info("[DetailedSchemaCache] 🧹 Todo el cache limpiado")
