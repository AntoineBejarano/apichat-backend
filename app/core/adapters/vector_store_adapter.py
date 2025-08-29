#!/usr/bin/env python3
"""
Vector Store Adapter - Adapter multi-driver para vector stores
────────────────────────────────────────────────────────────────
Implementa la Fase 4 del plan de refactorización:
- Soporte para múltiples drivers (pgvector, qdrant, weaviate, pinecone, opensearch)
- Namespace management por tenant/app/db/snapshot
- Batching controlado
- vector_upsert idempotente
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
from uuid import UUID

from .base_adapter import BaseAdapter, AdapterType, AdapterConfig


@dataclass
class VectorStoreConfig(AdapterConfig):
    """Configuración específica para vector stores"""
    index_name: str = "default"
    dimensions: int = 1536
    distance_metric: str = "cosine"  # cosine, euclidean, dot
    max_top_k: int = 100
    namespace_strategy: str = "tenant_app_db_snapshot"


@dataclass
class VectorDocument:
    """Documento vectorizado para almacenar"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: List[float]
    namespace: str


@dataclass
class SearchResult:
    """Resultado de búsqueda vectorial"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    namespace: str


class VectorStoreAdapter(BaseAdapter):
    """
    🔧 Vector Store Adapter multi-driver
    
    Responsabilidades:
    - Almacenar y buscar embeddings
    - Soporte para múltiples drivers
    - Namespace management
    - Batching automático
    """
    
    def __init__(self, config: Optional[VectorStoreConfig] = None):
        # 🔧 FASE 4: Configuración por ENV
        if config is None:
            config = self._load_config_from_env()
        
        super().__init__(AdapterType.VECTOR_STORE, config)
        self.vector_config = config
        
        # 🔧 FASE 4: Configuración de búsqueda
        self.max_top_k = int(self._get_env_config("MAX_TOPK_VECTOR", config.max_top_k))
        self.distance_metric = self._get_env_config("DISTANCE_METRIC", config.distance_metric)
        
        # Inicializar driver específico
        self.driver = self._initialize_driver()
        
        self._log_operation("VectorStoreAdapter inicializado", 
                           provider=config.provider, 
                           index_name=config.index_name,
                           dimensions=config.dimensions)
    
    def _load_config_from_env(self) -> VectorStoreConfig:
        """Cargar configuración desde variables de entorno"""
        return VectorStoreConfig(
            provider=os.getenv("VECTOR_PROVIDER", "pgvector"),
            url=os.getenv("VECTOR_URL"),
            api_key=os.getenv("VECTOR_API_KEY"),
            timeout=int(os.getenv("VECTOR_TIMEOUT", "30")),
            max_retries=int(os.getenv("VECTOR_MAX_RETRIES", "3")),
            batch_size=int(os.getenv("VECTOR_BATCH_SIZE", "100")),
            index_name=os.getenv("VECTOR_INDEX", "default"),
            dimensions=int(os.getenv("VECTOR_DIM", "1536")),
            distance_metric=os.getenv("VECTOR_DISTANCE_METRIC", "cosine"),
            max_top_k=int(os.getenv("MAX_TOPK_VECTOR", "100")),
            namespace_strategy=os.getenv("VECTOR_NAMESPACE_STRATEGY", "tenant_app_db_snapshot")
        )
    
    def _initialize_driver(self):
        """Inicializar el driver específico del vector store"""
        provider_name = self.vector_config.provider.lower()
        
        try:
            if provider_name == "pgvector":
                return self._init_pgvector_driver()
            elif provider_name == "qdrant":
                return self._init_qdrant_driver()
            elif provider_name == "weaviate":
                return self._init_weaviate_driver()
            elif provider_name == "pinecone":
                return self._init_pinecone_driver()
            elif provider_name == "opensearch":
                return self._init_opensearch_driver()
            else:
                raise ValueError(f"Driver de vector store no soportado: {provider_name}")
        except Exception as e:
            self._log_error("Inicialización de driver", e, provider=provider_name)
            raise
    
    def _init_pgvector_driver(self):
        """Inicializar driver pgvector"""
        try:
            import psycopg2
            from pgvector.psycopg2 import register_vector
            
            # Conectar a PostgreSQL
            conn = psycopg2.connect(self.vector_config.url)
            register_vector(conn)
            
            # Crear extensión pgvector si no existe
            with conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Crear tabla de embeddings si no existe
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        embedding vector(%s),
                        namespace TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """, (self.vector_config.dimensions,))
                
                # Crear índice vectorial
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_namespace 
                    ON embeddings(namespace)
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embeddings_vector 
                    ON embeddings 
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
            
            conn.commit()
            conn.close()
            
            self._log_operation("Driver pgvector inicializado correctamente")
            return {"type": "pgvector", "url": self.vector_config.url}
            
        except ImportError:
            raise ImportError("pgvector package no instalado. Instalar con: pip install pgvector psycopg2-binary")
        except Exception as e:
            raise Exception(f"Error inicializando pgvector: {e}")
    
    def _init_qdrant_driver(self):
        """Inicializar driver Qdrant"""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
            
            # Conectar a Qdrant
            if self.vector_config.url.startswith("http"):
                client = QdrantClient(url=self.vector_config.url, api_key=self.vector_config.api_key)
            else:
                client = QdrantClient(path=self.vector_config.url)
            
            # Crear colección si no existe
            collections = client.get_collections()
            if self.vector_config.index_name not in [c.name for c in collections.collections]:
                client.create_collection(
                    collection_name=self.vector_config.index_name,
                    vectors_config=VectorParams(
                        size=self.vector_config.dimensions,
                        distance=Distance.COSINE if self.distance_metric == "cosine" else Distance.EUCLIDEAN
                    )
                )
            
            self._log_operation("Driver Qdrant inicializado correctamente")
            return {"type": "qdrant", "client": client, "collection": self.vector_config.index_name}
            
        except ImportError:
            raise ImportError("qdrant-client package no instalado. Instalar con: pip install qdrant-client")
        except Exception as e:
            raise Exception(f"Error inicializando Qdrant: {e}")
    
    def _init_weaviate_driver(self):
        """Inicializar driver Weaviate"""
        try:
            import weaviate
            
            # Conectar a Weaviate
            client = weaviate.Client(
                url=self.vector_config.url,
                auth_client_secret=weaviate.Auth.api_key(self.vector_config.api_key) if self.vector_config.api_key else None
            )
            
            # Crear clase si no existe
            class_obj = {
                "class": self.vector_config.index_name,
                "vectorizer": "none",  # Usaremos embeddings pre-generados
                "properties": [
                    {"name": "content", "dataType": ["text"]},
                    {"name": "metadata", "dataType": ["text"]},
                    {"name": "namespace", "dataType": ["text"]}
                ]
            }
            
            try:
                client.schema.create_class(class_obj)
            except:
                pass  # La clase ya existe
            
            self._log_operation("Driver Weaviate inicializado correctamente")
            return {"type": "weaviate", "client": client, "class": self.vector_config.index_name}
            
        except ImportError:
            raise ImportError("weaviate-client package no instalado. Instalar con: pip install weaviate-client")
        except Exception as e:
            raise Exception(f"Error inicializando Weaviate: {e}")
    
    def _init_pinecone_driver(self):
        """Inicializar driver Pinecone"""
        try:
            import pinecone
            
            # Inicializar Pinecone
            pinecone.init(api_key=self.vector_config.api_key, environment=self.vector_config.url)
            
            # Crear índice si no existe
            if self.vector_config.index_name not in pinecone.list_indexes():
                pinecone.create_index(
                    name=self.vector_config.index_name,
                    dimension=self.vector_config.dimensions,
                    metric="cosine" if self.distance_metric == "cosine" else "euclidean"
                )
            
            # Conectar al índice
            index = pinecone.Index(self.vector_config.index_name)
            
            self._log_operation("Driver Pinecone inicializado correctamente")
            return {"type": "pinecone", "index": index}
            
        except ImportError:
            raise ImportError("pinecone-client package no instalado. Instalar con: pip install pinecone-client")
        except Exception as e:
            raise Exception(f"Error inicializando Pinecone: {e}")
    
    def _init_opensearch_driver(self):
        """Inicializar driver OpenSearch"""
        try:
            from opensearchpy import OpenSearch
            
            # Conectar a OpenSearch
            client = OpenSearch(
                hosts=[self.vector_config.url],
                http_auth=("admin", self.vector_config.api_key) if self.vector_config.api_key else None,
                use_ssl=True,
                verify_certs=False,
                ssl_show_warn=False
            )
            
            # Crear índice si no existe
            index_name = self.vector_config.index_name
            if not client.indices.exists(index=index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "content": {"type": "text"},
                            "metadata": {"type": "object"},
                            "namespace": {"type": "keyword"},
                            "embedding": {
                                "type": "knn_vector",
                                "dimension": self.vector_config.dimensions,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil" if self.distance_metric == "cosine" else "l2"
                                }
                            }
                        }
                    }
                }
                client.indices.create(index=index_name, body=mapping)
            
            self._log_operation("Driver OpenSearch inicializado correctamente")
            return {"type": "opensearch", "client": client, "index": index_name}
            
        except ImportError:
            raise ImportError("opensearch-py package no instalado. Instalar con: pip install opensearch-py")
        except Exception as e:
            raise Exception(f"Error inicializando OpenSearch: {e}")
    
    def _create_namespace(self, **kwargs) -> str:
        """🔧 FASE 4: Crear namespace basado en estrategia configurada"""
        strategy = self.vector_config.namespace_strategy
        
        if strategy == "tenant_app_db_snapshot":
            tenant_id = kwargs.get("tenant_id", "default")
            app_id = kwargs.get("app_id", "default")
            db_id = kwargs.get("db_id", "default")
            snapshot_id = kwargs.get("snapshot_id", "default")
            return f"{tenant_id}:{app_id}:{db_id}:{snapshot_id}"
        
        elif strategy == "db_snapshot":
            db_id = kwargs.get("db_id", "default")
            snapshot_id = kwargs.get("snapshot_id", "default")
            return f"{db_id}:{snapshot_id}"
        
        elif strategy == "simple":
            return kwargs.get("namespace", "default")
        
        else:
            return "default"
    
    def _generate_document_id(self, content: str, namespace: str) -> str:
        """Generar ID único para documento basado en contenido y namespace"""
        content_hash = hashlib.md5(f"{content}:{namespace}".encode()).hexdigest()
        return f"{namespace}:{content_hash}"
    
    def upsert_documents(self, documents: List[VectorDocument], **kwargs) -> bool:
        """
        🔧 FASE 4: Upsert idempotente de documentos vectorizados
        
        Args:
            documents: Lista de documentos a upsert
            **kwargs: Parámetros adicionales (tenant_id, app_id, db_id, snapshot_id)
            
        Returns:
            True si se completó exitosamente
        """
        if not documents:
            return True
        
        # 🔧 FASE 4: Batching automático
        batches = [documents[i:i + self.config.batch_size] 
                  for i in range(0, len(documents), self.config.batch_size)]
        
        try:
            for batch in batches:
                self._upsert_batch(batch, **kwargs)
            
            self._log_operation("Documentos upsertados", 
                               total_documents=len(documents), 
                               total_batches=len(batches))
            return True
            
        except Exception as e:
            self._log_error("Upsert de documentos", e, total_documents=len(documents))
            raise
    
    def _upsert_batch(self, documents: List[VectorDocument], **kwargs):
        """Upsert de un batch de documentos"""
        driver_type = self.driver["type"]
        
        if driver_type == "pgvector":
            self._upsert_batch_pgvector(documents, **kwargs)
        elif driver_type == "qdrant":
            self._upsert_batch_qdrant(documents, **kwargs)
        elif driver_type == "weaviate":
            self._upsert_batch_weaviate(documents, **kwargs)
        elif driver_type == "pinecone":
            self._upsert_batch_pinecone(documents, **kwargs)
        elif driver_type == "opensearch":
            self._upsert_batch_opensearch(documents, **kwargs)
        else:
            raise ValueError(f"Driver no soportado: {driver_type}")
    
    def _upsert_batch_pgvector(self, documents: List[VectorDocument], **kwargs):
        """Upsert batch en pgvector"""
        import psycopg2
        from pgvector.psycopg2 import register_vector
        
        conn = psycopg2.connect(self.driver["url"])
        register_vector(conn)
        
        with conn.cursor() as cur:
            for doc in documents:
                cur.execute("""
                    INSERT INTO embeddings (id, content, metadata, embedding, namespace)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) 
                    DO UPDATE SET 
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding,
                        namespace = EXCLUDED.namespace
                """, (doc.id, doc.content, doc.metadata, doc.embedding, doc.namespace))
        
        conn.commit()
        conn.close()
    
    def _upsert_batch_qdrant(self, documents: List[VectorDocument], **kwargs):
        """Upsert batch en Qdrant"""
        client = self.driver["client"]
        collection = self.driver["collection"]
        
        points = []
        for doc in documents:
            points.append({
                "id": doc.id,
                "vector": doc.embedding,
                "payload": {
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "namespace": doc.namespace
                }
            })
        
        client.upsert(collection_name=collection, points=points)
    
    def _upsert_batch_weaviate(self, documents: List[VectorDocument], **kwargs):
        """Upsert batch en Weaviate"""
        client = self.driver["client"]
        class_name = self.driver["class"]
        
        for doc in documents:
            data_object = {
                "content": doc.content,
                "metadata": str(doc.metadata),
                "namespace": doc.namespace
            }
            
            # Weaviate requiere que el vector se pase por separado
            client.data_object.create(
                data_object=data_object,
                class_name=class_name,
                vector=doc.embedding
            )
    
    def _upsert_batch_pinecone(self, documents: List[VectorDocument], **kwargs):
        """Upsert batch en Pinecone"""
        index = self.driver["index"]
        
        vectors = []
        for doc in documents:
            vectors.append({
                "id": doc.id,
                "values": doc.embedding,
                "metadata": {
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "namespace": doc.namespace
                }
            })
        
        index.upsert(vectors=vectors)
    
    def _upsert_batch_opensearch(self, documents: List[VectorDocument], **kwargs):
        """Upsert batch en OpenSearch"""
        client = self.driver["client"]
        index_name = self.driver["index"]
        
        for doc in documents:
            body = {
                "content": doc.content,
                "metadata": doc.metadata,
                "namespace": doc.namespace,
                "embedding": doc.embedding
            }
            
            client.index(
                index=index_name,
                id=doc.id,
                body=body
            )
    
    def search_similar(self, query_embedding: List[float], 
                      namespace: Optional[str] = None,
                      top_k: Optional[int] = None,
                      **kwargs) -> List[SearchResult]:
        """
        🔧 FASE 4: Búsqueda vectorial con filtros de namespace
        
        Args:
            query_embedding: Embedding de la consulta
            namespace: Namespace para filtrar (opcional)
            top_k: Número máximo de resultados
            **kwargs: Parámetros adicionales
            
        Returns:
            Lista de resultados ordenados por similitud
        """
        if top_k is None:
            top_k = self.max_top_k
        
        top_k = min(top_k, self.max_top_k)
        
        try:
            driver_type = self.driver["type"]
            
            if driver_type == "pgvector":
                results = self._search_pgvector(query_embedding, namespace, top_k, **kwargs)
            elif driver_type == "qdrant":
                results = self._search_qdrant(query_embedding, namespace, top_k, **kwargs)
            elif driver_type == "weaviate":
                results = self._search_weaviate(query_embedding, namespace, top_k, **kwargs)
            elif driver_type == "pinecone":
                results = self._search_pinecone(query_embedding, namespace, top_k, **kwargs)
            elif driver_type == "opensearch":
                results = self._search_opensearch(query_embedding, namespace, top_k, **kwargs)
            else:
                raise ValueError(f"Driver no soportado: {driver_type}")
            
            self._log_operation("Búsqueda vectorial completada", 
                               query_dimensions=len(query_embedding),
                               namespace=namespace,
                               top_k=top_k,
                               results_count=len(results))
            
            return results
            
        except Exception as e:
            self._log_error("Búsqueda vectorial", e, 
                           query_dimensions=len(query_embedding),
                           namespace=namespace)
            raise
    
    def _search_pgvector(self, query_embedding: List[float], 
                         namespace: Optional[str], top_k: int, **kwargs) -> List[SearchResult]:
        """Búsqueda en pgvector"""
        import psycopg2
        from pgvector.psycopg2 import register_vector
        
        conn = psycopg2.connect(self.driver["url"])
        register_vector(conn)
        
        with conn.cursor() as cur:
            if namespace:
                cur.execute("""
                    SELECT id, content, metadata, namespace, 
                           1 - (embedding <=> %s) as score
                    FROM embeddings 
                    WHERE namespace = %s
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (query_embedding, namespace, query_embedding, top_k))
            else:
                cur.execute("""
                    SELECT id, content, metadata, namespace, 
                           1 - (embedding <=> %s) as score
                    FROM embeddings 
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (query_embedding, query_embedding, top_k))
            
            rows = cur.fetchall()
        
        conn.close()
        
        return [
            SearchResult(
                id=row[0],
                content=row[1],
                metadata=row[2] if row[2] else {},
                score=float(row[4]),
                namespace=row[3]
            )
            for row in rows
        ]
    
    def _search_qdrant(self, query_embedding: List[float], 
                       namespace: Optional[str], top_k: int, **kwargs) -> List[SearchResult]:
        """Búsqueda en Qdrant"""
        client = self.driver["client"]
        collection = self.driver["collection"]
        
        # Construir filtro de namespace
        filter_condition = None
        if namespace:
            filter_condition = {
                "key": "namespace",
                "match": {"value": namespace}
            }
        
        response = client.search(
            collection_name=collection,
            query_vector=query_embedding,
            query_filter=filter_condition,
            limit=top_k
        )
        
        return [
            SearchResult(
                id=str(point.id),
                content=point.payload.get("content", ""),
                metadata=point.payload.get("metadata", {}),
                score=point.score,
                namespace=point.payload.get("namespace", "")
            )
            for point in response
        ]
    
    def _search_weaviate(self, query_embedding: List[float], 
                         namespace: Optional[str], top_k: int, **kwargs) -> List[SearchResult]:
        """Búsqueda en Weaviate"""
        client = self.driver["client"]
        class_name = self.driver["class"]
        
        # Construir filtro de namespace
        where_filter = None
        if namespace:
            where_filter = {
                "path": ["namespace"],
                "operator": "Equal",
                "valueString": namespace
            }
        
        response = client.query.get(class_name, ["content", "metadata", "namespace"]).with_near_vector({
            "vector": query_embedding
        }).with_where(where_filter).with_limit(top_k).do()
        
        results = response["data"]["Get"][class_name]
        
        return [
            SearchResult(
                id=str(i),
                content=result.get("content", ""),
                metadata=eval(result.get("metadata", "{}")),
                score=0.0,  # Weaviate no devuelve score por defecto
                namespace=result.get("namespace", "")
            )
            for i, result in enumerate(results)
        ]
    
    def _search_pinecone(self, query_embedding: List[float], 
                         namespace: Optional[str], top_k: int, **kwargs) -> List[SearchResult]:
        """Búsqueda en Pinecone"""
        index = self.driver["index"]
        
        # Construir filtro de namespace
        filter_dict = {}
        if namespace:
            filter_dict["namespace"] = namespace
        
        response = index.query(
            vector=query_embedding,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True
        )
        
        return [
            SearchResult(
                id=match.id,
                content=match.metadata.get("content", ""),
                metadata=match.metadata.get("metadata", {}),
                score=match.score,
                namespace=match.metadata.get("namespace", "")
            )
            for match in response.matches
        ]
    
    def _search_opensearch(self, query_embedding: List[float], 
                          namespace: Optional[str], top_k: int, **kwargs) -> List[SearchResult]:
        """Búsqueda en OpenSearch"""
        client = self.driver["client"]
        index_name = self.driver["index"]
        
        # Construir query
        query = {
            "size": top_k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": top_k
                    }
                }
            }
        }
        
        # Agregar filtro de namespace
        if namespace:
            query["query"]["bool"] = {
                "must": [
                    {"knn": {"embedding": {"vector": query_embedding, "k": top_k}}},
                    {"term": {"namespace": namespace}}
                ]
            }
        
        response = client.search(index=index_name, body=query)
        
        return [
            SearchResult(
                id=hit["_id"],
                content=hit["_source"].get("content", ""),
                metadata=hit["_source"].get("metadata", {}),
                score=hit["_score"],
                namespace=hit["_source"].get("namespace", "")
            )
            for hit in response["hits"]["hits"]
        ]
    
    def delete_namespace(self, namespace: str) -> bool:
        """Eliminar todos los documentos de un namespace"""
        try:
            driver_type = self.driver["type"]
            
            if driver_type == "pgvector":
                return self._delete_namespace_pgvector(namespace)
            elif driver_type == "qdrant":
                return self._delete_namespace_qdrant(namespace)
            elif driver_type == "weaviate":
                return self._delete_namespace_weaviate(namespace)
            elif driver_type == "pinecone":
                return self._delete_namespace_pinecone(namespace)
            elif driver_type == "opensearch":
                return self._delete_namespace_opensearch(namespace)
            else:
                raise ValueError(f"Driver no soportado: {driver_type}")
                
        except Exception as e:
            self._log_error("Eliminación de namespace", e, namespace=namespace)
            return False
    
    def _delete_namespace_pgvector(self, namespace: str) -> bool:
        """Eliminar namespace en pgvector"""
        import psycopg2
        
        conn = psycopg2.connect(self.driver["url"])
        with conn.cursor() as cur:
            cur.execute("DELETE FROM embeddings WHERE namespace = %s", (namespace,))
        conn.commit()
        conn.close()
        return True
    
    def _delete_namespace_qdrant(self, namespace: str) -> bool:
        """Eliminar namespace en Qdrant"""
        client = self.driver["client"]
        collection = self.driver["collection"]
        
        # Obtener IDs de documentos en el namespace
        response = client.scroll(
            collection_name=collection,
            scroll_filter={"key": "namespace", "match": {"value": namespace}},
            limit=1000
        )
        
        if response[0]:
            ids = [point.id for point in response[0]]
            if ids:
                client.delete(collection_name=collection, points_selector=ids)
        
        return True
    
    def _delete_namespace_weaviate(self, namespace: str) -> bool:
        """Eliminar namespace en Weaviate"""
        client = self.driver["client"]
        class_name = self.driver["class"]
        
        # Weaviate no soporta eliminación por filtro, solo por ID
        # Esta es una limitación del driver
        return True
    
    def _delete_namespace_pinecone(self, namespace: str) -> bool:
        """Eliminar namespace en Pinecone"""
        index = self.driver["index"]
        
        # Pinecone no soporta eliminación por filtro, solo por ID
        # Esta es una limitación del driver
        return True
    
    def _delete_namespace_opensearch(self, namespace: str) -> bool:
        """Eliminar namespace en OpenSearch"""
        client = self.driver["client"]
        index_name = self.driver["index"]
        
        query = {"query": {"term": {"namespace": namespace}}}
        client.delete_by_query(index=index_name, body=query)
        return True
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """Obtener estadísticas de un namespace"""
        try:
            driver_type = self.driver["type"]
            
            if driver_type == "pgvector":
                return self._get_namespace_stats_pgvector(namespace)
            elif driver_type == "qdrant":
                return self._get_namespace_stats_qdrant(namespace)
            else:
                return {"error": f"Stats no soportados para {driver_type}"}
                
        except Exception as e:
            self._log_error("Obtención de stats de namespace", e, namespace=namespace)
            return {"error": str(e)}
    
    def _get_namespace_stats_pgvector(self, namespace: str) -> Dict[str, Any]:
        """Obtener stats de namespace en pgvector"""
        import psycopg2
        
        conn = psycopg2.connect(self.driver["url"])
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as total_documents,
                       AVG(LENGTH(content)) as avg_content_length,
                       MIN(created_at) as first_document,
                       MAX(created_at) as last_document
                FROM embeddings 
                WHERE namespace = %s
            """, (namespace,))
            
            row = cur.fetchone()
        
        conn.close()
        
        return {
            "namespace": namespace,
            "total_documents": row[0] if row else 0,
            "avg_content_length": int(row[1]) if row and row[1] else 0,
            "first_document": str(row[2]) if row and row[2] else None,
            "last_document": str(row[3]) if row and row[3] else None
        }
    
    def _get_namespace_stats_qdrant(self, namespace: str) -> Dict[str, Any]:
        """Obtener stats de namespace en Qdrant"""
        client = self.driver["client"]
        collection = self.driver["collection"]
        
        response = client.scroll(
            collection_name=collection,
            scroll_filter={"key": "namespace", "match": {"value": namespace}},
            limit=1
        )
        
        total = response[1] if len(response) > 1 else 0
        
        return {
            "namespace": namespace,
            "total_documents": total,
            "avg_content_length": 0,  # Qdrant no proporciona esta info
            "first_document": None,
            "last_document": None
        }
    
    def _health_check(self) -> bool:
        """Verificar salud del adapter de vector store"""
        try:
            # Intentar operación básica
            test_embedding = [0.0] * self.vector_config.dimensions
            results = self.search_similar(test_embedding, top_k=1)
            return True
        except Exception as e:
            self._log_error("Health check", e)
            return False
    
    def initialize(self) -> bool:
        """Inicializar el adapter de vector store"""
        try:
            health_status = self._health_check()
            if health_status:
                self._log_operation("Adapter de vector store inicializado correctamente")
            return health_status
        except Exception as e:
            self._log_error("Inicialización", e)
            return False
