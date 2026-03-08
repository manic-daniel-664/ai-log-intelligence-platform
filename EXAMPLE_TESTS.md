# Example Test Flow Commands

This document shows how to drive the extended pipeline end-to-end for
anomaly detection and AI analysis, and how to query the Insight API.

---

## 1. Start/Build Containers

```bash
# from workspace root
docker compose up --build -d kafka zookeeper redis postgres elasticsearch \
  log-producer log-parser anomaly-detector ai-analyzer insight-api kafka-ui
```

Wait until all services show `Up` (use `docker compose ps`).

## 2. Produce Sample Logs

Send a burst of error logs to trigger the anomaly detector:

```bash
for i in {1..6}; do
  curl -s -X POST http://localhost:8000/logs \
    -H "Content-Type: application/json" \
    -d "{\"service\": \"auth-app\", \"log\": \"2026-03-08 12:00:$i ERROR Failure example\"}"
  sleep 5
done
```

You should see `incident.detected` events published by `anomaly-detector`.

## 3. Inspect Kafka Topics

```bash
# see new incident topic messages
docker exec kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic incident.detected \
  --from-beginning --max-messages 5
```

## 4. Watch Analyzed Incidents

```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic incident.analyzed \
  --from-beginning --max-messages 5
```

The `ai-analyzer` will read detected incidents, call the LLM stub, store the
analysis in Postgres, and republish.  If the LLM call fails you will find
events in `dead.letter.queue`.

## 5. Query PostgreSQL Directly (optional)

```bash
docker exec -it postgres psql -U admin -d incidents

# inside psql
SELECT * FROM incident_analysis LIMIT 10;
```

## 6. Use Insight API

```bash
# list all incidents
curl http://localhost:8100/incidents | jq

# get single incident details
curl http://localhost:8100/incidents/<incident_id> | jq

# get only analysis
curl http://localhost:8100/incidents/<incident_id>/analysis | jq
```

Replace `<incident_id>` with an actual UUID from the list.

## 7. Flow Verification Script

You can reuse the earlier `tests/test_pipeline.py` by extending it or simply run
these manual commands to simulate traffic.  The same verification script can be
updated to include anomaly and AI layers later.

---

**Notes**

- Redis sliding window entries have 60-second TTL; adjust test timings accordingly.
- Duplicate incidents within the same window are suppressed by a Redis key.
- All inter-service communication uses internal Kafka listener (`kafka:29092`).
- Health endpoints:
  - producer: `GET /health` port 8000
  - insight-api: `GET /health` port 8100

