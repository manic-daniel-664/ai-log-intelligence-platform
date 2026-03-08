# Correlation ID Tracing

## Updated Event Envelope

```json
{
  "event_id": "2e8d3257-4f31-4850-b4fb-30478c7eb709",
  "correlation_id": "8fc6781e-9d81-45f8-8c3a-afd2d37269f9",
  "event_type": "incident.analyzed",
  "timestamp": "2026-03-08T09:08:55Z",
  "version": "v1",
  "payload": {
    "incident_id": "b551e79e-95e8-43e9-ae76-7c7e8ee45705",
    "correlation_id": "8fc6781e-9d81-45f8-8c3a-afd2d37269f9",
    "root_cause": "...",
    "severity": "Low",
    "mitigation": "...",
    "confidence": 75
  }
}
```

## Database Migration

```sql
ALTER TABLE incident_analysis
ADD COLUMN IF NOT EXISTS correlation_id UUID;

CREATE INDEX IF NOT EXISTS idx_incident_analysis_correlation_id
ON incident_analysis(correlation_id);
```

## Example Structured Logs

```text
[2026-03-08 09:08:37,611] [INFO] [service=log-producer] [correlation_id=8fc6781e-9d81-45f8-8c3a-afd2d37269f9] Accepted inbound log
[2026-03-08 09:08:38,121] [INFO] [service=anomaly-detector] [correlation_id=8fc6781e-9d81-45f8-8c3a-afd2d37269f9] Incident triggered for service demo-service reason ERROR_SPIKE
[2026-03-08 09:08:38,422] [INFO] [service=ai-analyzer] [correlation_id=8fc6781e-9d81-45f8-8c3a-afd2d37269f9] Analysis completed for incident b551e79e-95e8-43e9-ae76-7c7e8ee45705 severity=Low
```

## Demo Verification

`demo_run_real_llm.py` now verifies:

1. `correlation_id` from producer response.
2. Same `correlation_id` in `log-producer`, `anomaly-detector`, `ai-analyzer` logs.
3. Same `correlation_id` in `incident_analysis` row.
4. Same `correlation_id` in Insight API `/incidents/{incident_id}` response.

