#!/usr/bin/env python3
"""
SchemaGraphService - Servicio para construir y gestionar el grafo de relaciones del esquema
──────────────────────────────────────────────────────────────────────────────────────────
Implementa:
- Construcción del grafo desde snapshot del esquema
- Detección automática de relaciones (FK, M2M)
- Caché optimizado para respuesta rápida
- Análisis de complejidad del grafo
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from uuid import UUID

from app.models.schema_graph_model import (
    SchemaGraph, 
    GraphNode, 
    GraphEdge, 
    GraphCache
)
from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
from app.utils.logger import logger


class SchemaGraphService:
    """
    Servicio principal para el grafo de relaciones del esquema.
    
    Implementa la Fase 2 del plan de refactorización:
    - Construcción del grafo desde snapshot
    - Detección de relaciones FK y M2M
    - Caché optimizado para respuesta rápida
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 2: Tipos de nodos y aristas
        self.NODE_TYPES = {
            "table": "table",
            "column": "column", 
            "relationship": "relationship"
        }
        
        self.EDGE_TYPES = {
            "HAS_COLUMN": "HAS_COLUMN",
            "FK_RELATION": "FK_RELATION",
            "MANY_TO_MANY": "MANY_TO_MANY",
            "INDEX_ON": "INDEX_ON"
        }
    
    async def build_graph_from_snapshot(self, db_id: UUID, user_id: UUID, snapshot_id: Optional[UUID] = None) -> Optional[SchemaGraph]:
        """
        Construye el grafo de relaciones desde un snapshot del esquema.
        
        Args:
            db_id: ID de la base de datos
            user_id: ID del usuario
            snapshot_id: ID del snapshot (opcional)
            
        Returns:
            SchemaGraph construido o None si falla
        """
        try:
            self.logger.info(f"[SchemaGraphService] 🕸️ Construyendo grafo para DB {db_id}")
            start_time = time.time()
            
            # Obtener el snapshot del esquema
            detailed_cache = self.factory.get_detailed_schema_cache_service()
            if not detailed_cache:
                self.logger.error("[SchemaGraphService] ❌ DetailedSchemaCacheService no disponible")
                return None
            
            # Obtener el cache entry
            cache_entry = detailed_cache.get_cache_entry(user_id, db_id)
            if not cache_entry or not cache_entry.schema:
                self.logger.error(f"[SchemaGraphService] ❌ No se encontró schema para DB {db_id}")
                return None
            
            # Crear el grafo
            graph = await self._create_graph_record(db_id, user_id, snapshot_id)
            if not graph:
                return None
            
            # Construir nodos y aristas
            success = await self._build_graph_structure(graph, cache_entry.schema)
            if not success:
                await self._mark_graph_failed(graph, "BUILD_STRUCTURE_FAILED", "Error construyendo estructura del grafo")
                return None
            
            # Generar caché optimizado
            cache_success = await self._generate_graph_cache(graph)
            if not cache_success:
                self.logger.warning(f"[SchemaGraphService] ⚠️ No se pudo generar caché para grafo {graph.id}")
            
            # Finalizar construcción
            build_duration = int(time.time() - start_time)
            await self._finalize_graph(graph, build_duration)
            
            self.logger.info(f"[SchemaGraphService] ✅ Grafo {graph.id} construido en {build_duration}s")
            return graph
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error construyendo grafo: {e}")
            return None
    
    async def get_graph(self, db_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el grafo activo de una base de datos.
        
        Args:
            db_id: ID de la base de datos
            user_id: ID del usuario
            
        Returns:
            Diccionario con el grafo o None si no existe
        """
        try:
            db = self.factory.get_db()
            
            # Buscar grafo activo
            graph = db.query(SchemaGraph).filter(
                SchemaGraph.database_id == db_id,
                SchemaGraph.user_id == user_id,
                SchemaGraph.is_active == True
            ).first()
            
            if not graph:
                return None
            
            # Buscar caché válido
            cache = db.query(GraphCache).filter(
                GraphCache.graph_id == graph.id,
                GraphCache.is_valid == True
            ).first()
            
            if cache:
                # Actualizar estadísticas de acceso
                cache.last_accessed_at = datetime.now(timezone.utc)
                cache.access_count += 1
                db.commit()
                
                return {
                    "id": str(graph.id),
                    "database_id": str(graph.database_id),
                    "version": graph.version,
                    "is_active": graph.is_active,
                    "total_tables": graph.total_tables,
                    "total_columns": graph.total_columns,
                    "total_relationships": graph.total_relationships,
                    "total_foreign_keys": graph.total_foreign_keys,
                    "total_many_to_many": graph.total_many_to_many,
                    "complexity_score": graph.complexity_score,
                    "is_complex": graph.is_complex,
                    "built_at": graph.built_at.isoformat() if graph.built_at else None,
                    "build_duration_seconds": graph.build_duration_seconds,
                    "nodes": cache.nodes_cache,
                    "edges": cache.edges_cache,
                    "adjacency_matrix": cache.adjacency_matrix,
                    "cache_info": {
                        "version": cache.cache_version,
                        "size_bytes": cache.cache_size_bytes,
                        "last_accessed": cache.last_accessed_at.isoformat() if cache.last_accessed_at else None,
                        "access_count": cache.access_count
                    }
                }
            else:
                # Retornar información básica sin caché
                return {
                    "id": str(graph.id),
                    "database_id": str(graph.database_id),
                    "version": graph.version,
                    "is_active": graph.is_active,
                    "total_tables": graph.total_tables,
                    "total_columns": graph.total_columns,
                    "total_relationships": graph.total_relationships,
                    "total_foreign_keys": graph.total_foreign_keys,
                    "total_many_to_many": graph.total_many_to_many,
                    "complexity_score": graph.complexity_score,
                    "is_complex": graph.is_complex,
                    "built_at": graph.built_at.isoformat() if graph.built_at else None,
                    "build_duration_seconds": graph.build_duration_seconds,
                    "note": "Caché no disponible, regenerar grafo"
                }
                
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error obteniendo grafo: {e}")
            return None
    
    async def _create_graph_record(self, db_id: UUID, user_id: UUID, snapshot_id: Optional[UUID]) -> Optional[SchemaGraph]:
        """Crea el registro del grafo en la base de datos"""
        try:
            # Desactivar grafos anteriores
            db = self.factory.get_db()
            db.query(SchemaGraph).filter(
                SchemaGraph.database_id == db_id,
                SchemaGraph.user_id == user_id,
                SchemaGraph.is_active == True
            ).update({"is_active": False})
            
            # Crear nuevo grafo
            graph = SchemaGraph(
                database_id=db_id,
                user_id=user_id,
                snapshot_id=snapshot_id,
                version="1.0",
                is_active=True
            )
            
            db.add(graph)
            db.commit()
            db.refresh(graph)
            
            self.logger.info(f"[SchemaGraphService] 📝 Grafo {graph.id} creado para DB {db_id}")
            return graph
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error creando grafo: {e}")
            return None
    
    async def _build_graph_structure(self, graph: SchemaGraph, schema: Dict[str, Any]) -> bool:
        """Construye la estructura del grafo (nodos y aristas)"""
        try:
            db = self.factory.get_db()
            
            # Extraer información del schema
            tables = schema.get('tables', {})
            relationships = schema.get('relationships', [])
            
            # Contadores para estadísticas
            total_tables = len(tables)
            total_columns = 0
            total_foreign_keys = 0
            total_many_to_many = 0
            
            # Crear nodos para tablas
            table_nodes = {}
            for table_name, table_info in tables.items():
                # Nodo de tabla
                table_node = GraphNode(
                    graph_id=graph.id,
                    node_type=self.NODE_TYPES["table"],
                    resource_id=f"table_{table_name}",
                    resource_name=table_name,
                    display_name=table_name,
                    description=table_info.get('description', f"Tabla {table_name}"),
                    properties={
                        "table_type": table_info.get('table_type', 'BASE TABLE'),
                        "row_count": table_info.get('row_count'),
                        "size_bytes": table_info.get('size_bytes'),
                        "comment": table_info.get('comment')
                    }
                )
                db.add(table_node)
                db.flush()  # Para obtener el ID
                table_nodes[table_name] = table_node
                
                # Nodos para columnas
                columns = table_info.get('columns', {})
                for col_name, col_info in columns.items():
                    total_columns += 1
                    
                    col_node = GraphNode(
                        graph_id=graph.id,
                        node_type=self.NODE_TYPES["column"],
                        resource_id=f"column_{table_name}_{col_name}",
                        resource_name=col_name,
                        display_name=col_name,
                        description=col_info.get('comment', f"Columna {col_name}"),
                        properties={
                            "data_type": col_info.get('data_type'),
                            "is_nullable": col_info.get('is_nullable'),
                            "is_primary_key": col_info.get('is_primary_key', False),
                            "is_foreign_key": col_info.get('is_foreign_key', False),
                            "default_value": col_info.get('default_value'),
                            "comment": col_info.get('comment')
                        }
                    )
                    db.add(col_node)
                    db.flush()
                    
                    # Arista HAS_COLUMN
                    has_column_edge = GraphEdge(
                        graph_id=graph.id,
                        source_node_id=table_node.id,
                        target_node_id=col_node.id,
                        edge_type=self.EDGE_TYPES["HAS_COLUMN"],
                        relationship_name=f"{table_name}_has_{col_name}",
                        cardinality="1:1",
                        is_optional=False
                    )
                    db.add(has_column_edge)
            
            # Crear aristas para relaciones
            for rel in relationships:
                source_table = rel.get('source_table')
                target_table = rel.get('target_table')
                rel_type = rel.get('type', 'FK')
                
                if source_table in table_nodes and target_table in table_nodes:
                    if rel_type == 'FK':
                        total_foreign_keys += 1
                        edge_type = self.EDGE_TYPES["FK_RELATION"]
                    elif rel_type == 'M2M':
                        total_many_to_many += 1
                        edge_type = self.EDGE_TYPES["MANY_TO_MANY"]
                    else:
                        edge_type = self.EDGE_TYPES["FK_RELATION"]
                    
                    # Arista de relación
                    rel_edge = GraphEdge(
                        graph_id=graph.id,
                        source_node_id=table_nodes[source_table].id,
                        target_node_id=table_nodes[target_table].id,
                        edge_type=edge_type,
                        relationship_name=rel.get('name', f"{source_table}_to_{target_table}"),
                        cardinality=rel.get('cardinality', '1:N'),
                        is_optional=rel.get('is_optional', True),
                        cascade_delete=rel.get('cascade_delete', False),
                        properties={
                            "source_column": rel.get('source_column'),
                            "target_column": rel.get('target_column'),
                            "constraint_name": rel.get('constraint_name'),
                            "on_update": rel.get('on_update'),
                            "on_delete": rel.get('on_delete')
                        }
                    )
                    db.add(rel_edge)
            
            # Actualizar estadísticas del grafo
            graph.total_tables = total_tables
            graph.total_columns = total_columns
            graph.total_foreign_keys = total_foreign_keys
            graph.total_many_to_many = total_many_to_many
            graph.total_relationships = total_foreign_keys + total_many_to_many
            
            db.commit()
            
            self.logger.info(f"[SchemaGraphService] ✅ Estructura del grafo construida: {total_tables} tablas, {total_columns} columnas, {graph.total_relationships} relaciones")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error construyendo estructura: {e}")
            return False
    
    async def _generate_graph_cache(self, graph: SchemaGraph) -> bool:
        """Genera el caché optimizado del grafo"""
        try:
            db = self.factory.get_db()
            
            # Obtener nodos y aristas
            nodes = db.query(GraphNode).filter(GraphNode.graph_id == graph.id).all()
            edges = db.query(GraphEdge).filter(GraphEdge.graph_id == graph.id).all()
            
            # Preparar caché de nodos
            nodes_cache = []
            for node in nodes:
                node_data = {
                    "id": str(node.id),
                    "type": node.node_type,
                    "resource_id": node.resource_id,
                    "resource_name": node.resource_name,
                    "display_name": node.display_name,
                    "description": node.description,
                    "synonyms": node.synonyms,
                    "properties": node.properties,
                    "x_position": node.x_position,
                    "y_position": node.y_position
                }
                nodes_cache.append(node_data)
            
            # Preparar caché de aristas
            edges_cache = []
            for edge in edges:
                edge_data = {
                    "id": str(edge.id),
                    "source_node_id": str(edge.source_node_id),
                    "target_node_id": str(edge.target_node_id),
                    "edge_type": edge.edge_type,
                    "relationship_name": edge.relationship_name,
                    "cardinality": edge.cardinality,
                    "is_optional": edge.is_optional,
                    "cascade_delete": edge.cascade_delete,
                    "properties": edge.properties,
                    "edge_path": edge.edge_path
                }
                edges_cache.append(edge_data)
            
            # Generar matriz de adyacencia
            adjacency_matrix = self._build_adjacency_matrix(nodes, edges)
            
            # Crear caché
            cache = GraphCache(
                graph_id=graph.id,
                nodes_cache=nodes_cache,
                edges_cache=edges_cache,
                adjacency_matrix=adjacency_matrix,
                cache_version="1.0",
                cache_size_bytes=len(json.dumps(nodes_cache + edges_cache)),
                is_valid=True
            )
            
            db.add(cache)
            db.commit()
            
            self.logger.info(f"[SchemaGraphService] ✅ Caché generado para grafo {graph.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error generando caché: {e}")
            return False
    
    def _build_adjacency_matrix(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> Dict[str, Any]:
        """Construye la matriz de adyacencia para búsquedas rápidas"""
        try:
            # Crear índice de nodos por ID
            node_index = {str(node.id): node.resource_name for node in nodes}
            
            # Inicializar matriz
            matrix = {}
            for node in nodes:
                matrix[node.resource_name] = {
                    "incoming": [],
                    "outgoing": [],
                    "self_loops": []
                }
            
            # Llenar matriz
            for edge in edges:
                source_name = node_index.get(str(edge.source_node_id))
                target_name = node_index.get(str(edge.target_node_id))
                
                if source_name and target_name:
                    if source_name == target_name:
                        matrix[source_name]["self_loops"].append({
                            "edge_id": str(edge.id),
                            "type": edge.edge_type,
                            "properties": edge.properties
                        })
                    else:
                        matrix[source_name]["outgoing"].append({
                            "target": target_name,
                            "edge_id": str(edge.id),
                            "type": edge.edge_type,
                            "properties": edge.properties
                        })
                        
                        matrix[target_name]["incoming"].append({
                            "source": source_name,
                            "edge_id": str(edge.id),
                            "type": edge.edge_type,
                            "properties": edge.properties
                        })
            
            return matrix
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error construyendo matriz de adyacencia: {e}")
            return {}
    
    async def _finalize_graph(self, graph: SchemaGraph, build_duration: int) -> bool:
        """Finaliza la construcción del grafo"""
        try:
            db = self.factory.get_db()
            
            graph.built_at = datetime.now(timezone.utc)
            graph.build_duration_seconds = build_duration
            
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error finalizando grafo: {e}")
            return False
    
    async def _mark_graph_failed(self, graph: SchemaGraph, error_code: str, error_detail: str) -> bool:
        """Marca el grafo como fallido"""
        try:
            db = self.factory.get_db()
            
            graph.is_active = False
            graph.graph_metadata = {
                "error_code": error_code,
                "error_detail": error_detail,
                "failed_at": datetime.now(timezone.utc).isoformat()
            }
            
            db.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error marcando grafo como fallido: {e}")
            return False
    
    async def invalidate_graph_cache(self, graph_id: UUID) -> bool:
        """Invalida el caché de un grafo"""
        try:
            db = self.factory.get_db()
            
            db.query(GraphCache).filter(
                GraphCache.graph_id == graph_id
            ).update({
                "is_valid": False,
                "updated_at": datetime.now(timezone.utc)
            })
            
            db.commit()
            self.logger.info(f"[SchemaGraphService] ✅ Caché invalidado para grafo {graph_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error invalidando caché: {e}")
            return False
    
    async def get_graph_statistics(self, db_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene estadísticas del grafo"""
        try:
            db = self.factory.get_db()
            
            graph = db.query(SchemaGraph).filter(
                SchemaGraph.database_id == db_id,
                SchemaGraph.user_id == user_id,
                SchemaGraph.is_active == True
            ).first()
            
            if not graph:
                return None
            
            return {
                "total_tables": graph.total_tables,
                "total_columns": graph.total_columns,
                "total_relationships": graph.total_relationships,
                "total_foreign_keys": graph.total_foreign_keys,
                "total_many_to_many": graph.total_many_to_many,
                "complexity_score": graph.complexity_score,
                "is_complex": graph.is_complex,
                "built_at": graph.built_at.isoformat() if graph.built_at else None,
                "build_duration_seconds": graph.build_duration_seconds
            }
            
        except Exception as e:
            self.logger.error(f"[SchemaGraphService] ❌ Error obteniendo estadísticas: {e}")
            return None
