#!/usr/bin/env python3
"""
SchemaGraphModel - Modelo para el grafo de relaciones del esquema
────────────────────────────────────────────────────────────────
Implementa:
- Nodos del grafo (tablas, columnas)
- Aristas del grafo (relaciones, foreign keys)
- Caché serializado para respuesta rápida
- Metadatos del grafo para análisis
"""

import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import BaseTable


class SchemaGraph(BaseTable):
    """Modelo principal para el grafo de relaciones del esquema"""
    
    __tablename__ = "schema_graphs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    database_id = Column(UUID(as_uuid=True), ForeignKey("database_connections.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # 🔧 FASE 2: Metadata del grafo
    snapshot_id = Column(UUID(as_uuid=True), nullable=True, comment="ID del snapshot del esquema")
    version = Column(String, nullable=False, default="1.0")
    is_active = Column(Boolean, nullable=False, default=True, comment="Grafo activo para esta DB")
    
    # 🔧 FASE 2: Estadísticas del grafo
    total_tables = Column(Integer, nullable=False, default=0)
    total_columns = Column(Integer, nullable=False, default=0)
    total_relationships = Column(Integer, nullable=False, default=0)
    total_foreign_keys = Column(Integer, nullable=False, default=0)
    total_many_to_many = Column(Integer, nullable=False, default=0)
    
    # 🔧 FASE 2: Caché del grafo (JSON serializado)
    graph_cache = Column(JSON, nullable=True, comment="Caché completo del grafo para respuesta rápida")
    graph_metadata = Column(JSON, nullable=True, comment="Metadatos del grafo (estadísticas, complejidad)")
    
    # 🔧 FASE 2: Información de construcción
    built_at = Column(DateTime(timezone=True), nullable=True, comment="Cuándo se construyó el grafo")
    build_duration_seconds = Column(Integer, nullable=True, comment="Duración de la construcción en segundos")
    
    # Timestamps estándar
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    database = relationship("DatabaseConnection", back_populates="schema_graphs")
    user = relationship("User", back_populates="schema_graphs")
    
    def __repr__(self):
        return f"<SchemaGraph(id={self.id}, tables={self.total_tables}, relationships={self.total_relationships})>"
    
    @property
    def complexity_score(self) -> float:
        """Calcula un score de complejidad del grafo"""
        if self.total_tables == 0:
            return 0.0
        
        # Fórmula: (relaciones + FK + M2M) / tablas * 10
        complexity = (self.total_relationships + self.total_foreign_keys + self.total_many_to_many) / self.total_tables * 10
        return min(100.0, max(0.0, complexity))
    
    @property
    def is_complex(self) -> bool:
        """Determina si el grafo es complejo (score > 50)"""
        return self.complexity_score > 50.0


class GraphNode(BaseTable):
    """Nodos del grafo (tablas y columnas)"""
    
    __tablename__ = "graph_nodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("schema_graphs.id"), nullable=False)
    
    # 🔧 FASE 2: Identificación del nodo
    node_type = Column(String, nullable=False, comment="table, column, relationship")
    resource_id = Column(String, nullable=False, comment="ID único del recurso en la DB")
    resource_name = Column(String, nullable=False, comment="Nombre del recurso")
    
    # 🔧 FASE 2: Metadatos del nodo
    display_name = Column(String, nullable=True, comment="Nombre para mostrar al usuario")
    description = Column(Text, nullable=True, comment="Descripción del nodo")
    synonyms = Column(JSON, nullable=True, comment="Sinónimos del nombre")
    
    # 🔧 FASE 2: Propiedades específicas por tipo
    properties = Column(JSON, nullable=True, comment="Propiedades específicas del nodo")
    
    # 🔧 FASE 2: Posición en el grafo (para visualización)
    x_position = Column(Integer, nullable=True, comment="Posición X en el grafo")
    y_position = Column(Integer, nullable=True, comment="Posición Y en el grafo")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    graph = relationship("SchemaGraph", back_populates="nodes")
    outgoing_edges = relationship("GraphEdge", foreign_keys="GraphEdge.source_node_id", back_populates="source_node")
    incoming_edges = relationship("GraphEdge", foreign_keys="GraphEdge.target_node_id", back_populates="target_node")
    
    def __repr__(self):
        return f"<GraphNode(type={self.node_type}, name={self.resource_name})>"


