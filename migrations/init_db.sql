-- Polymarket Pricing Gap Detection System
-- Database Initialization Script

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Contracts Table
-- Stores Polymarket contract data with historical odds tracking
CREATE TABLE contracts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_id VARCHAR(255) UNIQUE NOT NULL,
    question TEXT NOT NULL,
    description TEXT,
    end_date TIMESTAMP,
    category VARCHAR(100),
    current_yes_odds DECIMAL(5,4),
    current_no_odds DECIMAL(5,4),
    volume_24h DECIMAL(15,2),
    liquidity DECIMAL(15,2),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical Odds Table
-- Tracks odds changes over time for trend analysis
CREATE TABLE historical_odds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    yes_odds DECIMAL(5,4) NOT NULL,
    no_odds DECIMAL(5,4) NOT NULL,
    volume DECIMAL(15,2),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Social Posts Table
-- Stores social media posts for sentiment analysis
CREATE TABLE social_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id VARCHAR(255) UNIQUE NOT NULL,
    platform VARCHAR(50) NOT NULL, -- 'twitter', 'reddit', etc.
    author VARCHAR(255),
    content TEXT NOT NULL,
    url TEXT,
    engagement_score INTEGER DEFAULT 0, -- likes, upvotes, etc.
    posted_at TIMESTAMP NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    related_contracts UUID[] -- Array of related contract IDs
);

-- Sentiment Analysis Table
-- Stores analyzed sentiment for posts and aggregated by contract
CREATE TABLE sentiment_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID REFERENCES social_posts(id) ON DELETE CASCADE,
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    sentiment_score DECIMAL(4,3), -- -1.0 to 1.0
    sentiment_label VARCHAR(20), -- 'positive', 'negative', 'neutral'
    confidence DECIMAL(4,3), -- 0.0 to 1.0
    topics TEXT[], -- Extracted topics/keywords
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Detected Gaps Table
-- Records identified pricing gaps with analysis
CREATE TABLE detected_gaps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    gap_type VARCHAR(50) NOT NULL, -- 'sentiment_mismatch', 'info_asymmetry', 'arbitrage', 'pattern_deviation'
    confidence_score INTEGER NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
    explanation TEXT NOT NULL,
    evidence JSONB, -- Structured evidence data
    market_odds DECIMAL(5,4),
    implied_odds DECIMAL(5,4), -- What odds should be based on analysis
    edge_percentage DECIMAL(5,2), -- Potential edge in percentage
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    resolved_at TIMESTAMP
);

-- System Logs Table
-- Tracks system events, errors, and performance metrics
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    log_level VARCHAR(20) NOT NULL, -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    agent_name VARCHAR(100), -- Which agent generated the log
    message TEXT NOT NULL,
    log_metadata JSONB, -- Additional structured data (renamed from 'metadata' to avoid conflicts)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Aggregated Sentiment Table (Materialized View for performance)
-- Pre-computed sentiment aggregations per contract for faster queries
CREATE MATERIALIZED VIEW contract_sentiment_summary AS
SELECT
    c.id as contract_id,
    c.contract_id as external_contract_id,
    c.question,
    COUNT(DISTINCT sp.id) as total_posts,
    AVG(sa.sentiment_score) as avg_sentiment,
    COUNT(CASE WHEN sa.sentiment_label = 'positive' THEN 1 END) as positive_count,
    COUNT(CASE WHEN sa.sentiment_label = 'negative' THEN 1 END) as negative_count,
    COUNT(CASE WHEN sa.sentiment_label = 'neutral' THEN 1 END) as neutral_count,
    MAX(sp.posted_at) as latest_post_time,
    SUM(sp.engagement_score) as total_engagement
FROM contracts c
LEFT JOIN sentiment_analysis sa ON c.id = sa.contract_id
LEFT JOIN social_posts sp ON sa.post_id = sp.id
WHERE sp.posted_at > NOW() - INTERVAL '24 hours'
GROUP BY c.id, c.contract_id, c.question;

-- Indexes for Performance
CREATE INDEX idx_contracts_active ON contracts(active);
CREATE INDEX idx_contracts_end_date ON contracts(end_date);
CREATE INDEX idx_contracts_category ON contracts(category);
CREATE INDEX idx_historical_odds_contract ON historical_odds(contract_id, recorded_at DESC);
CREATE INDEX idx_social_posts_platform ON social_posts(platform);
CREATE INDEX idx_social_posts_posted_at ON social_posts(posted_at DESC);
CREATE INDEX idx_social_posts_related_contracts ON social_posts USING GIN(related_contracts);
CREATE INDEX idx_sentiment_contract ON sentiment_analysis(contract_id);
CREATE INDEX idx_sentiment_analyzed_at ON sentiment_analysis(analyzed_at DESC);
CREATE INDEX idx_detected_gaps_contract ON detected_gaps(contract_id);
CREATE INDEX idx_detected_gaps_confidence ON detected_gaps(confidence_score DESC);
CREATE INDEX idx_detected_gaps_detected_at ON detected_gaps(detected_at DESC);
CREATE INDEX idx_system_logs_level ON system_logs(log_level);
CREATE INDEX idx_system_logs_created_at ON system_logs(created_at DESC);

-- Function to refresh materialized view
CREATE OR REPLACE FUNCTION refresh_contract_sentiment_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW contract_sentiment_summary;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for contracts table
CREATE TRIGGER update_contracts_updated_at
    BEFORE UPDATE ON contracts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to archive old data (data retention)
CREATE OR REPLACE FUNCTION archive_old_data()
RETURNS void AS $$
BEGIN
    -- Archive social posts older than 30 days
    DELETE FROM social_posts
    WHERE posted_at < NOW() - INTERVAL '30 days';

    -- Archive sentiment analysis older than 30 days
    DELETE FROM sentiment_analysis
    WHERE analyzed_at < NOW() - INTERVAL '30 days';

    -- Archive system logs older than 90 days (except errors)
    DELETE FROM system_logs
    WHERE created_at < NOW() - INTERVAL '90 days'
    AND log_level NOT IN ('ERROR', 'CRITICAL');

    -- Refresh materialized view
    REFRESH MATERIALIZED VIEW contract_sentiment_summary;
END;
$$ LANGUAGE plpgsql;

-- Sample queries for common operations
COMMENT ON TABLE contracts IS 'Stores active and historical Polymarket contracts';
COMMENT ON TABLE detected_gaps IS 'Pricing gaps identified by the system with confidence scores';
COMMENT ON MATERIALIZED VIEW contract_sentiment_summary IS 'Pre-aggregated sentiment data for fast queries. Refresh regularly.';

-- Grant permissions (adjust username as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO polymarket_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO polymarket_user;

-- Initial system log entry
INSERT INTO system_logs (log_level, agent_name, message, log_metadata)
VALUES ('INFO', 'SYSTEM', 'Database initialized successfully', '{"version": "1.0.0", "initialized_at": "now"}');

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema created successfully!';
    RAISE NOTICE 'Tables created: contracts, historical_odds, social_posts, sentiment_analysis, detected_gaps, system_logs';
    RAISE NOTICE 'Materialized view created: contract_sentiment_summary';
    RAISE NOTICE 'Remember to refresh the materialized view periodically!';
END $$;
