-- Fix system_logs table to rename metadata column to log_metadata
-- Run this in pgAdmin Query Tool if you have the old schema

-- Check if the old column exists first
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'metadata'
    ) THEN
        -- Rename the column
        ALTER TABLE system_logs RENAME COLUMN metadata TO log_metadata;
        RAISE NOTICE 'Column renamed from metadata to log_metadata';
    ELSE
        RAISE NOTICE 'Column already named log_metadata or does not exist';
    END IF;
END $$;
