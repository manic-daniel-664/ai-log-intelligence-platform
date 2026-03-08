#!/usr/bin/env python3
"""
Run an end-to-end demo that validates real Gemini-backed AI analysis.

Behavior:
1. Ensures Docker Compose services are running.
2. Waits for producer and insight APIs to be healthy.
3. Sends 6 ERROR logs to trigger anomaly detection.
4. Polls PostgreSQL for a new analyzed incident.
5. Verifies output is not the known stub response.
6. Prints a clean summary.

Only error details are printed when failures occur.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import requests


PRODUCER_HEALTH_URL = "http://localhost:8000/health"
INSIGHT_HEALTH_URL = "http://localhost:8100/health"
PRODUCER_LOG_URL = "http://localhost:8000/logs"

SERVICE_NAME = "demo-service"
LOG_COUNT = 6
LOG_INTERVAL_SECONDS = 1.0
HEALTH_TIMEOUT_SECONDS = 120
PIPELINE_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "incidents"),
    "user": os.getenv("DB_USER", "admin"),
    "password": os.getenv("DB_PASSWORD", "admin"),
}

KNOWN_STUB_RESPONSE = {
    "root_cause": "Example cause",
    "severity": "Medium",
    "mitigation": "Restart service",
    "confidence": 80,
}


@dataclass
class IncidentRecord:
    incident_id: str
    correlation_id: Optional[str]
    service: str
    trigger_reason: str
    severity: str
    root_cause: str
    mitigation: str
    confidence: int
    created_at: datetime


class DemoError(RuntimeError):
    pass


def run_cmd(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as exc:
        raise DemoError(f"Command failed to execute: {' '.join(cmd)} ({exc})") from exc


def ensure_compose_services_running() -> None:
    print("1) Ensuring Docker Compose services are running...")
    ps = run_cmd(["docker", "compose", "ps"], timeout=30)
    if ps.returncode != 0:
        raise DemoError(f"`docker compose ps` failed: {ps.stderr.strip()}")

    required = {
        "kafka",
        "redis",
        "postgres",
        "log-producer",
        "log-parser",
        "anomaly-detector",
        "ai-analyzer",
        "insight-api",
    }

    running = set()
    for line in ps.stdout.splitlines():
        low = line.lower()
        if "running" not in low and "up" not in low:
            continue
        for name in required:
            if name in line:
                running.add(name)

    if running >= required:
        return

    up = run_cmd(["docker", "compose", "up", "-d"], timeout=120)
    if up.returncode != 0:
        raise DemoError(f"`docker compose up -d` failed: {up.stderr.strip()}")


def wait_for_health(url: str, name: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise DemoError(f"{name} health check timed out after {timeout_seconds}s ({url})")


def verify_ai_analyzer_real_llm_mode() -> None:
    """
    Best-effort check to ensure ai-analyzer container is configured for real LLM mode.
    """
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "ai-analyzer",
        "python",
        "-c",
        "import os; print(os.getenv('USE_REAL_LLM',''))",
    ]
    result = run_cmd(cmd, timeout=20)
    if result.returncode != 0:
        raise DemoError(f"Failed checking USE_REAL_LLM in ai-analyzer: {result.stderr.strip()}")
    if result.stdout.strip().lower() != "true":
        raise DemoError("ai-analyzer USE_REAL_LLM is not 'true'; real Gemini calls are disabled.")


def send_error_logs_and_capture_correlation_ids() -> list[str]:
    print("3) Sending ERROR logs to trigger anomaly detection...")
    payload_template = {"service": SERVICE_NAME, "log": "ERROR 500 Database timeout after 1200ms"}
    correlation_ids: list[str] = []
    for i in range(LOG_COUNT):
        payload = dict(payload_template)
        payload["log"] = f"{payload_template['log']} #{i + 1}"
        try:
            response = requests.post(PRODUCER_LOG_URL, json=payload, timeout=5)
        except requests.RequestException as exc:
            raise DemoError(f"Failed to send log {i + 1}/{LOG_COUNT}: {exc}") from exc
        if response.status_code >= 300:
            raise DemoError(
                f"Producer returned HTTP {response.status_code} for log {i + 1}/{LOG_COUNT}: {response.text[:300]}"
            )
        try:
            body = response.json()
            cid = body.get("correlation_id")
            if cid:
                correlation_ids.append(cid)
        except Exception:
            pass
        time.sleep(LOG_INTERVAL_SECONDS)
    if not correlation_ids:
        raise DemoError("Producer response did not include correlation_id")
    return correlation_ids


def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as exc:
        raise DemoError(f"PostgreSQL connection failed: {exc}") from exc


def fetch_latest_incident_for_service(conn, service: str) -> Optional[IncidentRecord]:
    sql = """
        SELECT incident_id, correlation_id, service, trigger_reason, severity, root_cause, mitigation, confidence, created_at
        FROM incident_analysis
        WHERE service = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (service,))
        row = cur.fetchone()
    if not row:
        return None
    return IncidentRecord(
        incident_id=row[0],
        correlation_id=str(row[1]) if row[1] else None,
        service=row[2],
        trigger_reason=row[3],
        severity=row[4],
        root_cause=row[5],
        mitigation=row[6],
        confidence=row[7],
        created_at=row[8],
    )


