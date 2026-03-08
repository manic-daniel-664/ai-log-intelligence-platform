#!/usr/bin/env python3
"""
End-to-End Pipeline Testing Script
Tests the complete AI Log Intelligence pipeline from log ingestion to processing
"""

import requests
import json
import time
from typing import Dict, List
import subprocess
import sys

# Configuration
PRODUCER_URL = "http://localhost:8000"
KAFKA_BOOTSTRAP_SERVER = "kafka:29092"
DOCKER_EXEC_PREFIX = ["docker", "exec", "kafka"]
INSIGHT_URL = "http://localhost:8100"

class PipelineTestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add_test(self, name: str, passed: bool, message: str = ""):
        status = "✅ PASS" if passed else "❌ FAIL"
        self.tests.append({
            "name": name,
            "passed": passed,
            "message": message,
            "status": status
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {name} {message}")
    
    def print_summary(self):
        print("\n" + "="*80)
        print("PIPELINE TEST SUMMARY")
        print("="*80)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📊 Total: {self.passed + self.failed}")
        print("="*80 + "\n")
        return self.failed == 0

class KafkaHelper:
    @staticmethod
    def get_topic_list() -> List[str]:
        """Get list of all Kafka topics"""
        try:
            cmd = DOCKER_EXEC_PREFIX + ["kafka-topics", "--list", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            return []
        except Exception as e:
            print(f"Error getting topic list: {e}")
            return []
    
    @staticmethod
    def get_consumer_lag(group_id: str, topic: str) -> Dict:
        """Get consumer group lag for a topic"""
        try:
            cmd = DOCKER_EXEC_PREFIX + ["kafka-consumer-groups", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER, 
                                       "--group", group_id, "--describe"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Parse output to find lag
                lines = result.stdout.strip().split('\n')
                total_lag = 0
                for line in lines:
                    if topic in line and "LAG" not in line:
                        parts = line.split()
                        if len(parts) >= 8:
                            try:
                                lag = int(parts[7]) if parts[7] != '-' else 0
                                total_lag += lag
                            except:
                                pass
                return {"lag": total_lag, "raw": result.stdout}
            return {"lag": -1, "raw": result.stderr}
        except Exception as e:
            print(f"Error getting consumer lag: {e}")
            return {"lag": -1, "raw": str(e)}
    
    @staticmethod
    def get_message_count(topic: str, max_messages: int = 100) -> int:
        """Get count of messages in a topic"""
        try:
            cmd = DOCKER_EXEC_PREFIX + ["kafka-console-consumer", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER,
                                       "--topic", topic, "--from-beginning", "--max-messages", str(max_messages),
                                       "--timeout-ms", "3000"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            # Count "Processed a total of" message
            if "Processed a total of" in result.stdout:
                parts = result.stdout.split("Processed a total of")[-1].split("messages")[0].strip()
                return int(parts)
            return 0
        except Exception as e:
            return 0

def test_service_health() -> bool:
    """Test 1: Verify all services are healthy"""
    print("\n📋 TEST 1: Service Health Check")
    print("-" * 80)
    
    results = PipelineTestResults()
    
    # Test producer API health
    try:
        response = requests.get(f"{PRODUCER_URL}/health", timeout=5)
        results.add_test("Producer API Health", response.status_code == 200, 
                        f"Status: {response.status_code}")
    except Exception as e:
        results.add_test("Producer API Health", False, f"Error: {str(e)}")
    
    # Test Kafka connectivity
    topics = KafkaHelper.get_topic_list()
    results.add_test("Kafka Connectivity", len(topics) > 0, 
                    f"Found {len(topics)} topics")
    
    # Test required topics exist
    required_topics = ['log.received', 'log.parsed', 'incident.detected', 
                      'incident.ready_for_analysis', 'incident.analyzed', 'dead.letter.queue']
    for topic in required_topics:
        results.add_test(f"Topic '{topic}' exists", topic in topics)
    
    results.print_summary()
    return results.failed == 0

def test_log_producer() -> bool:
    """Test 2: Verify log producer sends messages correctly"""
    print("\n📋 TEST 2: Log Producer Functionality")
    print("-" * 80)
    
    results = PipelineTestResults()
    
    test_logs = [
        {"service": "auth-service", "log": "2024-01-01 10:00:00 ERROR Authentication failed for user admin from 192.168.1.1"},
        {"service": "api-service", "log": "2024-01-01 10:00:01 ERROR Database connection timeout after 5000ms"},
        {"service": "payment-service", "log": "2024-01-01 10:00:02 ERROR Payment processing failed for order #12345"},
    ]
    
    for i, test_log in enumerate(test_logs):
        try:
            response = requests.post(f"{PRODUCER_URL}/logs", json=test_log, timeout=5)
            results.add_test(f"Publish log #{i+1}", response.status_code == 200,
                            f"Service: {test_log['service']}")
        except Exception as e:
            results.add_test(f"Publish log #{i+1}", False, f"Error: {str(e)}")
    
    # Wait for messages to be processed
    time.sleep(2)
    
    # Check message count
    message_count = KafkaHelper.get_message_count("log.received", max_messages=100)
    results.add_test("Messages received by Kafka", message_count > 0,
                    f"Message count: {message_count}")
    
    results.print_summary()
    return results.failed == 0

def test_log_parser_consumer() -> bool:
    """Test 3: Verify log parser consumer processes messages"""
    print("\n📋 TEST 3: Log Parser Consumer")
    print("-" * 80)
    
    results = PipelineTestResults()
    
    # Check consumer group exists
    try:
        cmd = DOCKER_EXEC_PREFIX + ["kafka-consumer-groups", "--list", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        consumer_groups = result.stdout.strip().split('\n') if result.returncode == 0 else []
        results.add_test("Consumer group 'log-parser-group' exists", 
                        "log-parser-group" in consumer_groups)
    except Exception as e:
        results.add_test("Consumer group check", False, f"Error: {str(e)}")
    
    # Check consumer lag
    lag_info = KafkaHelper.get_consumer_lag("log-parser-group", "log.received")
    results.add_test("Consumer has zero lag", lag_info["lag"] == 0,
                    f"Current lag: {lag_info['lag']}")
    
    # Check parsed messages are produced
    parsed_count = KafkaHelper.get_message_count("log.parsed", max_messages=100)
    results.add_test("Parsed messages published", parsed_count > 0,
                    f"Parsed message count: {parsed_count}")
    
    results.print_summary()
    return results.failed == 0

def test_event_flow() -> bool:
    """Test 4: Verify complete event flow through topics"""
    print("\n📋 TEST 4: Event Flow Verification")
    print("-" * 80)
    
    results = PipelineTestResults()
    
    topics_to_check = {
        "log.received": "Raw log events",
        "log.parsed": "Parsed log events"
    }
    
    for topic, description in topics_to_check.items():
        try:
            cmd = DOCKER_EXEC_PREFIX + ["kafka-console-consumer", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER,
                                       "--topic", topic, "--max-messages", "1", "--timeout-ms", "3000"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            has_messages = "event_id" in result.stdout and "event_type" in result.stdout
            results.add_test(f"Topic '{topic}' has valid events", has_messages,
                            description)
        except Exception as e:
            results.add_test(f"Topic '{topic}' check", False, f"Error: {str(e)}")
    
    results.print_summary()
    return results.failed == 0

def test_service_communication() -> bool:
    """Test 5: Verify inter-service communication"""
    print("\n📋 TEST 5: Inter-Service Communication")
    print("-" * 80)
    
    results = PipelineTestResults()
    
    # Send a test log and verify it flows through the pipeline
    test_payload = {
        "service": "test-service",
        "log": "2024-01-01 11:00:00 ERROR Service communication test"
    }
    
    try:
        # Send log
        response = requests.post(f"{PRODUCER_URL}/logs", json=test_payload, timeout=5)
        results.add_test("Step 1: Log Producer accepts log", response.status_code == 200)
        
        # Wait for processing
        time.sleep(1)
        
        # Check if it reached Kafka
        cmd = DOCKER_EXEC_PREFIX + ["kafka-console-consumer", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER,
                                   "--topic", "log.received", "--max-messages", "1", "--timeout-ms", "3000"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        message_in_kafka = "test-service" in result.stdout
        results.add_test("Step 2: Message reaches Kafka (log.received)", message_in_kafka)
        
        # Wait for consumer to process
        time.sleep(1)
        
        # Check if parsed message is published
        cmd = DOCKER_EXEC_PREFIX + ["kafka-console-consumer", "--bootstrap-server", KAFKA_BOOTSTRAP_SERVER,
                                   "--topic", "log.parsed", "--max-messages", "1", "--timeout-ms", "3000"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        parsed_in_kafka = "log.parsed" in result.stdout and "test-service" in result.stdout
        results.add_test("Step 3: Consumer publishes to log.parsed", parsed_in_kafka)
        
    except Exception as e:
        results.add_test("Service communication flow", False, f"Error: {str(e)}")
    
    results.print_summary()
    return results.failed == 0


def test_anomaly_and_analysis() -> bool:
    """Test 6: Anomaly detection, AI analysis, and Insight API"""
    print("\n📋 TEST 6: Anomaly & AI Flow")
    print("-" * 80)
    results = PipelineTestResults()
    # send several ERROR logs for same service to trigger anomaly
    for i in range(6):
        payload = {"service": "anomaly-service", "log": f"ERROR spike {i}"}
        try:
            requests.post(f"{PRODUCER_URL}/logs", json=payload, timeout=5)
        except:
            pass
    # give time for pipeline to process
    time.sleep(3)
    detected = KafkaHelper.get_message_count("incident.detected", max_messages=10)
    results.add_test("Incident detected published", detected > 0,
                    f"count={detected}")
    # wait for AI
    time.sleep(3)
    analyzed = KafkaHelper.get_message_count("incident.analyzed", max_messages=10)
    results.add_test("Incident analyzed published", analyzed > 0,
                    f"count={analyzed}")
    # query Insight API
    try:
        resp = requests.get(f"{INSIGHT_URL}/incidents", timeout=5)
        results.add_test("Insight API reachable", resp.status_code == 200,
                        f"status={resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            results.add_test("Insight API returned records", len(data) > 0,
                            f"records={len(data)}")
    except Exception as e:
        results.add_test("Insight API call", False, f"Error: {e}")
    results.print_summary()
    return results.failed == 0


def main():
    """Run all pipeline tests"""
    print("\n" + "="*80)
    print("🚀 AI LOG INTELLIGENCE PIPELINE - END-TO-END TEST SUITE")
    print("="*80)
    
    all_passed = True
    
    # Run all tests
    all_passed &= test_service_health()
    all_passed &= test_log_producer()
    all_passed &= test_log_parser_consumer()
    all_passed &= test_event_flow()
    all_passed &= test_service_communication()
    # new check for anomaly and AI layers
    all_passed &= test_anomaly_and_analysis()
    
    # Final summary
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - PIPELINE IS FULLY OPERATIONAL")
    else:
        print("⚠️  SOME TESTS FAILED - PLEASE REVIEW THE LOGS ABOVE")
    print("="*80 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
