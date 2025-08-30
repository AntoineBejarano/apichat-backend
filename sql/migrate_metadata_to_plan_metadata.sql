-- Migración: Cambiar columna 'metadata' a 'plan_metadata' en user_plans
-- Fecha: $(date)
-- Descripción: Soluciona conflicto con atributo reservado 'metadata' en SQLAlchemy

-- Verificar si la columna 'metadata' existe
DO $$
BEGIN
    -- Si existe la columna 'metadata', renombrarla a 'plan_metadata'
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_plans' 
        AND column_name = 'metadata'
    ) THEN
        -- Renombrar la columna
        ALTER TABLE user_plans RENAME COLUMN metadata TO plan_metadata;
        
        RAISE NOTICE 'Columna metadata renombrada a plan_metadata en user_plans';
    ELSE
        RAISE NOTICE 'Columna metadata no existe en user_plans, no se requiere migración';
    END IF;
END $$;

-- Verificar el resultado
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'user_plans' 
AND column_name IN ('metadata', 'plan_metadata')
ORDER BY column_name;
