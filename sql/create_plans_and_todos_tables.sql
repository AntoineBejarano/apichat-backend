-- =====================================================
-- 🎯 FASE 1: CREAR TABLAS PARA PLANES Y TO-DOS
-- =====================================================

-- 1. Tabla de PLANES (contenedores del objetivo global)
CREATE TABLE IF NOT EXISTS user_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'running', 'completed', 'failed', 'paused')),
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    
    -- Estimaciones y métricas
    estimated_duration INTEGER, -- en minutos
    actual_duration INTEGER,    -- en minutos
    
    -- Metadatos
    plan_metadata JSONB DEFAULT '{}', -- recursos usados, contexto, etc.
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Agregar constraint de foreign key si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'user_plans_user_id_fkey' 
        AND table_name = 'user_plans'
    ) THEN
        ALTER TABLE user_plans 
        ADD CONSTRAINT user_plans_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 2. Tabla de PLAN_TASKS (to-dos atómicos)
CREATE TABLE IF NOT EXISTS plan_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL,
    
    -- Información de la tarea
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'done', 'failed', 'skipped')),
    
    -- Orden y dependencias
    order_index INTEGER NOT NULL,
    dependencies JSONB DEFAULT '[]', -- IDs de tareas de las que depende
    
    -- Estimaciones y métricas
    estimated_effort INTEGER, -- en minutos
    actual_effort INTEGER,    -- en minutos
    
    -- Resultados y errores
    outcome JSONB DEFAULT '{}', -- resultado de la ejecución
    errors JSONB DEFAULT '[]',  -- errores encontrados
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Agregar constraint de foreign key si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'plan_tasks_plan_id_fkey' 
        AND table_name = 'plan_tasks'
    ) THEN
        ALTER TABLE plan_tasks 
        ADD CONSTRAINT plan_tasks_plan_id_fkey 
        FOREIGN KEY (plan_id) REFERENCES user_plans(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 3. Tabla de PLAN_EXECUTION_STATE (seguimiento en Redis)
CREATE TABLE IF NOT EXISTS plan_execution_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL,
    run_id VARCHAR(255) NOT NULL, -- ID único para esta ejecución
    
    -- Estado de ejecución
    redis_key VARCHAR(255) NOT NULL, -- clave en Redis
    current_task_index INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'initialized' CHECK (status IN ('initialized', 'running', 'paused', 'completed', 'failed')),
    
    -- Metadatos de ejecución
    execution_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agregar constraints si no existen
DO $$
BEGIN
    -- Foreign key constraint
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'plan_execution_state_plan_id_fkey' 
        AND table_name = 'plan_execution_state'
    ) THEN
        ALTER TABLE plan_execution_state 
        ADD CONSTRAINT plan_execution_state_plan_id_fkey 
        FOREIGN KEY (plan_id) REFERENCES user_plans(id) ON DELETE CASCADE;
    END IF;
    
    -- Unique constraint
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'plan_execution_state_plan_run_unique' 
        AND table_name = 'plan_execution_state'
    ) THEN
        ALTER TABLE plan_execution_state 
        ADD CONSTRAINT plan_execution_state_plan_run_unique 
        UNIQUE(plan_id, run_id);
    END IF;
END $$;

-- 4. Tabla de PLAN_OUTCOMES (métricas y resultados)
CREATE TABLE IF NOT EXISTS plan_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL,
    
    -- Métricas de ejecución
    total_tasks INTEGER NOT NULL,
    completed_tasks INTEGER NOT NULL DEFAULT 0,
    failed_tasks INTEGER NOT NULL DEFAULT 0,
    skipped_tasks INTEGER NOT NULL DEFAULT 0,
    
    -- Tiempos
    total_estimated_time INTEGER, -- en minutos
    total_actual_time INTEGER,    -- en minutos
    
    -- Resultados
    success_rate DECIMAL(5,2) DEFAULT 0.0, -- porcentaje de éxito
    outcome_summary TEXT,
    
    -- Metadatos
    execution_metadata JSONB DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agregar constraint de foreign key si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'plan_outcomes_plan_id_fkey' 
        AND table_name = 'plan_outcomes'
    ) THEN
        ALTER TABLE plan_outcomes 
        ADD CONSTRAINT plan_outcomes_plan_id_fkey 
        FOREIGN KEY (plan_id) REFERENCES user_plans(id) ON DELETE CASCADE;
    END IF;
END $$;

