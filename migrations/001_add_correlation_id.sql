ALTER TABLE incident_analysis
ADD COLUMN IF NOT EXISTS correlation_id UUID;

CREATE INDEX IF NOT EXISTS idx_incident_analysis_correlation_id
ON incident_analysis(correlation_id);

