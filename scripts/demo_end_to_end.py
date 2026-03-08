#!/usr/bin/env python3
"""
AI Log Intelligence Pipeline - End-to-End Demo Script

Portfolio showcase script that:
1. Ensures Docker services are running
2. Triggers anomaly logs to demonstrate detection
3. Verifies end-to-end processing through AI analysis
4. Queries results and displays summary

Usage:
  python3 scripts/demo_end_to_end.py
"""

import subprocess
import time
import requests
import sys
import psycopg2
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuration
PRODUCER_URL = "http://localhost:8000"
INSIGHT_URL = "http://localhost:8100"
KAFKA_BOOTSTRAP = "kafka:29092"

# PostgreSQL Configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "incidents",
    "user": "admin",
    "password": "admin"
}

# Demo Configuration
LOG_COUNT = 6
LOG_INTERVAL = 1.5  # seconds between logs
SERVICE_NAME = "demo-service"
HEALTH_CHECK_TIMEOUT = 60  # seconds
ANALYSIS_WAIT_TIMEOUT = 30  # seconds

# Color codes for terminal output
class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(title: str) -> None:
    """Print a formatted section header"""
    print(f"\n{Color.HEADER}{Color.BOLD}{'='*70}{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}{title.center(70)}{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}{'='*70}{Color.END}\n")


def print_section(title: str) -> None:
    """Print a sub-section header"""
    print(f"\n{Color.CYAN}{Color.BOLD}→ {title}{Color.END}")
    print(f"{Color.CYAN}{'-'*68}{Color.END}")


def print_success(msg: str) -> None:
    """Print a success message"""
    print(f"{Color.GREEN}✓ {msg}{Color.END}")


def print_error(msg: str) -> None:
    """Print an error message"""
    print(f"{Color.RED}✗ {msg}{Color.END}")


def print_info(msg: str) -> None:
    """Print an info message"""
    print(f"{Color.BLUE}ℹ {msg}{Color.END}")


def run_command(cmd: List[str], timeout: int = 10) -> Tuple[int, str, str]:
    """
    Execute a shell command and return exit code, stdout, stderr
    
    Args:
        cmd: Command as list of strings
        timeout: Command timeout in seconds
    
    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def ensure_services_running() -> bool:
    """
    Step 1: Ensure Docker services are running
    
    Checks if containers are running, starts them if needed.
    Returns True if all services are running, False otherwise.
    """
    print_section("Step 1: Ensuring Services Running")
    
    # Check if containers are running
    print_info("Checking container status...")
    code, stdout, _ = run_command(["docker", "compose", "ps"])
    
    if code != 0:
        print_error("Failed to check container status")
        return False
    
    required_services = [
        "log-producer",
        "log-parser",
        "anomaly-detector",
        "ai-analyzer",
        "insight-api",
        "kafka",
        "postgres",
        "redis"
    ]
    
    running_services = []
    for line in stdout.split('\n'):
        for service in required_services:
            if service in line and "running" in line.lower():
                running_services.append(service)
    
    missing_services = [s for s in required_services if s not in running_services]
    
    if missing_services:
        print_info(f"Services not running: {', '.join(missing_services)}")
        print_info("Starting docker-compose stack...")
        code, _, stderr = run_command(
            ["docker", "compose", "up", "-d"],
            timeout=60
        )
        if code != 0:
            print_error(f"Failed to start services: {stderr}")
            return False
        print_success("Services started")
        time.sleep(5)  # Wait for services to initialize
    else:
        print_success(f"All {len(required_services)} required services running")
    
    return True


def wait_for_service(url: str, service_name: str, timeout: int = 60) -> bool:
    """
    Wait for a service to respond to health checks
    
    Polls the service health endpoint with exponential backoff.
    Returns True if service becomes healthy, False if timeout.
    """
    print_info(f"Waiting for {service_name} to be healthy...")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < timeout:
        attempt += 1
        try:
            response = requests.get(f"{url}/health", timeout=3)
            if response.status_code == 200:
                print_success(f"{service_name} is healthy (attempt {attempt})")
                return True
        except requests.RequestException:
            pass
        
        # Exponential backoff: 1s, 2s, 4s, 5s, 5s...
        wait_time = min(2 ** min(attempt - 1, 2), 5)
        print_info(f"  Retrying in {wait_time}s... (elapsed: {int(time.time() - start_time)}s)")
        time.sleep(wait_time)
    
    print_error(f"Timeout waiting for {service_name} (waited {timeout}s)")
    return False


def send_logs() -> bool:
    """
    Step 2: Send ERROR logs to trigger anomaly detection
    
    Sends 6 ERROR logs rapidly to the producer API to trigger
    the anomaly detector (which watches for spikes).
    """
    print_section("Step 2: Triggering Anomaly Detection")
    
    print_info(f"Sending {LOG_COUNT} ERROR logs to trigger anomaly...")
    
    log_messages = [
        f"2024-01-01 10:00:0{i} ERROR HTTP 500 Database timeout after 1200ms"
        for i in range(1, LOG_COUNT + 1)
    ]
    
    success_count = 0
    
    for i, log_msg in enumerate(log_messages, 1):
        payload = {
            "service": SERVICE_NAME,
            "log": log_msg
        }
        
        try:
            response = requests.post(
                f"{PRODUCER_URL}/logs",
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                print_info(f"  [{i}/{LOG_COUNT}] Log sent")
                success_count += 1
            else:
                print_error(f"  [{i}/{LOG_COUNT}] HTTP {response.status_code}")
        except requests.RequestException as e:
            print_error(f"  [{i}/{LOG_COUNT}] Failed: {str(e)}")
        
        # Space out the logs to ensure they arrive within the anomaly window
        if i < LOG_COUNT:
            time.sleep(LOG_INTERVAL)
    
    if success_count == LOG_COUNT:
        print_success(f"All {LOG_COUNT} anomaly logs sent successfully")
        return True
    else:
        print_error(f"Only {success_count}/{LOG_COUNT} logs sent successfully")
        return False


def get_db_connection():
    """Create a PostgreSQL connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print_error(f"Failed to connect to PostgreSQL: {e}")
        return None