class GraphEdge(BaseTable):
    """Aristas del grafo (relaciones entre nodos)"""
    
    __tablename__ = "graph_edges"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("schema_graphs.id"), nullable=False)
    
    # 🔧 FASE 2: Nodos conectados
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("graph_nodes.id"), nullable=False)
    
    # 🔧 FASE 2: Tipo de relación
    edge_type = Column(String, nullable=False, comment="HAS_COLUMN, FK_RELATION, MANY_TO_MANY, INDEX_ON")
    relationship_name = Column(String, nullable=True, comment="Nombre de la relación")
    
    # 🔧 FASE 2: Metadatos de la relación
    cardinality = Column(String, nullable=True, comment="1:1, 1:N, N:M")
    is_optional = Column(Boolean, nullable=True, comment="Si la relación es opcional")
    cascade_delete = Column(Boolean, nullable=True, comment="Si hay cascade delete")
    
    # 🔧 FASE 2: Propiedades específicas
    properties = Column(JSON, nullable=True, comment="Propiedades específicas de la relación")
    
    # 🔧 FASE 2: Posición de la arista (para visualización)
    edge_path = Column(JSON, nullable=True, comment="Path de la arista (puntos intermedios)")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    graph = relationship("SchemaGraph", back_populates="edges")
    source_node = relationship("GraphNode", foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node = relationship("GraphNode", foreign_keys=[target_node_id], back_populates="incoming_edges")
    
    def __repr__(self):
        return f"<GraphEdge({self.source_node.resource_name} -> {self.target_node.resource_name}: {self.edge_type})>"


class GraphCache(BaseTable):
    """Caché optimizado del grafo para respuesta rápida"""
    
    __tablename__ = "graph_caches"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    graph_id = Column(UUID(as_uuid=True), ForeignKey("schema_graphs.id"), nullable=False)
    
    # 🔧 FASE 2: Caché serializado
    nodes_cache = Column(JSON, nullable=False, comment="Caché de nodos optimizado")
    edges_cache = Column(JSON, nullable=False, comment="Caché de aristas optimizado")
    adjacency_matrix = Column(JSON, nullable=True, comment="Matriz de adyacencia para búsquedas rápidas")
    
    # 🔧 FASE 2: Metadatos del caché
    cache_version = Column(String, nullable=False, default="1.0")
    cache_size_bytes = Column(Integer, nullable=True, comment="Tamaño del caché en bytes")
    is_valid = Column(Boolean, nullable=False, default=True, comment="Si el caché es válido")
    
    # 🔧 FASE 2: Información de performance
    last_accessed_at = Column(DateTime(timezone=True), nullable=True, comment="Último acceso al caché")
    access_count = Column(Integer, nullable=False, default=0, comment="Número de accesos al caché")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    graph = relationship("SchemaGraph", back_populates="caches")
    
    def __repr__(self):
        return f"<GraphCache(graph_id={self.graph_id}, valid={self.is_valid}, size={self.cache_size_bytes} bytes)>"


# 🔧 FASE 2: Agregar relaciones al modelo SchemaGraph
def add_graph_relationships():
    """Agrega las relaciones faltantes al modelo SchemaGraph"""
    SchemaGraph.nodes = relationship("GraphNode", back_populates="graph", cascade="all, delete-orphan")
    SchemaGraph.edges = relationship("GraphEdge", back_populates="graph", cascade="all, delete-orphan")
    SchemaGraph.caches = relationship("GraphCache", back_populates="graph", cascade="all, delete-orphan")


# Ejecutar la función para agregar relaciones
add_graph_relationships()
