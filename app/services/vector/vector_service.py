#!/usr/bin/env python3
"""
Vector Service - Servicio integrado para embeddings y vector store
──────────────────────────────────────────────────────────────────
Implementa la Fase 4 del plan de refactorización:
- Integración de EmbeddingAdapter y VectorStoreAdapter
- Pipeline completo: texto → embeddings → almacenamiento → búsqueda
- Namespace management automático
- Batching y optimizaciones
"""

import logging
import time
from typing import List, Dict, Any, Optional, Union
from uuid import UUID

from app.core.adapters.embedding_adapter import EmbeddingAdapter, EmbeddingConfig
from app.core.adapters.vector_store_adapter import VectorStoreAdapter, VectorStoreConfig, VectorDocument, SearchResult


class VectorService:
    """
    🔧 Vector Service integrado
    
    Responsabilidades:
    - Generar embeddings para texto
    - Almacenar embeddings en vector store
    - Búsqueda vectorial semántica
    - Gestión de namespaces
    - Optimizaciones de performance
    """
    
    def __init__(self, embedding_config: Optional[EmbeddingConfig] = None, 
                 vector_config: Optional[VectorStoreConfig] = None):
        self.logger = logging.getLogger(__name__)
        
        # 🔧 FASE 4: Inicializar adapters
        self.embedding_adapter = EmbeddingAdapter(embedding_config)
        self.vector_adapter = VectorStoreAdapter(vector_config)
        
        # Verificar compatibilidad de dimensiones
        self._validate_dimensions()
        
        self.logger.info(f"[VectorService] 🔧 Servicio inicializado - Embeddings: {self.embedding_adapter.config.provider}, Vector: {self.vector_adapter.config.provider}")
    
    def _validate_dimensions(self):
        """Validar que las dimensiones de ambos adapters sean compatibles"""
        embedding_dims = self.embedding_adapter.get_embedding_dimensions()
        vector_dims = self.vector_adapter.vector_config.dimensions
        
        if embedding_dims != vector_dims:
            self.logger.warning(f"[VectorService] ⚠️ Dimensiones no coinciden: Embeddings={embedding_dims}, Vector={vector_dims}")
            # Ajustar dimensiones del vector store si es posible
            if hasattr(self.vector_adapter, 'vector_config'):
                self.vector_adapter.vector_config.dimensions = embedding_dims
    
    async def process_texts(self, texts: List[str], 
                           metadata_list: Optional[List[Dict[str, Any]]] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        🔧 FASE 4: Pipeline completo: texto → embeddings → almacenamiento
        
        Args:
            texts: Lista de textos a procesar
            metadata_list: Metadatos para cada texto (opcional)
            **kwargs: Parámetros para namespace (tenant_id, app_id, db_id, snapshot_id)
            
        Returns:
            Resultado del procesamiento con estadísticas
        """
        start_time = time.time()
        
        try:
            if not texts:
                return {"success": True, "message": "No hay textos para procesar", "total_processed": 0}
            
            # 🔧 FASE 4: 1. Generar embeddings
            self.logger.info(f"[VectorService] 🧠 Generando embeddings para {len(texts)} textos")
            embeddings = self.embedding_adapter.generate_embeddings(texts)
            
            if len(embeddings) != len(texts):
                raise ValueError(f"Error: se generaron {len(embeddings)} embeddings para {len(texts)} textos")
            
            # 🔧 FASE 4: 2. Crear namespace
            namespace = self.vector_adapter._create_namespace(**kwargs)
            
            # 🔧 FASE 4: 3. Preparar documentos vectorizados
            documents = []
            for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
                
                # Generar ID único
                doc_id = self.vector_adapter._generate_document_id(text, namespace)
                
                document = VectorDocument(
                    id=doc_id,
                    content=text,
                    metadata=metadata,
                    embedding=embedding,
                    namespace=namespace
                )
                documents.append(document)
            
            # 🔧 FASE 4: 4. Almacenar en vector store
            self.logger.info(f"[VectorService] 💾 Almacenando {len(documents)} documentos en namespace '{namespace}'")
            success = self.vector_adapter.upsert_documents(documents, **kwargs)
            
            if not success:
                raise Exception("Error al almacenar documentos en vector store")
            
            # 🔧 FASE 4: 5. Calcular estadísticas
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "success": True,
                "message": f"Procesados {len(texts)} textos exitosamente",
                "total_processed": len(texts),
                "namespace": namespace,
                "embedding_provider": self.embedding_adapter.config.provider,
                "vector_provider": self.vector_adapter.config.provider,
                "embedding_dimensions": len(embeddings[0]) if embeddings else 0,
                "processing_time_ms": processing_time_ms,
                "batch_size": self.embedding_adapter.batch_size,
                "vector_batch_size": self.vector_adapter.config.batch_size
            }
            
            self.logger.info(f"[VectorService] ✅ Pipeline completado en {processing_time_ms}ms - {len(texts)} textos procesados")
            return result
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            self.logger.error(f"[VectorService] ❌ Error en pipeline: {e}")
            
            return {
                "success": False,
                "message": f"Error procesando textos: {str(e)}",
                "total_processed": 0,
                "processing_time_ms": processing_time_ms,
                "error": str(e)
            }
    
    async def search_similar(self, query: str, 
                           namespace: Optional[str] = None,
                           top_k: Optional[int] = None,
                           **kwargs) -> Dict[str, Any]:
        """
        🔧 FASE 4: Búsqueda vectorial semántica
        
        Args:
            query: Texto de consulta
            namespace: Namespace para filtrar (opcional)
            top_k: Número máximo de resultados
            **kwargs: Parámetros adicionales
            
        Returns:
            Resultados de búsqueda con metadatos
        """
        start_time = time.time()
        
        try:
            # 🔧 FASE 4: 1. Generar embedding de la consulta
            self.logger.info(f"[VectorService] 🔍 Generando embedding para consulta: '{query[:50]}...'")
            query_embeddings = self.embedding_adapter.generate_embeddings([query])
            
            if not query_embeddings:
                raise ValueError("No se pudo generar embedding para la consulta")
            
            query_embedding = query_embeddings[0]
            
            # 🔧 FASE 4: 2. Búsqueda vectorial
            self.logger.info(f"[VectorService] 🔎 Realizando búsqueda vectorial en namespace '{namespace}'")
            search_results = self.vector_adapter.search_similar(
                query_embedding=query_embedding,
                namespace=namespace,
                top_k=top_k,
                **kwargs
            )
            
            # 🔧 FASE 4: 3. Calcular estadísticas
            search_time_ms = int((time.time() - start_time) * 1000)
            
            result = {
                "success": True,
                "query": query,
                "namespace": namespace,
                "total_results": len(search_results),
                "search_time_ms": search_time_ms,
                "embedding_provider": self.embedding_adapter.config.provider,
                "vector_provider": self.vector_adapter.config.provider,
                "results": [
                    {
                        "id": result.id,
                        "content": result.content,
                        "metadata": result.metadata,
                        "score": result.score,
                        "namespace": result.namespace
                    }
                    for result in search_results
                ]
            }
            
            self.logger.info(f"[VectorService] ✅ Búsqueda completada en {search_time_ms}ms - {len(search_results)} resultados")
            return result
            
        except Exception as e:
            search_time_ms = int((time.time() - start_time) * 1000)
            self.logger.error(f"[VectorService] ❌ Error en búsqueda: {e}")
            
            return {
                "success": False,
                "message": f"Error en búsqueda: {str(e)}",
                "query": query,
                "namespace": namespace,
                "search_time_ms": search_time_ms,
                "error": str(e)
            }
    
    async def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """Obtener estadísticas de un namespace específico"""
        try:
            stats = self.vector_adapter.get_namespace_stats(namespace)
            return {
                "success": True,
                "namespace": namespace,
                "stats": stats
            }
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error obteniendo stats de namespace '{namespace}': {e}")
            return {
                "success": False,
                "namespace": namespace,
                "error": str(e)
            }
    
    async def delete_namespace(self, namespace: str) -> Dict[str, Any]:
        """Eliminar todos los documentos de un namespace"""
        try:
            self.logger.info(f"[VectorService] 🗑️ Eliminando namespace '{namespace}'")
            success = self.vector_adapter.delete_namespace(namespace)
            
            if success:
                return {
                    "success": True,
                    "message": f"Namespace '{namespace}' eliminado exitosamente",
                    "namespace": namespace
                }
            else:
                return {
                    "success": False,
                    "message": f"Error eliminando namespace '{namespace}'",
                    "namespace": namespace
                }
                
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error eliminando namespace '{namespace}': {e}")
            return {
                "success": False,
                "message": f"Error eliminando namespace: {str(e)}",
                "namespace": namespace,
                "error": str(e)
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Obtener estado de salud de ambos adapters"""
        try:
            embedding_health = self.embedding_adapter.get_health_status()
            vector_health = self.vector_adapter.get_health_status()
            
            overall_health = "healthy" if (embedding_health["status"] == "healthy" and 
                                         vector_health["status"] == "healthy") else "unhealthy"
            
            return {
                "service": "vector_service",
                "overall_status": overall_health,
                "embedding_adapter": embedding_health,
                "vector_adapter": vector_health,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error obteniendo health status: {e}")
            return {
                "service": "vector_service",
                "overall_status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de performance de ambos adapters"""
        try:
            embedding_metrics = self.embedding_adapter.get_performance_metrics()
            vector_metrics = self.vector_adapter.get_performance_metrics()
            
            return {
                "service": "vector_service",
                "embedding_adapter": embedding_metrics,
                "vector_adapter": vector_metrics,
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error obteniendo performance metrics: {e}")
            return {
                "service": "vector_service",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """Obtener información de configuración de ambos adapters"""
        try:
            return {
                "service": "vector_service",
                "embedding_config": {
                    "provider": self.embedding_adapter.config.provider,
                    "model": self.embedding_adapter.embedding_config.model,
                    "dimensions": self.embedding_adapter.embedding_config.dimensions,
                    "batch_size": self.embedding_adapter.batch_size,
                    "max_tokens_per_batch": self.embedding_adapter.max_tokens_per_batch
                },
                "vector_config": {
                    "provider": self.vector_adapter.config.provider,
                    "index_name": self.vector_adapter.vector_config.index_name,
                    "dimensions": self.vector_adapter.vector_config.dimensions,
                    "distance_metric": self.vector_adapter.vector_config.distance_metric,
                    "max_top_k": self.vector_adapter.vector_config.max_top_k,
                    "namespace_strategy": self.vector_adapter.vector_config.namespace_strategy
                },
                "timestamp": time.time()
            }
            
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error obteniendo configuración: {e}")
            return {
                "service": "vector_service",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def cleanup(self):
        """Limpieza de recursos"""
        try:
            self.embedding_adapter.cleanup()
            self.vector_adapter.cleanup()
            self.logger.info("[VectorService] 🧹 Limpieza completada")
        except Exception as e:
            self.logger.error(f"[VectorService] ❌ Error en limpieza: {e}")
    
    def __str__(self):
        return f"VectorService(Embedding: {self.embedding_adapter.config.provider}, Vector: {self.vector_adapter.config.provider})"
    
    def __repr__(self):
        return self.__str__()