-- =====================================================
-- 📊 ÍNDICES PARA OPTIMIZACIÓN
-- =====================================================

-- Índices para user_plans
CREATE INDEX IF NOT EXISTS idx_user_plans_user_id ON user_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_user_plans_status ON user_plans(status);
CREATE INDEX IF NOT EXISTS idx_user_plans_created_at ON user_plans(created_at);
CREATE INDEX IF NOT EXISTS idx_user_plans_user_status ON user_plans(user_id, status);

-- Índices para plan_tasks
CREATE INDEX IF NOT EXISTS idx_plan_tasks_plan_id ON plan_tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_status ON plan_tasks(status);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_order ON plan_tasks(plan_id, order_index);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_plan_status ON plan_tasks(plan_id, status);

-- Índices para plan_execution_state
CREATE INDEX IF NOT EXISTS idx_plan_execution_state_plan_id ON plan_execution_state(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_execution_state_run_id ON plan_execution_state(run_id);
CREATE INDEX IF NOT EXISTS idx_plan_execution_state_status ON plan_execution_state(status);

-- Índices para plan_outcomes
CREATE INDEX IF NOT EXISTS idx_plan_outcomes_plan_id ON plan_outcomes(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_outcomes_created_at ON plan_outcomes(created_at);

-- =====================================================
-- 🔄 TRIGGERS PARA ACTUALIZAR updated_at
-- =====================================================

-- Trigger para user_plans
CREATE OR REPLACE FUNCTION update_user_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_user_plans_updated_at
    BEFORE UPDATE ON user_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_user_plans_updated_at();

-- Trigger para plan_execution_state
CREATE OR REPLACE FUNCTION update_plan_execution_state_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_plan_execution_state_updated_at
    BEFORE UPDATE ON plan_execution_state
    FOR EACH ROW
    EXECUTE FUNCTION update_plan_execution_state_updated_at();

-- =====================================================
-- 📝 COMENTARIOS EN LAS TABLAS
-- =====================================================

COMMENT ON TABLE user_plans IS 'Contenedores de objetivos globales del usuario (ej: "Migrar a microservicios")';
COMMENT ON TABLE plan_tasks IS 'Tareas atómicas ejecutables dentro de un plan (ej: "Crear tabla users")';
COMMENT ON TABLE plan_execution_state IS 'Estado de ejecución de planes en Redis para seguimiento en tiempo real';
COMMENT ON TABLE plan_outcomes IS 'Métricas y resultados de planes completados para análisis y recomendaciones';

COMMENT ON COLUMN user_plans.status IS 'Estado del plan: draft, running, completed, failed, paused';
COMMENT ON COLUMN plan_tasks.status IS 'Estado de la tarea: pending, running, done, failed, skipped';
COMMENT ON COLUMN plan_tasks.order_index IS 'Orden de ejecución de la tarea dentro del plan';
COMMENT ON COLUMN plan_tasks.dependencies IS 'Array de IDs de tareas de las que depende esta tarea';
COMMENT ON COLUMN plan_execution_state.run_id IS 'ID único para esta ejecución del plan';
COMMENT ON COLUMN plan_execution_state.redis_key IS 'Clave en Redis para el estado de ejecución';

-- =====================================================
-- ✅ VERIFICACIÓN DE CREACIÓN
-- =====================================================

-- Verificar que las tablas se crearon correctamente
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name IN ('user_plans', 'plan_tasks', 'plan_execution_state', 'plan_outcomes')
ORDER BY table_name, ordinal_position;

-- Mostrar resumen de tablas creadas
SELECT 
    'user_plans' as tabla,
    'Contenedor del objetivo global' as descripcion,
    COUNT(*) as columnas
FROM information_schema.columns WHERE table_name = 'user_plans'
UNION ALL
SELECT 
    'plan_tasks' as tabla,
    'Tareas atómicas ejecutables' as descripcion,
    COUNT(*) as columnas
FROM information_schema.columns WHERE table_name = 'plan_tasks'
UNION ALL
SELECT 
    'plan_execution_state' as tabla,
    'Estado de ejecución en Redis' as descripcion,
    COUNT(*) as columnas
FROM information_schema.columns WHERE table_name = 'plan_execution_state'
UNION ALL
SELECT 
    'plan_outcomes' as tabla,
    'Métricas y resultados' as descripcion,
    COUNT(*) as columnas
FROM information_schema.columns WHERE table_name = 'plan_outcomes';
