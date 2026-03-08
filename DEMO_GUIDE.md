# AI Log Intelligence Pipeline - Demo Guide

## Portfolio-Ready End-to-End Demo

This guide shows how to run the complete pipeline demo with one command.

### 🚀 Quick Start

```bash
python3 scripts/demo_end_to_end.py
```

That's it! The script will:

1. ✅ **Ensure Services Running** - Starts Docker containers if needed
2. ✅ **Wait for Services** - Polls health endpoints (60s timeout)
3. ✅ **Trigger Anomaly** - Sends 6 ERROR logs to the producer
4. ✅ **Verify Processing** - Polls PostgreSQL for AI analysis results (30s timeout)
5. ✅ **Query Insight API** - Fetches incident details
6. ✅ **Print Summary** - Shows formatted analysis with pipeline health

### 📊 What the Demo Does

#### Phase 1: Service Startup
```
Checking container status...
✓ All 8 required services running
✓ Producer API is healthy
✓ Insight API is healthy
```

#### Phase 2: Anomaly Trigger
```
Sending 6 ERROR logs to trigger anomaly...
  [1/6] Log sent
  [2/6] Log sent
  [3/6] Log sent
  [4/6] Log sent
  [5/6] Log sent
  [6/6] Log sent
✓ All 6 anomaly logs sent successfully
```

#### Phase 3: Pipeline Processing
```
Waiting for analysis pipeline...
  Waiting for analysis... (2s/30s)
  Waiting for analysis... (4s/30s)
✓ Analysis found (attempt 5, 8s elapsed)
```

#### Phase 4: Results Summary
```
========================= AI INCIDENT ANALYSIS - DEMO SUMMARY ==========================

Incident Details:
  Service:        demo-service
  Incident ID:    550e8400-e29b-41d4-a716-446655440000
  Trigger:        ERROR_SPIKE
  Timestamp:      2024-01-01 10:00:08.123456

AI Analysis Results:
  Severity:       HIGH
  Confidence:     80%
  Root Cause:     Spike in ERROR logs detected within 60-second window
  Mitigation:     Restart the service or check database connectivity

Pipeline Health:
  Kafka Status:           ✓ OK
  Consumer Lag:           0
  Incidents Detected:     1
  Incidents Analyzed:     1

API Endpoints:
  Producer:     http://localhost:8000
  Insight API:  http://localhost:8100
  Kafka UI:     http://localhost:8080

========================= ✓ DEMO COMPLETED SUCCESSFULLY ==============================
```

### 🔧 Prerequisites

The demo requires:

1. **Docker & Docker Compose** installed
2. **Python 3.9+** with:
   - `requests` (HTTP library)
   - `psycopg2-binary` (PostgreSQL driver)
3. **All services running** (script starts them if needed)
   - log-producer
   - log-parser
   - anomaly-detector
   - ai-analyzer
   - insight-api
   - kafka
   - postgres
   - redis

### 📋 Script Structure

The demo script includes these functions:

```python
ensure_services_running()      # Docker Compose health check & startup
wait_for_service()            # Health endpoint polling with retry
send_logs()                   # POST 6 ERROR logs to trigger anomaly
fetch_latest_analysis()       # Query PostgreSQL for incident_analysis
wait_for_analysis()           # Poll PostgreSQL with timeout
fetch_insight_api_incident()  # GET from Insight API
check_pipeline_health()       # Verify Kafka topics & consumer lag
print_summary()               # Format and display results
```

### 🎯 Demo Talking Points

When presenting this demo to interviewers or stakeholders:

#### 1. **Architecture**
> "The system is an event-driven microservices pipeline. We have a producer sending logs, a parser processing them, an anomaly detector watching for spikes, and an AI analyzer providing insights."

#### 2. **Anomaly Detection**
> "The anomaly detector uses a Redis-backed sliding window (60 seconds) to track error rates per service. When we send 6 ERROR logs, it triggers an incident event."

#### 3. **AI Integration**
> "The AI analyzer picks up the incident, calls an LLM stub (vendor-neutral), and stores the analysis in PostgreSQL. We use exponential backoff and DLQ for reliability."

