-- PostgreSQL schema for incidents and analysis

CREATE TABLE IF NOT EXISTS incident_analysis (
    incident_id UUID PRIMARY KEY,
    correlation_id UUID,
    service VARCHAR(100),
    trigger_reason VARCHAR(100),
    severity VARCHAR(50),
    root_cause TEXT,
    mitigation TEXT,
    confidence INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incident_analysis_correlation_id
ON incident_analysis(correlation_id);
