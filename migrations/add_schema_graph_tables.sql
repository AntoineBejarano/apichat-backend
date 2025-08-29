-- 🔧 FASE 2: Migración para agregar tablas del grafo de schema
-- Fecha: $(date)
-- Descripción: Agregar tablas para el grafo de relaciones del esquema

-- Crear tabla schema_graphs
CREATE TABLE IF NOT EXISTS schema_graphs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    database_id UUID NOT NULL REFERENCES database_connections(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- 🔧 FASE 2: Metadata del grafo
    snapshot_id UUID,
    version VARCHAR(20) NOT NULL DEFAULT '1.0',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 🔧 FASE 2: Estadísticas del grafo
    total_tables INTEGER NOT NULL DEFAULT 0,
    total_columns INTEGER NOT NULL DEFAULT 0,
    total_relationships INTEGER NOT NULL DEFAULT 0,
    total_foreign_keys INTEGER NOT NULL DEFAULT 0,
    total_many_to_many INTEGER NOT NULL DEFAULT 0,
    
    -- 🔧 FASE 2: Caché del grafo
    graph_cache JSONB,
    graph_metadata JSONB,
    
    -- 🔧 FASE 2: Información de construcción
    built_at TIMESTAMP WITH TIME ZONE,
    build_duration_seconds INTEGER,
    
    -- Timestamps estándar
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear tabla graph_nodes
CREATE TABLE IF NOT EXISTS graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_id UUID NOT NULL REFERENCES schema_graphs(id) ON DELETE CASCADE,
    
    -- 🔧 FASE 2: Identificación del nodo
    node_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    resource_name VARCHAR(255) NOT NULL,
    
    -- 🔧 FASE 2: Metadatos del nodo
    display_name VARCHAR(255),
    description TEXT,
    synonyms JSONB,
    
    -- 🔧 FASE 2: Propiedades específicas
    properties JSONB,
    
    -- 🔧 FASE 2: Posición en el grafo
    x_position INTEGER,
    y_position INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear tabla graph_edges
CREATE TABLE IF NOT EXISTS graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_id UUID NOT NULL REFERENCES schema_graphs(id) ON DELETE CASCADE,
    
    -- 🔧 FASE 2: Nodos conectados
    source_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    
    -- 🔧 FASE 2: Tipo de relación
    edge_type VARCHAR(100) NOT NULL,
    relationship_name VARCHAR(255),
    
    -- 🔧 FASE 2: Metadatos de la relación
    cardinality VARCHAR(20),
    is_optional BOOLEAN,
    cascade_delete BOOLEAN,
    
    -- 🔧 FASE 2: Propiedades específicas
    properties JSONB,
    
    -- 🔧 FASE 2: Posición de la arista
    edge_path JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear tabla graph_caches
CREATE TABLE IF NOT EXISTS graph_caches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_id UUID NOT NULL REFERENCES schema_graphs(id) ON DELETE CASCADE,
    
    -- 🔧 FASE 2: Caché serializado
    nodes_cache JSONB NOT NULL,
    edges_cache JSONB NOT NULL,
    adjacency_matrix JSONB,
    
    -- 🔧 FASE 2: Metadatos del caché
    cache_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    cache_size_bytes INTEGER,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 🔧 FASE 2: Información de performance
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    access_count INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_schema_graphs_database_id ON schema_graphs(database_id);
CREATE INDEX IF NOT EXISTS idx_schema_graphs_user_id ON schema_graphs(user_id);
CREATE INDEX IF NOT EXISTS idx_schema_graphs_is_active ON schema_graphs(is_active);
CREATE INDEX IF NOT EXISTS idx_schema_graphs_snapshot_id ON schema_graphs(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph_id ON graph_nodes(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_node_type ON graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_resource_id ON graph_nodes(resource_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_resource_name ON graph_nodes(resource_name);

CREATE INDEX IF NOT EXISTS idx_graph_edges_graph_id ON graph_edges(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source_node_id ON graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target_node_id ON graph_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_edge_type ON graph_edges(edge_type);

CREATE INDEX IF NOT EXISTS idx_graph_caches_graph_id ON graph_caches(graph_id);
CREATE INDEX IF NOT EXISTS idx_graph_caches_is_valid ON graph_caches(is_valid);

-- Crear índices compuestos para búsquedas comunes
CREATE INDEX IF NOT EXISTS idx_schema_graphs_db_active ON schema_graphs(database_id, is_active);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_graph_type ON graph_nodes(graph_id, node_type);
CREATE INDEX IF NOT EXISTS idx_graph_edges_graph_type ON graph_edges(graph_id, edge_type);

-- Agregar comentarios a las tablas
COMMENT ON TABLE schema_graphs IS '🔧 FASE 2: Grafo de relaciones del esquema de base de datos';
COMMENT ON TABLE graph_nodes IS '🔧 FASE 2: Nodos del grafo (tablas, columnas, relaciones)';
COMMENT ON TABLE graph_edges IS '🔧 FASE 2: Aristas del grafo (relaciones entre nodos)';
COMMENT ON TABLE graph_caches IS '🔧 FASE 2: Caché optimizado del grafo para respuesta rápida';

-- Comentarios de columnas importantes
COMMENT ON COLUMN schema_graphs.is_active IS 'Si el grafo está activo para esta DB';
COMMENT ON COLUMN schema_graphs.complexity_score IS 'Score de complejidad calculado automáticamente';
COMMENT ON COLUMN graph_nodes.node_type IS 'Tipo de nodo: table, column, relationship';
COMMENT ON COLUMN graph_edges.edge_type IS 'Tipo de arista: HAS_COLUMN, FK_RELATION, MANY_TO_MANY';
COMMENT ON COLUMN graph_caches.adjacency_matrix IS 'Matriz de adyacencia para búsquedas rápidas';

-- Crear función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_schema_graphs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_graph_nodes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_graph_edges_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_graph_caches_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear triggers para updated_at
CREATE TRIGGER trigger_update_schema_graphs_updated_at
    BEFORE UPDATE ON schema_graphs
    FOR EACH ROW
    EXECUTE FUNCTION update_schema_graphs_updated_at();

CREATE TRIGGER trigger_update_graph_nodes_updated_at
    BEFORE UPDATE ON graph_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_nodes_updated_at();

CREATE TRIGGER trigger_update_graph_edges_updated_at
    BEFORE UPDATE ON graph_edges
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_edges_updated_at();

CREATE TRIGGER trigger_update_graph_caches_updated_at
    BEFORE UPDATE ON graph_caches
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_caches_updated_at();

-- Crear función para calcular complexity_score
CREATE OR REPLACE FUNCTION calculate_graph_complexity(
    p_total_tables INTEGER,
    p_total_relationships INTEGER,
    p_total_foreign_keys INTEGER,
    p_total_many_to_many INTEGER
) RETURNS FLOAT AS $$
BEGIN
    IF p_total_tables = 0 THEN
        RETURN 0.0;
    END IF;
    
    -- Fórmula: (relaciones + FK + M2M) / tablas * 10
    RETURN LEAST(100.0, GREATEST(0.0, 
        (p_total_relationships + p_total_foreign_keys + p_total_many_to_many)::FLOAT / p_total_tables * 10
    ));
END;
$$ LANGUAGE plpgsql;

-- Crear función para actualizar complexity_score automáticamente
CREATE OR REPLACE FUNCTION update_graph_complexity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.complexity_score = calculate_graph_complexity(
        NEW.total_tables,
        NEW.total_relationships,
        NEW.total_foreign_keys,
        NEW.total_many_to_many
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger para complexity_score
CREATE TRIGGER trigger_update_graph_complexity
    BEFORE INSERT OR UPDATE ON schema_graphs
    FOR EACH ROW
    EXECUTE FUNCTION update_graph_complexity();

-- Verificar que la migración se completó exitosamente
SELECT '🔧 FASE 2: Migración completada exitosamente' as status;
SELECT COUNT(*) as total_schema_graphs FROM schema_graphs;
SELECT COUNT(*) as total_graph_nodes FROM graph_nodes;
SELECT COUNT(*) as total_graph_edges FROM graph_edges;
SELECT COUNT(*) as total_graph_caches FROM graph_caches;
