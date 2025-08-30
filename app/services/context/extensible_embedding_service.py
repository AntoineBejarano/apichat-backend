"""
ExtensibleEmbeddingService - Sistema de embeddings extensible
────────────────────────────────────────────────────────────
Servicio de embeddings diseñado para ser extensible a múltiples tipos de recursos:
- APIs (endpoints, parámetros, respuestas)
- Estrategias (reglas, condiciones, acciones)
- Funciones (código, documentación, metadatos)
- Cualquier otro tipo de recurso en el futuro
"""

import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.core.adapters.embedding_adapter import EmbeddingAdapter
from app.core.adapters.vector_store_adapter import VectorStoreAdapter
from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Tipos de recursos soportados por el sistema de embeddings"""
    API_ENDPOINT = "api_endpoint"
    API_PARAMETER = "api_parameter"
    API_RESPONSE = "api_response"
    STRATEGY_RULE = "strategy_rule"
    STRATEGY_CONDITION = "strategy_condition"
    STRATEGY_ACTION = "strategy_action"
    FUNCTION_CODE = "function_code"
    FUNCTION_DOCS = "function_docs"
    DATABASE_TABLE = "database_table"
    DATABASE_COLUMN = "database_column"
    DATABASE_RELATIONSHIP = "database_relationship"


@dataclass
class EmbeddingResource:
    """Recurso embebible genérico"""
    id: str
    resource_type: ResourceType
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    namespace: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class EmbeddingSearchResult:
    """Resultado de búsqueda de embeddings"""
    resource_id: str
    resource_type: ResourceType
    content: str
    similarity_score: float
    metadata: Dict[str, Any]
    namespace: str


class ExtensibleEmbeddingService:
    """
    Servicio de embeddings extensible para múltiples tipos de recursos.
    Diseñado para crecer con nuevas funcionalidades como estrategias.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        
        # Adapters
        self.embedding_adapter = factory.get_embedding_adapter()
        self.vector_adapter = factory.get_vector_store_adapter()
        
        # Cache de embeddings por tipo de recurso
        self.embedding_cache = {}
        
        self.logger.info("[ExtensibleEmbeddingService] 🚀 Inicializado con sistema extensible")
    
    async def create_embeddings_for_resource_type(
        self,
        resource_type: ResourceType,
        resources: List[Dict[str, Any]],
        namespace: str,
        **kwargs
    ) -> Dict[str, List[float]]:
        """
        Crear embeddings para un tipo específico de recurso.
        
        Args:
            resource_type: Tipo de recurso (API, Strategy, Function, etc.)
            resources: Lista de recursos a procesar
            namespace: Namespace para el vector store
            **kwargs: Parámetros adicionales específicos del tipo de recurso
            
        Returns:
            Diccionario con embeddings: {resource_id: embedding}
        """
        start_time = datetime.now()
        embeddings = {}
        
        try:
            self.logger.info(f"[ExtensibleEmbeddingService] 🧠 Creando embeddings para {len(resources)} recursos de tipo {resource_type.value}")
            
            # Procesar recursos según el tipo
            processed_resources = await self._process_resources_by_type(resource_type, resources, **kwargs)
            
            # Generar embeddings
            for resource in processed_resources:
                if resource.content:
                    embedding = await self._get_embedding(resource.content)
                    embeddings[resource.id] = embedding
                    
                    # Almacenar en vector store
                    await self._store_embedding(resource, embedding, namespace)
            
            # Cachear embeddings
            cache_key = f"{resource_type.value}_{namespace}"
            self.embedding_cache[cache_key] = embeddings
            
            response_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"[ExtensibleEmbeddingService] ✅ Embeddings creados: {len(embeddings)} recursos en {response_time:.2f}s")
            
            return embeddings
            
        except Exception as e:
            self.logger.error(f"[ExtensibleEmbeddingService] ❌ Error creando embeddings: {e}")
            return {}
    
    async def _process_resources_by_type(
        self,
        resource_type: ResourceType,
        resources: List[Dict[str, Any]],
        **kwargs
    ) -> List[EmbeddingResource]:
        """Procesar recursos según su tipo específico"""
        
        if resource_type == ResourceType.API_ENDPOINT:
            return await self._process_api_endpoints(resources, **kwargs)
        elif resource_type == ResourceType.API_PARAMETER:
            return await self._process_api_parameters(resources, **kwargs)
        elif resource_type == ResourceType.API_RESPONSE:
            return await self._process_api_responses(resources, **kwargs)
        elif resource_type == ResourceType.STRATEGY_RULE:
            return await self._process_strategy_rules(resources, **kwargs)
        elif resource_type == ResourceType.STRATEGY_CONDITION:
            return await self._process_strategy_conditions(resources, **kwargs)
        elif resource_type == ResourceType.STRATEGY_ACTION:
            return await self._process_strategy_actions(resources, **kwargs)
        elif resource_type == ResourceType.FUNCTION_CODE:
            return await self._process_function_code(resources, **kwargs)
        elif resource_type == ResourceType.FUNCTION_DOCS:
            return await self._process_function_docs(resources, **kwargs)
        else:
            # Procesamiento genérico para tipos no específicos
            return await self._process_generic_resources(resource_type, resources, **kwargs)
    
    async def _process_api_endpoints(self, resources: List[Dict[str, Any]], **kwargs) -> List[EmbeddingResource]:
        """Procesar endpoints de API para embeddings"""
        processed = []
        
        for resource in resources:
            path = resource.get("path", "")
            method = resource.get("method", "")
            details = resource.get("details", {})
            
            # Construir contenido rico para triggering
            content = self._build_api_endpoint_content(path, method, details)
            
            processed.append(EmbeddingResource(
                id=f"api_endpoint_{method}_{path}",
                resource_type=ResourceType.API_ENDPOINT,
                content=content,
                metadata={
                    "path": path,
                    "method": method,
                    "operation_id": details.get("operationId", ""),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "tags": details.get("tags", []),
                    "app_id": kwargs.get("app_id"),
                    "integration_id": kwargs.get("integration_id")
                }
            ))
        
        return processed
    
    async def _process_api_parameters(self, resources: List[Dict[str, Any]], **kwargs) -> List[EmbeddingResource]:
        """Procesar parámetros de API para embeddings"""
        processed = []
        
        for resource in resources:
            param = resource.get("parameter", {})
            endpoint_path = resource.get("endpoint_path", "")
            method = resource.get("method", "")
            
            content = self._build_api_parameter_content(param, endpoint_path, method)
            
            processed.append(EmbeddingResource(
                id=f"api_param_{method}_{endpoint_path}_{param.get('name', '')}",
                resource_type=ResourceType.API_PARAMETER,
                content=content,
                metadata={
                    "parameter_name": param.get("name", ""),
                    "parameter_type": param.get("schema", {}).get("type", ""),
                    "parameter_in": param.get("in", ""),
                    "required": param.get("required", False),
                    "description": param.get("description", ""),
                    "endpoint_path": endpoint_path,
                    "method": method,
                    "app_id": kwargs.get("app_id")
                }
            ))
        
        return processed
    
    async def _process_strategy_rules(self, resources: List[Dict[str, Any]], **kwargs) -> List[EmbeddingResource]:
        """Procesar reglas de estrategia para embeddings (futuro)"""
        processed = []
        
        for resource in resources:
            # TODO: Implementar cuando se añadan las estrategias
            content = f"Strategy rule: {resource.get('name', '')} - {resource.get('description', '')}"
            
            processed.append(EmbeddingResource(
                id=f"strategy_rule_{resource.get('id', '')}",
                resource_type=ResourceType.STRATEGY_RULE,
                content=content,
                metadata={
                    "strategy_id": resource.get("strategy_id"),
                    "rule_name": resource.get("name", ""),
                    "rule_type": resource.get("type", ""),
                    "conditions": resource.get("conditions", []),
                    "actions": resource.get("actions", [])
                }
            ))
        
        return processed
    
    async def _process_generic_resources(
        self,
        resource_type: ResourceType,
        resources: List[Dict[str, Any]],
        **kwargs
    ) -> List[EmbeddingResource]:
        """Procesamiento genérico para tipos de recursos no específicos"""
        processed = []
        
        for resource in resources:
            content = f"{resource_type.value}: {resource.get('name', '')} - {resource.get('description', '')}"
            
            processed.append(EmbeddingResource(
                id=f"{resource_type.value}_{resource.get('id', '')}",
                resource_type=resource_type,
                content=content,
                metadata=resource
            ))
        
        return processed
    
    def _build_api_endpoint_content(self, path: str, method: str, details: Dict[str, Any]) -> str:
        """Construir contenido optimizado para triggering de endpoints"""
        operation_id = details.get("operationId", f"{method}_{path}")
        description = details.get("description", "")
        summary = details.get("summary", "")
        
        # Parámetros para triggering
        parameters = details.get("parameters", [])
        param_descriptions = []
        for param in parameters:
            param_descriptions.append(f"{param['name']}: {param.get('description', '')}")
        
        # Request body para triggering
        request_body = details.get("requestBody", {})
        body_schema = request_body.get("content", {}).get("application/json", {}).get("schema", {})
        
        # Response para contexto
        responses = details.get("responses", {})
        success_response = responses.get("200", {}).get("content", {}).get("application/json", {})
        
        # Casos de uso inferidos
        use_cases = self._infer_api_use_cases(path, method, details)
        
        content_parts = [
            f"API Endpoint: {method.upper()} {path}",
            f"Purpose: {summary}",
            f"Description: {description}",
            f"Parameters: {'; '.join(param_descriptions)}",
            f"Request body: {body_schema.get('type', 'object')}",
            f"Response: {success_response.get('schema', {}).get('type', 'object')}",
            f"Use cases: {use_cases}"
        ]
        
        return " | ".join(content_parts)
    
    def _build_api_parameter_content(self, param: Dict[str, Any], endpoint_path: str, method: str) -> str:
        """Construir contenido para parámetros de API"""
        param_name = param.get("name", "")
        param_type = param.get("schema", {}).get("type", "")
        param_in = param.get("in", "")
        description = param.get("description", "")
        required = param.get("required", False)
        
        content_parts = [
            f"API Parameter: {param_name}",
            f"Type: {param_type}",
            f"Location: {param_in}",
            f"Required: {required}",
            f"Description: {description}",
            f"Endpoint: {method.upper()} {endpoint_path}"
        ]
        
        return " | ".join(content_parts)
    
    def _infer_api_use_cases(self, path: str, method: str, details: Dict[str, Any]) -> str:
        """Inferir casos de uso para mejor triggering"""
        path_lower = path.lower()
        method_lower = method.lower()
        
        use_cases = []
        
        if method_lower == "post":
            if "user" in path_lower:
                use_cases.extend(["create user", "register user", "add user", "signup"])
            elif "product" in path_lower:
                use_cases.extend(["create product", "add product", "new product"])
            elif "order" in path_lower:
                use_cases.extend(["create order", "place order", "new order"])
            elif "auth" in path_lower or "login" in path_lower:
                use_cases.extend(["login", "authenticate", "sign in"])
        elif method_lower == "get":
            if "user" in path_lower:
                use_cases.extend(["get user", "fetch user", "retrieve user", "list users"])
            elif "product" in path_lower:
                use_cases.extend(["get product", "fetch product", "list products", "search products"])
            elif "order" in path_lower:
                use_cases.extend(["get order", "fetch order", "list orders"])
        elif method_lower == "put":
            use_cases.extend(["update", "modify", "edit", "change"])
        elif method_lower == "delete":
            use_cases.extend(["delete", "remove", "eliminate"])
        
        # Añadir casos de uso basados en tags
        tags = details.get("tags", [])
        for tag in tags:
            use_cases.append(f"{tag.lower()} operations")
        
        return ", ".join(use_cases) if use_cases else f"API operation for {path}"
    
    async def _get_embedding(self, content: str) -> List[float]:
        """Obtener embedding para un contenido específico"""
        try:
            # Cache simple de embeddings
            if content in self.embedding_cache:
                return self.embedding_cache[content]
            
            # Obtener embedding usando el adapter
            embeddings = self.embedding_adapter.generate_embeddings([content])
            
            if embeddings and len(embeddings) > 0:
                embedding = embeddings[0]
                # Cachear
                self.embedding_cache[content] = embedding
                return embedding
            
            return []
            
        except Exception as e:
            self.logger.error(f"[ExtensibleEmbeddingService] ❌ Error obteniendo embedding: {e}")
            return []
    
    async def _store_embedding(self, resource: EmbeddingResource, embedding: List[float], namespace: str):
        """Almacenar embedding en el vector store"""
        try:
            # Preparar documento para el vector store
            document = {
                "id": resource.id,
                "content": resource.content,
                "metadata": {
                    **resource.metadata,
                    "resource_type": resource.resource_type.value,
                    "created_at": datetime.now().isoformat()
                },
                "embedding": embedding
            }
            
            # Almacenar usando el vector adapter
            await self.vector_adapter.upsert_documents([document], namespace=namespace)
            
        except Exception as e:
            self.logger.error(f"[ExtensibleEmbeddingService] ❌ Error almacenando embedding: {e}")
    
    async def search_embeddings(
        self,
        query: str,
        resource_types: Optional[List[ResourceType]] = None,
        namespace: Optional[str] = None,
        top_k: int = 10,
        **filters
    ) -> List[EmbeddingSearchResult]:
        """
        Búsqueda semántica en embeddings de múltiples tipos de recursos.
        
        Args:
            query: Query de búsqueda
            resource_types: Tipos de recursos a buscar (None = todos)
            namespace: Namespace específico (None = todos)
            top_k: Número de resultados
            **filters: Filtros adicionales
            
        Returns:
            Lista de resultados de búsqueda
        """
        try:
            self.logger.info(f"[ExtensibleEmbeddingService] 🔍 Búsqueda semántica: '{query}' en {len(resource_types) if resource_types else 'todos'} tipos")
            
            # Generar embedding de la query
            query_embedding = await self._get_embedding(query)
            if not query_embedding:
                return []
            
            # Preparar filtros
            search_filters = {}
            if resource_types:
                search_filters["resource_type"] = [rt.value for rt in resource_types]
            if namespace:
                search_filters["namespace"] = namespace
            search_filters.update(filters)
            
            # Buscar en vector store
            results = await self.vector_adapter.search(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=search_filters
            )
            
            # Convertir resultados
            search_results = []
            for result in results:
                search_results.append(EmbeddingSearchResult(
                    resource_id=result.id,
                    resource_type=ResourceType(result.metadata.get("resource_type", "")),
                    content=result.content,
                    similarity_score=result.similarity_score,
                    metadata=result.metadata,
                    namespace=result.namespace
                ))
            
            self.logger.info(f"[ExtensibleEmbeddingService] ✅ Encontrados {len(search_results)} resultados")
            return search_results
            
        except Exception as e:
            self.logger.error(f"[ExtensibleEmbeddingService] ❌ Error en búsqueda: {e}")
            return []
    
    async def get_embedding_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del sistema de embeddings"""
        try:
            stats = {
                "cache_size": len(self.embedding_cache),
                "supported_resource_types": [rt.value for rt in ResourceType],
                "total_embeddings_cached": sum(len(embeddings) for embeddings in self.embedding_cache.values() if isinstance(embeddings, dict))
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"[ExtensibleEmbeddingService] ❌ Error obteniendo estadísticas: {e}")
            return {}