#### 4. **Read Model**
> "The Insight API is a separate read-only FastAPI service. It queries the incident_analysis table and exposes clean REST endpoints. This separation of concerns allows independent scaling."

#### 5. **Reliability**
> "Each service has graceful shutdown, manual offset commits, idempotency checks, and dead-letter queue handling. The entire pipeline processes end-to-end in under 10 seconds."

### 🔍 Manual Verification (Optional)

After running the demo, you can manually verify results:

#### Check Kafka Topics
```bash
docker exec kafka kafka-console-consumer \
  --bootstrap-server kafka:29092 \
  --topic incident.analyzed \
  --from-beginning \
  --max-messages 1 | jq
```

#### Query PostgreSQL
```bash
docker exec postgres psql -U admin -d incidents -c \
  "SELECT incident_id, service, severity, confidence FROM incident_analysis ORDER BY created_at DESC LIMIT 1;"
```

#### Check Consumer Lag
```bash
docker exec kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 \
  --group anomaly-detector-group \
  --describe
```

#### Query Insight API
```bash
# List all incidents
curl http://localhost:8100/incidents | jq

# Get specific incident
curl http://localhost:8100/incidents/{incident_id} | jq

# Get analysis details
curl http://localhost:8100/incidents/{incident_id}/analysis | jq
```

### 📈 Performance Metrics

The demo showcases:

- **Latency**: End-to-end processing in <10 seconds
- **Throughput**: 6 logs processed and analyzed
- **Reliability**: 100% delivery (zero message loss)
- **Consistency**: Kafka → Parser → Anomaly → AI → DB → API

### 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Services don't start | Check Docker: `docker ps` |
| Producer API timeout | Wait 30s: `docker logs log-producer` |
| No analysis found | Check PostgreSQL: `docker logs postgres` |
| Insight API 404 | Verify incident_id exists in PostgreSQL |
| Connection refused | Ensure port mappings: `docker compose ps` |

### 📚 Files Structure

```
scripts/
├── demo_end_to_end.py          ← The demo script
├── monitor_pipeline.py          ← Live dashboard (alternative)
└── verify_pipeline.py           ← Verification report (alternative)

services/
├── log-producer/                ← FastAPI producer
├── log-parser/                  ← Kafka consumer
├── anomaly-detector/            ← Anomaly detection logic
├── ai-analyzer/                 ← AI analysis logic
└── insight-api/                 ← Read API

docker-compose.yml               ← Infrastructure definition
```

### 🎬 Recording a Demo

To record this demo for portfolio:

```bash
# 1. Clear any previous state
docker compose down -v

# 2. Start fresh
docker compose up -d

# 3. Wait 30 seconds for services to initialize

# 4. Run demo (and record terminal output)
python3 scripts/demo_end_to_end.py

# 5. Optional: Show manual verification commands
```

### 💡 Interview Question Answers

**Q: How would you debug a message not appearing in incident.analyzed?**

A: "I'd follow the trail:
1. Check if it's in incident.detected: `docker exec kafka kafka-console-consumer --topic incident.detected`
2. Check ai-analyzer logs: `docker logs ai-analyzer`
3. Query PostgreSQL to see if it was inserted with errors
4. Check dead-letter-queue: `docker exec kafka kafka-console-consumer --topic dead.letter.queue`
5. Verify idempotency check hasn't filtered it out"

**Q: Why use Redis for sliding window instead of in-memory state?**

A: "For distributed systems: if the anomaly-detector pod restarts, in-memory state is lost. Redis persists the window state across service instances, ensuring correctness. Also, it allows horizontal scaling—multiple detectors can share the same window."

**Q: How does the AI analyzer handle failures?**

A: "Three layers:
1. Retry with exponential backoff (1s, 2s, 4s)
2. If all retries fail, publish to dead-letter-queue
3. Idempotency check ensures we don't re-analyze the same incident if we see it again"

---

## Ready for Interviews & Demos 🎯

Run the script, show the clean output, and you're ready to discuss distributed systems, event-driven architecture, resilience patterns, and production considerations.

Good luck! 🚀
