-- Migration 003: Add cycle_runs table for cycle history tracking

CREATE TABLE IF NOT EXISTS cycle_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_number INTEGER NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    duration_seconds DECIMAL(10,2),
    success BOOLEAN DEFAULT FALSE,
    contracts_collected INTEGER DEFAULT 0,
    posts_collected INTEGER DEFAULT 0,
    sentiments_analyzed INTEGER DEFAULT 0,
    gaps_detected INTEGER DEFAULT 0,
    llm_provider VARCHAR(50),
    errors JSONB,
    cycle_metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_cycle_runs_started_at ON cycle_runs(started_at DESC);
