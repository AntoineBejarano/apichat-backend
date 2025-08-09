-- =====================================================
-- TABLA: detailed_schema_cache
-- =====================================================
-- Cache multi-capa para esquemas de base de datos
-- L1: compact (para prompts AI)  
-- L2: detailed (para validación/rewrites)
-- L3: fingerprint (para invalidación barata)
-- =====================================================

CREATE TABLE detailed_schema_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    db_id UUID NOT NULL,
    
    -- 🔍 Fingerprint para invalidación rápida
    fingerprint TEXT NOT NULL,
    fingerprint_light TEXT NOT NULL, -- Hash ligero para checks baratos
    
    -- 📊 Snapshots del esquema
    snapshot JSONB NOT NULL,          -- Schema detallado completo
    compact TEXT NOT NULL,            -- Schema compacto para prompts AI
    
    -- ⚡ Metadatos de performance  
    table_count INTEGER NOT NULL DEFAULT 0,
    total_columns INTEGER NOT NULL DEFAULT 0,
    enrichment_level INTEGER NOT NULL DEFAULT 1, -- 1=basic, 2=with_fks, 3=with_stats
    
    -- 🕒 Timestamps
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enriched_at TIMESTAMPTZ NULL, -- Cuando se enriqueció con FKs/stats
    
    -- 🔒 Constraints
    UNIQUE (user_id, db_id)
);

-- =====================================================
-- ÍNDICES PARA PERFORMANCE
-- =====================================================

-- Índice principal para búsquedas por user + db
CREATE INDEX idx_schema_cache_user_db ON detailed_schema_cache(user_id, db_id);

-- Índice para invalidación por fingerprint
CREATE INDEX idx_schema_cache_fingerprint ON detailed_schema_cache(fingerprint_light);

-- Índice para limpieza de cache viejo
CREATE INDEX idx_schema_cache_accessed ON detailed_schema_cache(last_accessed);

-- Índice para jobs de enriquecimiento
CREATE INDEX idx_schema_cache_enrichment ON detailed_schema_cache(enrichment_level, generated_at) 
WHERE enrichment_level < 3;

-- =====================================================
-- COMENTARIOS DE DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE detailed_schema_cache IS 'Cache multi-capa para esquemas de BD con fingerprinting e invalidación inteligente';
COMMENT ON COLUMN detailed_schema_cache.fingerprint IS 'Hash completo del esquema para detección de cambios';
COMMENT ON COLUMN detailed_schema_cache.fingerprint_light IS 'Hash ligero (solo nombres de tablas) para checks baratos';
COMMENT ON COLUMN detailed_schema_cache.snapshot IS 'Schema detallado completo (tablas, columnas, tipos, FKs, índices)';
COMMENT ON COLUMN detailed_schema_cache.compact IS 'Schema compacto optimizado para prompts de AI';
COMMENT ON COLUMN detailed_schema_cache.enrichment_level IS '1=básico, 2=con FKs, 3=con estadísticas';
