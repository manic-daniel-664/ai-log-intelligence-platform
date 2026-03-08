
# 🚀 AI Log Intelligence Platform

An event-driven, AI-powered log intelligence system built using Kafka-based microservices.  
The platform detects anomaly spikes in real time and leverages Google Gemini to generate automated root cause and mitigation insights.

This project demonstrates distributed systems design, AI integration patterns, and production-grade observability practices.

---

# 🧠 Architecture Overview

The system follows an asynchronous event-driven pipeline:

Log Producer (FastAPI)
        │
        ▼
Kafka Topic: log.received
        │
        ▼
Log Parser
        │
        ▼
Kafka Topic: log.parsed
        │
        ▼
Anomaly Detector (Redis Sliding Window)
        │
        ▼
Kafka Topic: incident.detected
        │
        ▼
AI Analyzer (Google Gemini)
        │
        ▼
PostgreSQL (incident_analysis)
        │
        ▼
Insight API (FastAPI Read Model)

---

# ✨ Core Features

## ✅ Event-Driven Microservices
- Apache Kafka for asynchronous communication
- Consumer groups with manual offset commits
- Dead Letter Queue (DLQ) handling
- Versioned event envelope

## ✅ Real-Time Anomaly Detection
- Sliding window implementation using Redis ZSET
- Threshold-based error spike detection
- Deduplication using Redis SETNX with TTL
- Idempotent message processing

## ✅ AI-Powered Incident Analysis
- Integrated Google Gemini LLM
- Strict JSON output enforcement
- Exponential backoff retry (1s → 2s → 4s)
- Graceful DLQ fallback on failure
- Vendor-neutral LLM abstraction layer

## ✅ Distributed Tracing (Correlation ID)
- Correlation ID generated at system entry point
- Propagated across all Kafka events
- Logged in every service
- Persisted in PostgreSQL
- Returned via Insight API
- Verified end-to-end via demo script

## ✅ Observability & Resilience
- Structured logging
- Manual offset commit control
- Graceful shutdown handling
- Retry strategies for external AI calls
- Fault isolation between services

---

# 🛠 Tech Stack

| Layer | Technology |
|--------|------------|
| API | FastAPI |
| Messaging | Apache Kafka |
| Cache / State | Redis |
| Database | PostgreSQL |
| AI | Google Gemini |
| Containerization | Docker & Docker Compose |
| Language | Python 3.11 |

---

# 📂 Project Structure

ai-log-intelligence-platform/
│
├── services/
│   ├── log-producer/
│   ├── log-parser/
│   ├── anomaly-detector/
│   ├── ai-analyzer/
│   └── insight-api/
│
├── common/
│   └── tracing.py
│
├── scripts/
│   └── demo_run_real_llm.py
│
├── docker-compose.yml
├── README.md
└── .gitignore

---

# ⚙️ Setup Instructions

## 1️⃣ Clone the Repository

git clone <your-repo-url>
cd ai-log-intelligence-platform

## 2️⃣ Create Environment File

Create a `.env` file in the root directory:

GEMINI_API_KEY=your_api_key_here
USE_REAL_LLM=true
GEMINI_MODEL=gemini-flash-lite-latest

⚠️ Important:
- Do NOT commit `.env` to GitHub
- Add `.env` to `.gitignore`

## 3️⃣ Start All Services

docker compose up --build -d

## 4️⃣ Run End-to-End Demo

python scripts/demo_run_real_llm.py

---

# 📊 Example AI Output

REAL LLM INCIDENT ANALYSIS SUMMARY

incident_id   : 12a194d4-34ce-49fe-b00c-9364bd659122
correlation_id: 53234193-3f4c-4970-8436-6ba260d695ef
trigger_reason: ERROR_SPIKE

AI Output:
root_cause    : Investigate recent deployments or configuration changes.
severity      : Medium
mitigation    : Rollback last deployment and monitor error counts.
confidence    : 85

---

# 🔎 Insight API Endpoints

| Endpoint | Description |
|-----------|------------|
| GET /health | Service health check |
| GET /incidents | List all analyzed incidents |
| GET /incidents/{incident_id} | Fetch specific incident |
| GET /incidents/{incident_id}/analysis | Fetch AI analysis |

Default URL:
http://localhost:8100

---

# 🧠 Engineering Concepts Demonstrated

- Event-driven architecture
- Distributed systems design
- Sliding window anomaly detection
- Idempotent consumers
- Manual Kafka offset management
- Dead-letter queue patterns
- AI integration with structured output enforcement
- Correlation ID propagation
- CQRS read model separation
- Resilient microservices design

---

# 🚧 Production Enhancement Ideas

- Prometheus + Grafana monitoring
- Centralized logging (ELK or Loki)
- OpenTelemetry distributed tracing
- Kafka Schema Registry
- Kubernetes orchestration
- Horizontal scaling & partition tuning
- Circuit breakers for AI calls
- Rate limiting & security hardening

---

# 🎯 Purpose of This Project

This project explores:
- AI integration into backend systems
- Event-driven distributed architectures
- Resilient microservice design patterns
- Observability in asynchronous systems

---

# 👨‍💻 Author

Dani  
Backend Engineer | Distributed Systems & AI Integration
