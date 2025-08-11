# app/services/schema_explorer_service.py
"""
SchemaExplorerService - Nivel Unicornio 🦄
───────────────────────────────────────────
Servicio para explorar y cachear esquemas de base de datos con información completa.
Integra con DetailedSchemaCache para mantener esquemas detallados actualizados.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from sqlalchemy import inspect, text, MetaData
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from dataclasses import asdict

from app.services.data.cache_service import CacheService
from app.services.data.database_service import DatabaseService
from app.core.config import settings
from .detailed_schema_cache import DetailedSchemaCache, DatabaseSchema, TableInfo, ColumnInfo, ColumnType

logger = logging.getLogger(__name__)


class SchemaExplorerService:
    """
    Servicio para explorar y cachear esquemas de base de datos con información completa.
    """
    
    def __init__(self, cache_service: CacheService, database_service: DatabaseService):
        self.cache_service = cache_service
        self.database_service = database_service
        self.detailed_cache = DetailedSchemaCache()
        
        # Umbrales para Fast Schema Path (Fase 7) desde configuración
        self.CONF_FAST = settings.CONF_FAST
        self.CONF_AMBIGUOUS = settings.CONF_AMBIGUOUS
        self.FAST_PATH_RESPONSE_TIME_MS = settings.FAST_PATH_RESPONSE_TIME_MS
        
        # Índices léxicos para búsqueda rápida
        self._lexical_indexes = {}  # {db_id: {term: [(table, column, score)]}}
        
        logger.info(f"[SchemaExplorerService] 🦄 Inicializado con Fast Schema Path (CONF_FAST={self.CONF_FAST})")
    
    def fast_lookup(
        self, 
        query: str, 
        db_ids: List[UUID]
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """
        Fast Schema Path: búsqueda rápida sin LLM usando índices léxicos.
        
        Args:
            query: Consulta del usuario (ej: "¿dónde está el campo email?")
            db_ids: Lista de IDs de bases de datos a buscar
            
        Returns:
            Tuple: (resultado, confianza, tipo_respuesta)
            - resultado: Dict con matches encontrados o None
            - confianza: Score de confianza (0.0 - 1.0)
            - tipo_respuesta: "fast", "ambiguous", "fallback"
        """
        try:
            logger.info(f"[SchemaExplorerService] 🚀 Fast lookup para: '{query}' en {len(db_ids)} DBs")
            
            # 1. Normalizar y tokenizar la query
            normalized_query = self._normalize_query(query)
            query_terms = self._extract_search_terms(normalized_query)
            
            if not query_terms:
                logger.info("[SchemaExplorerService] ⚠️ No se pudieron extraer términos de búsqueda")
                return None, 0.0, "fallback"
            
            # 2. Buscar en índices léxicos
            all_matches = []
            total_score = 0.0
            
            for db_id in db_ids:
                # Asegurar que el índice léxico esté construido
                if db_id not in self._lexical_indexes:
                    self._build_lexical_index(db_id)
                
                # Buscar matches en este DB
                db_matches = self._search_lexical_index(db_id, query_terms)
                if db_matches:
                    all_matches.extend(db_matches)
                    total_score += sum(match['score'] for match in db_matches)
            
            if not all_matches:
                logger.info("[SchemaExplorerService] ⚠️ No se encontraron matches en índices léxicos")
                return None, 0.0, "fallback"
            
            # 3. Calcular confianza y determinar tipo de respuesta
            avg_confidence = total_score / len(all_matches)
            confidence = min(avg_confidence, 1.0)  # Cap en 1.0
            
            # 4. Determinar tipo de respuesta según umbrales
            if confidence >= self.CONF_FAST:
                response_type = "fast"
                result = self._format_fast_response(all_matches, confidence)
                logger.info(f"[SchemaExplorerService] ✅ Fast response con confianza {confidence:.2f}")
                
            elif confidence >= self.CONF_AMBIGUOUS:
                response_type = "ambiguous"
                result = self._format_ambiguous_response(all_matches, confidence)
                logger.info(f"[SchemaExplorerService] 🤔 Respuesta ambigua con confianza {confidence:.2f}")
                
            else:
                response_type = "fallback"
                result = None
                logger.info(f"[SchemaExplorerService] 📉 Fallback LLM con confianza {confidence:.2f}")
            
            return result, confidence, response_type
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error en fast_lookup: {e}")
            return None, 0.0, "fallback"
    
    def _normalize_query(self, query: str) -> str:
        """Normalizar query para búsqueda léxica"""
        # Convertir a minúsculas y remover caracteres especiales
        normalized = query.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _extract_search_terms(self, normalized_query: str) -> List[str]:
        """Extraer términos de búsqueda relevantes"""
        # Palabras clave comunes en consultas de esquema
        schema_keywords = {
            'tabla', 'table', 'columna', 'column', 'campo', 'field',
            'donde', 'where', 'esta', 'is', 'find', 'buscar', 'search',
            'email', 'user', 'usuario', 'id', 'name', 'nombre', 'date', 'fecha'
        }
        
        # Filtrar palabras comunes y muy cortas
        words = normalized_query.split()
        terms = [word for word in words if len(word) >= 3 and word not in schema_keywords]
        
        # Si no hay términos específicos, usar palabras más largas
        if not terms:
            terms = [word for word in words if len(word) >= 4]
        
        return terms[:5]  # Máximo 5 términos
    
    def _build_lexical_index(self, db_id: UUID) -> None:
        """Construir índice léxico para una base de datos"""
        try:
            logger.info(f"[SchemaExplorerService] 🔨 Construyendo índice léxico para DB {db_id}")
            
            # Obtener esquema detallado
            schema = self.detailed_cache.get_detailed_schema(db_id)
            if not schema:
                logger.warning(f"[SchemaExplorerService] ⚠️ No se pudo obtener esquema para DB {db_id}")
                return
            
            # Inicializar índice para este DB
            self._lexical_indexes[db_id] = {}
            
            # Indexar tablas y columnas
            for table_name, table_info in schema.tables.items():
                # Indexar nombre de tabla
                self._index_term(db_id, table_name, table_name, "table", 1.0)
                
                # Indexar columnas
                for col_name, col_info in table_info.columns.items():
                    # Indexar nombre de columna
                    self._index_term(db_id, col_name, table_name, "column", 0.9)
                    
                    # Indexar tipo de columna
                    if col_info.semantic_type:
                        self._index_term(db_id, col_info.semantic_type, table_name, "semantic_type", 0.7)
                    
                    # Indexar comentarios/descripciones si existen
                    if col_info.description:
                        self._index_term(db_id, col_info.description, table_name, "description", 0.6)
            
            logger.info(f"[SchemaExplorerService] ✅ Índice léxico construido para DB {db_id}: {len(self._lexical_indexes[db_id])} términos")
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error construyendo índice léxico para DB {db_id}: {e}")
    
    def _index_term(self, db_id: UUID, term: str, table_name: str, term_type: str, base_score: float) -> None:
        """Indexar un término en el índice léxico"""
        if not term:
            return
        
        # Normalizar término
        normalized_term = self._normalize_query(term)
        if not normalized_term:
            return
        
        # Generar trigrams para búsqueda fuzzy
        trigrams = self._generate_trigrams(normalized_term)
        
        for trigram in trigrams:
            if trigram not in self._lexical_indexes[db_id]:
                self._lexical_indexes[db_id][trigram] = []
            
            # Añadir entrada al índice
            entry = {
                'table': table_name,
                'column': table_name if term_type == "table" else None,
                'term_type': term_type,
                'original_term': term,
                'score': base_score,
                'trigram': trigram
            }
            
            self._lexical_indexes[db_id][trigram].append(entry)
    
    def _generate_trigrams(self, text: str) -> List[str]:
        """Generar trigrams para búsqueda fuzzy"""
        if len(text) < 3:
            return [text]
        
        trigrams = []
        for i in range(len(text) - 2):
            trigrams.append(text[i:i+3])
        
        return trigrams
    
    def _search_lexical_index(self, db_id: UUID, query_terms: List[str]) -> List[Dict[str, Any]]:
        """Buscar términos en el índice léxico"""
        if db_id not in self._lexical_indexes:
            return []
        
        matches = []
        
        for term in query_terms:
            # Generar trigrams del término de búsqueda
            term_trigrams = self._generate_trigrams(term)
            
            for trigram in term_trigrams:
                if trigram in self._lexical_indexes[db_id]:
                    # Añadir todos los matches para este trigram
                    for entry in self._lexical_indexes[db_id][trigram]:
                        # Calcular score de match
                        match_score = self._calculate_match_score(term, entry)
                        if match_score > 0:
                            match_entry = entry.copy()
                            match_entry['score'] = match_score
                            match_entry['db_id'] = db_id
                            matches.append(match_entry)
        
        # Remover duplicados y ordenar por score
        unique_matches = {}
        for match in matches:
            key = (match['table'], match.get('column'), match['db_id'])
            if key not in unique_matches or match['score'] > unique_matches[key]['score']:
                unique_matches[key] = match
        
        # Ordenar por score descendente
        sorted_matches = sorted(unique_matches.values(), key=lambda x: x['score'], reverse=True)
        
        return sorted_matches[:10]  # Top 10 matches
    
    def _calculate_match_score(self, query_term: str, index_entry: Dict[str, Any]) -> float:
        """Calcular score de match entre término de búsqueda y entrada del índice"""
        original_term = index_entry['original_term'].lower()
        base_score = index_entry['score']
        
        # Score por tipo de término
        type_bonus = {
            "table": 1.0,
            "column": 0.9,
            "semantic_type": 0.7,
            "description": 0.6
        }
        
        type_score = type_bonus.get(index_entry['term_type'], 0.5)
        
        # Score por exactitud del match
        if query_term == original_term:
            exact_match = 1.0
        elif query_term in original_term:
            exact_match = 0.8
        elif original_term in query_term:
            exact_match = 0.7
        else:
            # Búsqueda fuzzy con trigrams
            query_trigrams = set(self._generate_trigrams(query_term))
            entry_trigrams = set(self._generate_trigrams(original_term))
            
            if query_trigrams and entry_trigrams:
                intersection = len(query_trigrams & entry_trigrams)
                union = len(query_trigrams | entry_trigrams)
                exact_match = intersection / union if union > 0 else 0.0
            else:
                exact_match = 0.0
        
        # Score final combinado
        final_score = base_score * type_score * exact_match
        return min(final_score, 1.0)
    
    def _format_fast_response(self, matches: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
        """Formatear respuesta rápida para alta confianza"""
        # Agrupar por tabla
        tables = {}
        for match in matches:
            table_name = match['table']
            if table_name not in tables:
                tables[table_name] = {
                    'name': table_name,
                    'db_id': match['db_id'],
                    'columns': [],
                    'score': 0.0
                }
            
            if match.get('column') and match['column'] != table_name:
                tables[table_name]['columns'].append({
                    'name': match['column'],
                    'type': match['term_type'],
                    'score': match['score']
                })
            
            tables[table_name]['score'] = max(tables[table_name]['score'], match['score'])
        
        # Ordenar tablas por score
        sorted_tables = sorted(tables.values(), key=lambda x: x['score'], reverse=True)
        
        return {
            'type': 'fast_schema_lookup',
            'confidence': confidence,
            'response_time_ms': self.FAST_PATH_RESPONSE_TIME_MS,  # Usar configuración
            'tables': sorted_tables[:5],  # Top 5 tablas
            'total_matches': len(matches),
            'message': f"Encontré {len(sorted_tables)} tablas relevantes con confianza {confidence:.1%}"
        }
    
    def _format_ambiguous_response(self, matches: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
        """Formatear respuesta para confianza ambigua (requiere desambiguación)"""
        # Similar a fast_response pero con mensaje de desambiguación
        fast_response = self._format_fast_response(matches, confidence)
        fast_response['type'] = 'ambiguous_schema_lookup'
        fast_response['message'] = f"Encontré {len(fast_response['tables'])} posibles coincidencias. ¿Podrías ser más específico?"
        fast_response['requires_disambiguation'] = True
        
        return fast_response
    
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
        
        schema_str = json.dumps(schema_data, sort_keys=True, default=str)
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
