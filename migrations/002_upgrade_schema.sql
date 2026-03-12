-- Migration 002: Add ensemble sentiment, contract features, backtesting, and new tables
-- Run after init_db.sql and fix_metadata_column.sql
-- All new columns are nullable so existing data is unaffected.

-- ============================================================================
-- 1. Add ensemble sentiment columns to sentiment_analysis
-- ============================================================================
ALTER TABLE sentiment_analysis ADD COLUMN IF NOT EXISTS vader_score DECIMAL(4,3);
ALTER TABLE sentiment_analysis ADD COLUMN IF NOT EXISTS textblob_score DECIMAL(4,3);
ALTER TABLE sentiment_analysis ADD COLUMN IF NOT EXISTS ensemble_score DECIMAL(4,3);

-- ============================================================================
-- 2. Add gap tracking columns to detected_gaps
-- ============================================================================
ALTER TABLE detected_gaps ADD COLUMN IF NOT EXISTS social_sources_count INTEGER DEFAULT 0;
ALTER TABLE detected_gaps ADD COLUMN IF NOT EXISTS contract_features JSONB;
ALTER TABLE detected_gaps ADD COLUMN IF NOT EXISTS resolution_outcome VARCHAR(20);
ALTER TABLE detected_gaps ADD COLUMN IF NOT EXISTS was_correct BOOLEAN;
ALTER TABLE detected_gaps ADD COLUMN IF NOT EXISTS realized_edge DECIMAL(5,4);

-- ============================================================================
-- 3. Create sentiment_snapshots table (rolling window aggregates)
-- ============================================================================
CREATE TABLE IF NOT EXISTS sentiment_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    window_hours INTEGER NOT NULL,
    avg_score DECIMAL(4,3),
    post_count INTEGER DEFAULT 0,
    positive_ratio DECIMAL(4,3),
    sentiment_trend DECIMAL(4,3),
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sentiment_snap_contract ON sentiment_snapshots(contract_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_snap_time ON sentiment_snapshots(snapshot_at DESC);

-- ============================================================================
-- 4. Create backtest_results table
-- ============================================================================
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    gap_type VARCHAR(50),
    threshold DECIMAL(5,2) NOT NULL,
    total_predictions INTEGER DEFAULT 0,
    correct_predictions INTEGER DEFAULT 0,
    win_rate DECIMAL(5,4),
    avg_edge DECIMAL(5,4),
    expected_roi DECIMAL(5,4),
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    result_metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_backtest_time ON backtest_results(computed_at DESC);

-- ============================================================================
-- 5. Additional indexes for performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_gaps_resolved ON detected_gaps(resolved);
CREATE INDEX IF NOT EXISTS idx_gaps_was_correct ON detected_gaps(was_correct) WHERE was_correct IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sentiment_ensemble ON sentiment_analysis(ensemble_score) WHERE ensemble_score IS NOT NULL;
