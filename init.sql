-- Database initialization script for Jenkins AI Chatbot
-- This script creates the initial database schema and indexes

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- AI interactions audit table
CREATE TABLE IF NOT EXISTS ai_interactions (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_query TEXT NOT NULL,
    ai_response TEXT,
    intent_detected VARCHAR(255),
    permissions_used TEXT[],
    actions_planned JSONB,
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    confidence REAL,
    claude_model VARCHAR(100)
);

-- Jenkins API calls audit table
CREATE TABLE IF NOT EXISTS jenkins_api_calls (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    ai_interaction_id INTEGER REFERENCES ai_interactions(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    endpoint VARCHAR(500) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INTEGER,
    permission_required VARCHAR(255),
    permission_granted BOOLEAN,
    request_body JSONB,
    response_body JSONB,
    execution_time_ms INTEGER,
    user_token_hash VARCHAR(255),
    error_details TEXT,
    mcp_tool_used VARCHAR(255)
);

-- Security events audit table
CREATE TABLE IF NOT EXISTS security_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    user_id VARCHAR(255),
    session_id UUID,
    source_ip INET,
    user_agent TEXT,
    details JSONB,
    severity VARCHAR(20) DEFAULT 'medium',
    resolved BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_ai_interactions_user_id 
ON ai_interactions(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_session_id 
ON ai_interactions(session_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_timestamp 
ON ai_interactions(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_jenkins_api_calls_user_id 
ON jenkins_api_calls(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_jenkins_api_calls_interaction_id 
ON jenkins_api_calls(ai_interaction_id);

CREATE INDEX IF NOT EXISTS idx_jenkins_api_calls_timestamp 
ON jenkins_api_calls(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_security_events_timestamp 
ON security_events(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_security_events_user_id 
ON security_events(user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_security_events_type_severity 
ON security_events(event_type, severity, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_security_events_resolved 
ON security_events(resolved, timestamp DESC) WHERE NOT resolved;

-- Partitioning for large tables (optional, for high-volume deployments)
-- This can be uncommented if you expect high volume

-- CREATE TABLE ai_interactions_y2024m01 PARTITION OF ai_interactions
-- FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Create a function to automatically create monthly partitions
-- CREATE OR REPLACE FUNCTION create_monthly_partitions()
-- RETURNS void AS $$
-- DECLARE
--     start_date date;
--     end_date date;
--     table_name text;
-- BEGIN
--     start_date := date_trunc('month', CURRENT_DATE);
--     end_date := start_date + interval '1 month';
--     table_name := 'ai_interactions_y' || to_char(start_date, 'YYYY') || 'm' || to_char(start_date, 'MM');
--     
--     EXECUTE 'CREATE TABLE IF NOT EXISTS ' || table_name || 
--             ' PARTITION OF ai_interactions FOR VALUES FROM (''' || 
--             start_date || ''') TO (''' || end_date || ''')';
-- END;
-- $$ LANGUAGE plpgsql;

-- Views for common queries
CREATE OR REPLACE VIEW user_activity_summary AS
SELECT 
    user_id,
    DATE(timestamp) as activity_date,
    COUNT(*) as total_interactions,
    COUNT(CASE WHEN success THEN 1 END) as successful_interactions,
    AVG(response_time_ms) as avg_response_time,
    array_agg(DISTINCT intent_detected) FILTER (WHERE intent_detected IS NOT NULL) as intents_used
FROM ai_interactions
GROUP BY user_id, DATE(timestamp);

CREATE OR REPLACE VIEW security_events_summary AS
SELECT 
    event_type,
    severity,
    COUNT(*) as event_count,
    COUNT(CASE WHEN resolved THEN 1 END) as resolved_count,
    MAX(timestamp) as latest_occurrence,
    array_agg(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) as affected_users
FROM security_events
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY event_type, severity
ORDER BY event_count DESC;

CREATE OR REPLACE VIEW api_performance_summary AS
SELECT 
    endpoint,
    method,
    COUNT(*) as call_count,
    AVG(execution_time_ms) as avg_execution_time,
    COUNT(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 END) as successful_calls,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) as failed_calls,
    MAX(timestamp) as last_called
FROM jenkins_api_calls
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY endpoint, method
ORDER BY call_count DESC;

-- Grant permissions to application user
-- Note: In production, create a specific user with limited permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO chatbot_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbot_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO chatbot_user;

-- Insert initial security event to test the system
INSERT INTO security_events (event_type, details, severity)
VALUES ('system_initialized', '{"message": "Database schema created successfully"}', 'low');

-- Create a function to clean up old audit records
CREATE OR REPLACE FUNCTION cleanup_old_audit_records(retention_days INTEGER DEFAULT 90)
RETURNS TABLE(ai_deleted BIGINT, api_deleted BIGINT, security_deleted BIGINT) AS $$
DECLARE
    ai_count BIGINT;
    api_count BIGINT;
    security_count BIGINT;
BEGIN
    -- Clean up old AI interactions
    WITH deleted AS (
        DELETE FROM ai_interactions
        WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO ai_count FROM deleted;
    
    -- Clean up old API calls
    WITH deleted AS (
        DELETE FROM jenkins_api_calls
        WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
        RETURNING id
    )
    SELECT COUNT(*) INTO api_count FROM deleted;
    
    -- Clean up old resolved security events
    WITH deleted AS (
        DELETE FROM security_events
        WHERE timestamp < NOW() - (retention_days || ' days')::INTERVAL
          AND resolved = TRUE
        RETURNING id
    )
    SELECT COUNT(*) INTO security_count FROM deleted;
    
    RETURN QUERY SELECT ai_count, api_count, security_count;
END;
$$ LANGUAGE plpgsql;