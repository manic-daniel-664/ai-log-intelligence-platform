# 🎬 Running the End-to-End Demo

## One-Command Portfolio Demo

```bash
python3 scripts/demo_end_to_end.py
```

## What It Does ✨

The script orchestrates a complete end-to-end demonstration:

### 1️⃣ Service Startup (Automated)
- ✓ Checks Docker Compose status
- ✓ Starts containers if needed
- ✓ Waits for health checks (60s timeout)

### 2️⃣ Anomaly Trigger
- ✓ Sends 6 ERROR logs to the producer API
- ✓ Spaced 1.5 seconds apart
- ✓ Targets the "demo-service"

### 3️⃣ Pipeline Processing
- ✓ Anomaly detector picks up the spike
- ✓ AI analyzer generates insights
- ✓ Results stored in PostgreSQL
- ✓ Typically completes in <10 seconds

### 4️⃣ Results Verification
- ✓ Fetches incident from PostgreSQL
- ✓ Queries Insight API
- ✓ Checks pipeline health metrics

### 5️⃣ Beautiful Summary Output
```
========================= AI INCIDENT ANALYSIS - DEMO SUMMARY ==========================

Incident Details:
  Service:        demo-service
  Incident ID:    550e8400-e29b-41d4-a716-446655440000
  Trigger:        ERROR_SPIKE
  Timestamp:      2024-01-01 10:00:08.123456

AI Analysis Results:
  Severity:       HIGH
  Confidence:     85%
  Root Cause:     Spike in ERROR logs detected within 60-second window
  Mitigation:     Investigate database connection pool saturation

Pipeline Health:
  Kafka Status:           ✓ OK
  Consumer Lag:           0
  Incidents Detected:     1
  Incidents Analyzed:     1
```

## Key Features

✅ **Fully Automated** - No manual steps required  
✅ **Intelligent Retries** - Exponential backoff for service startup  
✅ **Error Handling** - Graceful timeouts and error messages  
✅ **Color-Coded Output** - Easy-to-read terminal formatting  
✅ **Production-Ready** - Demonstrates real reliability patterns  
✅ **Interview-Ready** - Perfect for technical demonstrations  

## Requirements

- Docker & Docker Compose
- Python 3.9+
- `requests` (HTTP client)
- `psycopg2-binary` (PostgreSQL driver)

Install dependencies:
```bash
pip install -r requirements.txt
```

## Detailed Guide

See [DEMO_GUIDE.md](DEMO_GUIDE.md) for:
- Extended explanation of each step
- Manual verification commands
- Interview talking points
- Troubleshooting guide
- Portfolio presentation tips

## Quick Troubleshooting

| Error | Solution |
|-------|----------|
| Services don't start | Check Docker: `docker ps` |
| Timeout waiting for API | Wait 60s, check `docker logs <service>` |
| No analysis found | Check PostgreSQL: `docker logs postgres` |
| Connection refused | Ensure `docker-compose up -d` completed |

## Related Commands

```bash
# View live dashboard
python3 scripts/monitor_pipeline.py

# Generate verification report
python3 scripts/verify_pipeline.py

# View Kafka UI
open http://localhost:8080

# Check producer health
curl http://localhost:8000/health

# Check insight API
curl http://localhost:8100/health
```

---

**Ready to impress? Run it now! 🚀**