def fetch_latest_analysis() -> Optional[Dict]:
    """
    Fetch the latest incident analysis from PostgreSQL
    
    Queries the incident_analysis table for the most recent record
    for our demo service.
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT incident_id, service, trigger_reason, severity, 
                   root_cause, mitigation, confidence, created_at
            FROM incident_analysis
            WHERE service = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (SERVICE_NAME,))
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return {
                "incident_id": str(row[0]),
                "service": row[1],
                "trigger_reason": row[2],
                "severity": row[3],
                "root_cause": row[4],
                "mitigation": row[5],
                "confidence": row[6],
                "created_at": row[7]
            }
        return None
    except psycopg2.Error as e:
        print_error(f"Database query error: {e}")
        return None
    finally:
        conn.close()


def wait_for_analysis(timeout: int = 30) -> Optional[Dict]:
    """
    Step 3: Wait for analysis to complete
    
    Polls PostgreSQL for new incident_analysis records.
    Waits up to `timeout` seconds for the analysis to appear.
    """
    print_section("Step 3: Waiting for Analysis Pipeline")
    
    start_time = time.time()
    attempt = 0
    
    while time.time() - start_time < timeout:
        attempt += 1
        
        analysis = fetch_latest_analysis()
        if analysis:
            elapsed = int(time.time() - start_time)
            print_success(f"Analysis found (attempt {attempt}, {elapsed}s elapsed)")
            return analysis
        
        elapsed = int(time.time() - start_time)
        remaining = timeout - elapsed
        print_info(f"  Waiting for analysis... ({elapsed}s/{timeout}s)")
        time.sleep(2)
    
    print_error(f"Timeout waiting for analysis ({timeout}s)")
    return None


def fetch_insight_api_incident(incident_id: str) -> Optional[Dict]:
    """
    Fetch incident details from Insight API
    
    Calls GET /incidents/{incident_id} to retrieve the full incident record
    with analysis details.
    """
    try:
        response = requests.get(
            f"{INSIGHT_URL}/incidents/{incident_id}",
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print_error(f"Failed to fetch from Insight API: {e}")
    
    return None


def fetch_all_incidents() -> Optional[List[Dict]]:
    """
    Fetch all incidents from Insight API
    
    Calls GET /incidents to retrieve list of all incidents.
    """
    try:
        response = requests.get(
            f"{INSIGHT_URL}/incidents",
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException as e:
        print_error(f"Failed to fetch incidents from Insight API: {e}")
    
    return None


def check_pipeline_health() -> Dict:
    """
    Step 5: Verify pipeline health
    
    Checks:
    - Database connectivity
    - Incident records in PostgreSQL
    - Service analysis availability
    """
    print_section("Step 5: Pipeline Health Verification")
    
    health = {
        "total_incidents": 0,
        "demo_service_incidents": 0,
        "db_status": False
    }
    
    # Query PostgreSQL for incident counts
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"]
        )
        cursor = conn.cursor()
        
        # Get total incidents
        print_info("Querying incident_analysis table...")
        cursor.execute("SELECT COUNT(*) FROM incident_analysis")
        total_count = cursor.fetchone()[0]
        health["total_incidents"] = total_count
        print_success(f"Total incidents in database: {total_count}")
        
        # Get demo-service incidents
        cursor.execute("SELECT COUNT(*) FROM incident_analysis WHERE service = %s", ("demo-service",))
        demo_count = cursor.fetchone()[0]
        health["demo_service_incidents"] = demo_count
        print_success(f"Demo service incidents: {demo_count}")
        
        health["db_status"] = True
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print_error(f"Failed to query database: {e}")
        health["db_status"] = False
    
    return health


def print_summary(analysis: Dict, health: Dict) -> None:
    """
    Step 6: Print formatted demo summary
    
    Displays incident analysis and pipeline metrics in a clean,
    portfolio-friendly format.
    """
    print_header("AI INCIDENT ANALYSIS - DEMO SUMMARY")
    
    print(f"{Color.BOLD}Incident Details:{Color.END}")
    print(f"  Service:        {Color.CYAN}{analysis['service']}{Color.END}")
    print(f"  Incident ID:    {Color.CYAN}{analysis['incident_id']}{Color.END}")
    print(f"  Trigger:        {Color.CYAN}{analysis['trigger_reason']}{Color.END}")
    print(f"  Timestamp:      {Color.CYAN}{analysis['created_at']}{Color.END}")
    
    print(f"\n{Color.BOLD}AI Analysis Results:{Color.END}")
    print(f"  Severity:       {Color.YELLOW}{analysis['severity'].upper()}{Color.END}")
    print(f"  Confidence:     {Color.YELLOW}{analysis['confidence']}%{Color.END}")
    print(f"  Root Cause:     {Color.CYAN}{analysis['root_cause']}{Color.END}")
    print(f"  Mitigation:     {Color.CYAN}{analysis['mitigation']}{Color.END}")
    
    print(f"\n{Color.BOLD}Pipeline Health:{Color.END}")
    print(f"  Database Status:        {Color.GREEN if health['db_status'] else Color.RED}{'✓' if health['db_status'] else '✗'} OK{Color.END}")
    print(f"  Total Incidents:        {Color.CYAN}{health['total_incidents']}{Color.END}")
    print(f"  Demo Service Incidents: {Color.CYAN}{health['demo_service_incidents']}{Color.END}")
    
    print(f"\n{Color.BOLD}API Endpoints:{Color.END}")
    print(f"  Producer:     {Color.CYAN}http://localhost:8000{Color.END}")
    print(f"  Insight API:  {Color.CYAN}http://localhost:8100{Color.END}")
    print(f"  Kafka UI:     {Color.CYAN}http://localhost:8080{Color.END}")
    
    print(f"\n{Color.HEADER}{Color.BOLD}{'='*70}{Color.END}")
    print(f"{Color.GREEN}{Color.BOLD}✓ DEMO COMPLETED SUCCESSFULLY{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}{'='*70}{Color.END}\n")


def main() -> int:
    """
    Main demo orchestration
    
    Runs all steps in sequence:
    1. Ensure services running
    2. Trigger anomaly logs
    3. Wait for analysis
    4. Fetch results from Insight API
    5. Print summary
    
    Returns 0 on success, 1 on failure.
    """
    print_header("AI LOG INTELLIGENCE - END-TO-END DEMO")
    print_info(f"Starting demo at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Step 1: Ensure services running
    if not ensure_services_running():
        print_error("Failed to ensure services are running")
        return 1
    
    # Step 1b: Wait for key services to be healthy
    print_section("Step 1b: Waiting for Services to be Healthy")
    
    if not wait_for_service(PRODUCER_URL, "Producer API", timeout=60):
        print_error("Producer API failed to become healthy")
        return 1
    
    if not wait_for_service(INSIGHT_URL, "Insight API", timeout=60):
        print_error("Insight API failed to become healthy")
        return 1
    
    print_success("All critical services are healthy\n")
    
    # Step 2: Send logs to trigger anomaly
    if not send_logs():
        print_error("Failed to send anomaly logs")
        return 1
    
    # Step 3: Wait for analysis to complete
    analysis = wait_for_analysis(timeout=ANALYSIS_WAIT_TIMEOUT)
    if not analysis:
        print_error("Failed to retrieve analysis results")
        return 1
    
    # Step 4: Verify Insight API (optional, mainly for validation)
    print_section("Step 4: Verifying Insight API")
    
    print_info(f"Fetching incident {analysis['incident_id']} from Insight API...")
    api_incident = fetch_insight_api_incident(analysis['incident_id'])
    
    if api_incident:
        print_success("Successfully retrieved incident from Insight API")
    else:
        print_error("Warning: Could not retrieve from Insight API (data may still be correct)")
    
    # Step 5: Check pipeline health
    health = check_pipeline_health()
    
    # Step 6: Print summary
    print_summary(analysis, health)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