def is_stub_like(record: IncidentRecord) -> bool:
    return (
        record.root_cause == KNOWN_STUB_RESPONSE["root_cause"]
        and record.severity == KNOWN_STUB_RESPONSE["severity"]
        and record.mitigation == KNOWN_STUB_RESPONSE["mitigation"]
        and int(record.confidence) == int(KNOWN_STUB_RESPONSE["confidence"])
    )


def wait_for_new_real_analysis(baseline_incident_id: Optional[str]) -> IncidentRecord:
    print("4) Waiting for pipeline to produce Gemini analysis...")
    deadline = time.time() + PIPELINE_TIMEOUT_SECONDS
    while time.time() < deadline:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT incident_id, correlation_id, service, trigger_reason, severity, root_cause, mitigation, confidence, created_at
                    FROM incident_analysis
                    WHERE service = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (SERVICE_NAME,),
                )
                row = cur.fetchone()
        if row:
            latest = IncidentRecord(
                incident_id=row[0],
                correlation_id=str(row[1]) if row[1] else None,
                service=row[2],
                trigger_reason=row[3],
                severity=row[4],
                root_cause=row[5],
                mitigation=row[6],
                confidence=row[7],
                created_at=row[8],
            )
            if latest.incident_id != baseline_incident_id and not is_stub_like(latest):
                return latest
        time.sleep(POLL_INTERVAL_SECONDS)
    raise DemoError(
        "Timed out waiting for a new non-stub AI analysis. "
        "Check GEMINI_API_KEY, USE_REAL_LLM=true, and ai-analyzer logs."
    )


def verify_insight_api_correlation(incident_id: str, expected_correlation_id: str) -> dict:
    try:
        response = requests.get(f"http://localhost:8100/incidents/{incident_id}", timeout=5)
    except requests.RequestException as exc:
        raise DemoError(f"Insight API request failed: {exc}") from exc
    if response.status_code != 200:
        raise DemoError(f"Insight API returned HTTP {response.status_code}: {response.text[:300]}")
    payload = response.json()
    got = payload.get("correlation_id")
    if got != expected_correlation_id:
        raise DemoError(
            f"Insight API correlation_id mismatch for incident {incident_id}: expected {expected_correlation_id}, got {got}"
        )
    return payload


def verify_service_logs(correlation_id: str) -> None:
    for service in ["log-producer", "anomaly-detector", "ai-analyzer"]:
        result = run_cmd(["docker", "compose", "logs", "--since", "10m", service], timeout=30)
        if result.returncode != 0:
            raise DemoError(f"Failed reading logs for {service}: {result.stderr.strip()}")
        if correlation_id not in result.stdout:
            raise DemoError(f"Correlation ID {correlation_id} not found in {service} logs")


def print_summary(record: IncidentRecord, insight_payload: dict) -> None:
    print("\n" + "=" * 72)
    print("REAL LLM INCIDENT ANALYSIS SUMMARY")
    print("=" * 72)
    print(f"incident_id   : {record.incident_id}")
    print(f"correlation_id: {record.correlation_id}")
    print(f"trigger_reason: {record.trigger_reason}")
    print("-" * 72)
    print("AI Output")
    print(f"root_cause    : {record.root_cause}")
    print(f"severity      : {record.severity}")
    print(f"mitigation    : {record.mitigation}")
    print(f"confidence    : {record.confidence}")
    print("-" * 72)
    print("Correlation Continuity Checks")
    print(f"producer_correlation_id : {record.correlation_id}")
    print("log-producer logs       : FOUND")
    print("anomaly-detector logs   : FOUND")
    print("ai-analyzer logs        : FOUND")
    print(f"database correlation_id : {record.correlation_id}")
    print(f"insight-api correlation : {insight_payload.get('correlation_id')}")
    print("=" * 72)


def main() -> int:
    started_at = datetime.now(timezone.utc)
    print("Real LLM pipeline demo started.")
    print(f"UTC start time: {started_at.isoformat()}")

    try:
        ensure_compose_services_running()

        print("2) Waiting for APIs to become healthy...")
        wait_for_health(PRODUCER_HEALTH_URL, "Producer API", HEALTH_TIMEOUT_SECONDS)
        wait_for_health(INSIGHT_HEALTH_URL, "Insight API", HEALTH_TIMEOUT_SECONDS)

        verify_ai_analyzer_real_llm_mode()

        with get_db_connection() as conn:
            baseline = fetch_latest_incident_for_service(conn, SERVICE_NAME)
        baseline_id = baseline.incident_id if baseline else None

        producer_correlation_ids = send_error_logs_and_capture_correlation_ids()
        analyzed = wait_for_new_real_analysis(baseline_id)
        if not analyzed.correlation_id:
            raise DemoError(f"Incident {analyzed.incident_id} has empty correlation_id in database")
        if analyzed.correlation_id not in producer_correlation_ids:
            raise DemoError(
                f"Analyzed incident correlation_id {analyzed.correlation_id} was not among produced IDs: {producer_correlation_ids}"
            )
        verify_service_logs(analyzed.correlation_id)
        insight_payload = verify_insight_api_correlation(analyzed.incident_id, analyzed.correlation_id)
        print_summary(analyzed, insight_payload)
        return 0

    except DemoError as exc:
        print("\nERROR:", exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print("\nERROR: Unexpected failure.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
