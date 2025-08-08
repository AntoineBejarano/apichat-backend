# app/services/vector_search_service.py
"""
VectorSearchService - Nivel Unicornio 🦄
─────────────────────────────────────────
Servicio de búsqueda vectorial para esquemas de base de datos.
Combina embeddings de OpenAI con búsqueda semántica inteligente.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
import numpy as np
from datetime import datetime

# LangChain imports
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

logger = logging.getLogger(__name__)


@dataclass
class SchemaEmbedding:
    """Embedding de un elemento del esquema"""
    id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    semantic_type: str
    relevance_score: float = 0.0


@dataclass
class SearchResult:
    """Resultado de búsqueda vectorial"""
    element_id: str
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    semantic_type: str
    relevance_boost: float = 1.0


class VectorSearchService:
    """
    Servicio de búsqueda vectorial para esquemas de base de datos.
    Utiliza OpenAI embeddings y Chroma para búsqueda semántica.
    """
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key
        self.embeddings = OpenAIEmbeddings(api_key=openai_api_key)
        self.vector_stores = {}  # Por base de datos
        self.embedding_cache = {}  # Cache de embeddings
        self.search_stats = {
            "total_searches": 0,
            "avg_response_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        logger.info("[VectorSearchService] 🦄 Inicializado con OpenAI embeddings")
    
    async def create_schema_embeddings(
        self, 
        db_id: UUID, 
        schema_data: Dict[str, Any]
    ) -> Dict[str, List[float]]:
        """
        Crear embeddings para todos los elementos del esquema.
        
        Args:
            db_id: ID de la base de datos
            schema_data: Datos del esquema
            
        Returns:
            Diccionario con embeddings: {element_id: embedding}
        """
        start_time = datetime.now()
        embeddings = {}
        
        try:
            # Procesar tablas
            for table_name, table_info in schema_data.get("tables", {}).items():
                # Embedding para tabla
                table_content = self._build_table_content(table_name, table_info)
                table_embedding = await self._get_embedding(table_content)
                embeddings[f"table_{table_name}"] = table_embedding
                
                # Embeddings para columnas
                for col_name, col_info in table_info.get("columns", {}).items():
                    col_content = self._build_column_content(table_name, col_name, col_info)
                    col_embedding = await self._get_embedding(col_content)
                    embeddings[f"column_{table_name}_{col_name}"] = col_embedding
                
                # Embeddings para relaciones
                for fk in table_info.get("foreign_keys", []):
                    fk_content = self._build_foreign_key_content(table_name, fk)
                    fk_embedding = await self._get_embedding(fk_content)
                    embeddings[f"fk_{table_name}_{fk['column']}"] = fk_embedding
            
            # Cachear embeddings
            self.embedding_cache[str(db_id)] = embeddings
            
            response_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[VectorSearchService] 💾 Embeddings creados: {len(embeddings)} elementos en {response_time:.2f}s")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"[VectorSearchService] ❌ Error creando embeddings: {e}")
            return {}
    
    def _build_table_content(self, table_name: str, table_info: Dict[str, Any]) -> str:
        """Construir contenido para embedding de tabla"""
        columns = table_info.get("columns", {})
        primary_keys = table_info.get("primary_keys", [])
        foreign_keys = table_info.get("foreign_keys", [])
        
        content_parts = [
            f"Table: {table_name}",
            f"Columns: {', '.join(columns.keys())}",
            f"Primary keys: {', '.join(primary_keys)}",
            f"Foreign keys: {len(foreign_keys)}"
        ]
        
        # Agregar información de columnas
        for col_name, col_info in columns.items():
            col_type = col_info.get("type", "unknown")
            semantic_type = col_info.get("semantic_type", "unknown")
            content_parts.append(f"Column {col_name}: {col_type} ({semantic_type})")
        
        return " | ".join(content_parts)
    
    def _build_column_content(self, table_name: str, col_name: str, col_info: Dict[str, Any]) -> str:
        """Construir contenido para embedding de columna"""
        col_type = col_info.get("type", "unknown")
        semantic_type = col_info.get("semantic_type", "unknown")
        nullable = col_info.get("nullable", True)
        primary_key = col_info.get("primary_key", False)
        unique = col_info.get("unique", False)
        
        content_parts = [
            f"Column: {col_name}",
            f"Table: {table_name}",
            f"Type: {col_type}",
            f"Semantic: {semantic_type}"
        ]
        
        if primary_key:
            content_parts.append("Primary key")
        if unique:
            content_parts.append("Unique")
        if not nullable:
            content_parts.append("Not null")
        
        return " | ".join(content_parts)
    
    def _build_foreign_key_content(self, table_name: str, fk_info: Dict[str, str]) -> str:
        """Construir contenido para embedding de foreign key"""
        column = fk_info.get("column", "")
        referenced_table = fk_info.get("referenced_table", "")
        referenced_column = fk_info.get("referenced_column", "")
        
        return f"Foreign key: {table_name}.{column} -> {referenced_table}.{referenced_column}"
    
    async def _get_embedding(self, content: str) -> List[float]:
        """Obtener embedding para un contenido específico"""
        try:
            # Cache simple de embeddings
            if content in self.embedding_cache:
                return self.embedding_cache[content]
            
            # Obtener embedding de OpenAI
            embedding = await self.embeddings.aembed_query(content)
            
            # Cachear
            self.embedding_cache[content] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"[VectorSearchService] ❌ Error obteniendo embedding: {e}")
            return []
    
    async def semantic_search(
        self, 
        db_id: UUID, 
        query: str, 
        top_k: int = 10
    ) -> List[SearchResult]:
        """
        Búsqueda semántica en el esquema.
        
        Args:
            db_id: ID de la base de datos
            query: Query del usuario
            top_k: Número máximo de resultados
            
        Returns:
            Lista de resultados ordenados por relevancia
        """
        start_time = datetime.now()
        
        try:
            # Obtener embeddings del cache
            embeddings = self.embedding_cache.get(str(db_id), {})
            if not embeddings:
                logger.warning(f"[VectorSearchService] ⚠️ No hay embeddings para DB {db_id}")
                return []
            
            # Obtener embedding de la query
            query_embedding = await self._get_embedding(query)
            if not query_embedding:
                return []
            
            # Calcular similitudes
            results = []
            for element_id, element_embedding in embeddings.items():
                similarity = self._cosine_similarity(query_embedding, element_embedding)
                
                # Boost semántico basado en el tipo de elemento
                relevance_boost = self._calculate_relevance_boost(element_id, query)
                
                result = SearchResult(
                    element_id=element_id,
                    content=self._get_element_content(element_id, embeddings),
                    similarity_score=similarity,
                    metadata=self._extract_metadata(element_id),
                    semantic_type=self._extract_semantic_type(element_id),
                    relevance_boost=relevance_boost
                )
                results.append(result)
            
            # Ordenar por score final (similarity * boost)
            results.sort(key=lambda x: x.similarity_score * x.relevance_boost, reverse=True)
            
            # Limitar resultados
            results = results[:top_k]
            
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_stats(response_time)
            
            logger.info(f"[VectorSearchService] 🔍 Búsqueda completada: {len(results)} resultados en {response_time:.2f}s")
            
            return results
            
        except Exception as e:
            logger.error(f"[VectorSearchService] ❌ Error en búsqueda semántica: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcular similitud coseno entre dos vectores"""
        try:
            vec1_array = np.array(vec1)
            vec2_array = np.array(vec2)
            
            dot_product = np.dot(vec1_array, vec2_array)
            norm1 = np.linalg.norm(vec1_array)
            norm2 = np.linalg.norm(vec2_array)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
            
        except Exception as e:
            logger.error(f"[VectorSearchService] ❌ Error calculando similitud: {e}")
            return 0.0
    
    def _calculate_relevance_boost(self, element_id: str, query: str) -> float:
        """Calcular boost de relevancia basado en el tipo de elemento"""
        query_lower = query.lower()
        boost = 1.0
        
        # Boost para tablas mencionadas
        if "table_" in element_id:
            table_name = element_id.replace("table_", "")
            if table_name.lower() in query_lower:
                boost *= 1.5
        
        # Boost para columnas de ubicación
        if "column_" in element_id and any(term in query_lower for term in ["madrid", "barcelona", "address", "city"]):
            if "address" in element_id or "city" in element_id:
                boost *= 2.0
        
        # Boost para columnas de nombre
        if "column_" in element_id and any(term in query_lower for term in ["name", "title", "valhalla"]):
            if "name" in element_id:
                boost *= 1.8
        
        # Boost para primary keys
        if "column_" in element_id and "id" in element_id:
            boost *= 1.3
        
        return boost
    
    def _get_element_content(self, element_id: str, embeddings: Dict[str, List[float]]) -> str:
        """Obtener contenido de un elemento"""
        # Esto sería reemplazado por el contenido real del elemento
        return f"Content for {element_id}"
    
    def _extract_metadata(self, element_id: str) -> Dict[str, Any]:
        """Extraer metadata de un elemento"""
        metadata = {"element_id": element_id}
        
        if "table_" in element_id:
            metadata["type"] = "table"
            metadata["table_name"] = element_id.replace("table_", "")
        elif "column_" in element_id:
            metadata["type"] = "column"
            parts = element_id.replace("column_", "").split("_", 1)
            if len(parts) == 2:
                metadata["table_name"] = parts[0]
                metadata["column_name"] = parts[1]
        elif "fk_" in element_id:
            metadata["type"] = "foreign_key"
        
        return metadata
    
    def _extract_semantic_type(self, element_id: str) -> str:
        """Extraer tipo semántico de un elemento"""
        if "table_" in element_id:
            return "table"
        elif "column_" in element_id:
            # Inferir tipo semántico basado en el nombre
            if "name" in element_id:
                return "name"
            elif "address" in element_id or "city" in element_id:
                return "location"
            elif "id" in element_id:
                return "identifier"
            else:
                return "unknown"
        elif "fk_" in element_id:
            return "relationship"
        else:
            return "unknown"
    
    def _update_stats(self, response_time: float) -> None:
        """Actualizar estadísticas de performance"""
        self.search_stats["total_searches"] += 1
        
        # Calcular tiempo promedio de respuesta
        current_avg = self.search_stats["avg_response_time"]
        total_searches = self.search_stats["total_searches"]
        
        self.search_stats["avg_response_time"] = (
            (current_avg * (total_searches - 1) + response_time) / total_searches
        )
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de búsqueda"""
        return {
            "total_searches": self.search_stats["total_searches"],
            "avg_response_time": self.search_stats["avg_response_time"],
            "cache_hits": self.search_stats["cache_hits"],
            "cache_misses": self.search_stats["cache_misses"],
            "embedding_cache_size": len(self.embedding_cache),
            "vector_stores_count": len(self.vector_stores)
        }
    
    def clear_cache(self, db_id: Optional[UUID] = None) -> None:
        """Limpiar cache de embeddings"""
        if db_id:
            self.embedding_cache.pop(str(db_id), None)
            logger.info(f"[VectorSearchService] 🗑️ Cache limpiado para DB {db_id}")
        else:
            self.embedding_cache.clear()
            logger.info("[VectorSearchService] 🧹 Todo el cache limpiado")
