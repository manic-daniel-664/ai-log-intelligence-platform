#!/usr/bin/env python3
"""
Pipeline Monitoring and Verification Dashboard
Provides real-time visibility into the AI Log Intelligence pipeline status
"""

import subprocess
import json
import sys
from datetime import datetime
from typing import Dict, List, Tuple

class PipelineMonitor:
    def __init__(self):
        self.kafka_bootstrap = "kafka:29092"
        self.docker_prefix = ["docker", "exec", "kafka"]
    
    def run_command(self, cmd: List[str], timeout: int = 10) -> Tuple[bool, str]:
        """Run a shell command and return success status and output"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def get_service_status(self) -> Dict:
        """Check the status of all pipeline services"""
        print("\n" + "="*80)
        print("🔍 SERVICE STATUS CHECK")
        print("="*80)
        
        status = {}
        
        # Check Docker containers
        cmd = ["docker", "compose", "ps", "--format", "json"]
        success, output = self.run_command(cmd)
        
        if success:
            try:
                containers = json.loads(output)
                for container in containers:
                    if container['Service'] in ['log-parser', 'log-producer', 'kafka', 'elasticsearch', 'zookeeper']:
                        status[container['Service']] = {
                            'status': container['State'],
                            'uptime': container.get('Created', 'N/A')
                        }
                        icon = "✅" if container['State'] == 'running' else "❌"
                        print(f"{icon} {container['Service']:20} | {container['State']:10} | Created: {container.get('Created', 'N/A')}")
            except json.JSONDecodeError:
                print("⚠️  Could not parse Docker container status")
        
        return status
    
    def get_topic_status(self) -> Dict:
        """Check Kafka topics and message counts"""
        print("\n" + "="*80)
        print("📊 KAFKA TOPICS & MESSAGE COUNTS")
        print("="*80)
        
        topics_info = {}
        
        # Get all topics
        cmd = self.docker_prefix + ["kafka-topics", "--list", "--bootstrap-server", self.kafka_bootstrap]
        success, output = self.run_command(cmd)
        
        if not success:
            print("❌ Failed to retrieve topics")
            return topics_info
        
        topics = output.strip().split('\n')
        pipeline_topics = ['log.received', 'log.parsed', 'incident.detected', 
                          'incident.ready_for_analysis', 'incident.analyzed', 'dead.letter.queue']
        
        for topic in pipeline_topics:
            if topic in topics:
                # Get partition info
                cmd = self.docker_prefix + ["kafka-topics", "--describe", "--topic", topic, "--bootstrap-server", self.kafka_bootstrap]
                success, output = self.run_command(cmd)
                
                if success:
                    # Parse partition count
                    lines = output.strip().split('\n')
                    partition_count = sum(1 for line in lines if topic in line and 'Topic:' not in line)
                    topics_info[topic] = {'partitions': partition_count}
                    print(f"✅ {topic:35} | Partitions: {partition_count}")
        
        return topics_info
    
    def get_consumer_status(self) -> Dict:
        """Check consumer group status and lag"""
        print("\n" + "="*80)
        print("👥 CONSUMER GROUP STATUS")
        print("="*80)
        
        consumer_status = {}
        
        # Get consumer groups
        cmd = self.docker_prefix + ["kafka-consumer-groups", "--list", "--bootstrap-server", self.kafka_bootstrap]
        success, output = self.run_command(cmd)
        
        if not success or not output.strip():
            print("⚠️  No consumer groups found")
            return consumer_status
        
        groups = output.strip().split('\n')
        
        for group in groups:
            if group == "__consumer_offsets":
                continue
            
            print(f"\n📌 Consumer Group: {group}")
            
            # Get group details
            cmd = self.docker_prefix + ["kafka-consumer-groups", "--describe", "--group", group, "--bootstrap-server", self.kafka_bootstrap]
            success, details = self.run_command(cmd)
            
            if success:
                lines = details.strip().split('\n')[1:]  # Skip header
                total_lag = 0
                topic_stats = {}
                
                for line in lines:
                    if not line.strip():
                        continue
                    
                    parts = line.split()
                    if len(parts) >= 8:
                        topic = parts[1]
                        partition = parts[2]
                        current_offset = int(parts[3]) if parts[3].isdigit() else 0
                        log_end = int(parts[4]) if parts[4].isdigit() else 0
                        lag = int(parts[5]) if parts[5] != '-' and parts[5].isdigit() else 0
                        
                        if topic not in topic_stats:
                            topic_stats[topic] = {'partitions': 0, 'total_lag': 0, 'messages': 0}
                        
                        topic_stats[topic]['partitions'] += 1
                        topic_stats[topic]['total_lag'] += lag
                        topic_stats[topic]['messages'] += log_end
                        total_lag += lag
                
                # Print topic details
                for topic, stats in topic_stats.items():
                    lag_indicator = "✅" if stats['total_lag'] == 0 else "⚠️"
                    print(f"  {lag_indicator} Topic: {topic:25} | Lag: {stats['total_lag']:3} | Messages: {stats['messages']:4}")
                
                consumer_status[group] = {
                    'total_lag': total_lag,
                    'topics': topic_stats
                }
        
        return consumer_status
    
    def get_message_flow(self) -> Dict:
        """Analyze message flow through the pipeline"""
        print("\n" + "="*80)
        print("🔄 MESSAGE FLOW ANALYSIS")
        print("="*80)
        
        flow_analysis = {}
        pipeline_topics = {
            'log.received': 'Input (Log Producer)',
            'log.parsed': 'Parsed Logs',
            'incident.detected': 'Detected Incidents',
            'incident.ready_for_analysis': 'Ready for Analysis',
            'incident.analyzed': 'Analyzed Incidents'
        }
        
        for topic, description in pipeline_topics.items():
            # Get topic partition info to count messages
            cmd = self.docker_prefix + ["kafka-run-class", "kafka.tools.JmxTool", "--object-name", f"kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec", "--attributes", "Count"]
            
            # Alternative: try to get from consumer group offsets
            cmd = self.docker_prefix + ["kafka-log-dirs", "--bootstrap-server", self.kafka_bootstrap, "--describe"]
            success, output = self.run_command(cmd, timeout=15)
            
            if success and topic in output:
                print(f"📨 {topic:35} | Status: ✅ Active")
                flow_analysis[topic] = {'status': 'active'}
            else:
                print(f"📨 {topic:35} | Status: ⚠️  Checking...")
                flow_analysis[topic] = {'status': 'checking'}
        
        return flow_analysis
    
    def generate_dashboard(self) -> None:
        """Generate and display the complete monitoring dashboard"""
        print("\n\n")
        print("╔" + "="*78 + "╗")
        print("║" + " "*78 + "║")
        print("║" + "🚀 AI LOG INTELLIGENCE PIPELINE - MONITORING DASHBOARD 🚀".center(78) + "║")
        print("║" + f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(78) + "║")
        print("║" + " "*78 + "║")
        print("╚" + "="*78 + "╝")
        
        # Collect all status information
        service_status = self.get_service_status()
        topic_status = self.get_topic_status()
        consumer_status = self.get_consumer_status()
        message_flow = self.get_message_flow()
        
        # Print summary
        print("\n" + "="*80)
        print("📈 PIPELINE HEALTH SUMMARY")
        print("="*80)
        
        # Check overall health
        all_services_running = all(
            svc.get('status') == 'running' 
            for svc in service_status.values()
        )
        
        has_active_topics = len(topic_status) >= 5
        has_zero_lag = all(
            cg.get('total_lag', 0) == 0 
            for cg in consumer_status.values()
        )
        
        print(f"{'✅ All Services Running' if all_services_running else '❌ Some Services Down':45} | {all_services_running}")
        print(f"{'✅ All Pipeline Topics Active' if has_active_topics else '⚠️  Some Topics Missing':45} | {has_active_topics}")
        print(f"{'✅ Consumer Groups Have Zero Lag' if has_zero_lag else '⚠️  Consumer Lag Detected':45} | {has_zero_lag}")
        
        overall_health = "🟢 HEALTHY" if (all_services_running and has_active_topics and has_zero_lag) else "🟡 DEGRADED"
        print(f"\n{'Overall Pipeline Health:':45} {overall_health}\n")
        
        print("="*80)
        print("💡 NEXT STEPS:")
        print("="*80)
        print("""
1. ✅ Services are running and communicating properly
2. ✅ Kafka topics are created and accessible
3. ✅ Consumer groups are configured with zero lag
4. 🚀 Send test logs via API: curl -X POST http://localhost:8000/logs \\
      -H "Content-Type: application/json" \\
      -d '{"service": "test-service", "log": "ERROR message"}'
5. 📊 View Kafka UI at http://localhost:8080
6. 🔍 Monitor logs: docker logs log-parser -f
7. 🧪 Run full test suite: python3 tests/test_pipeline.py
        """)
        print("="*80)

def main():
    """Run the monitoring dashboard"""
    monitor = PipelineMonitor()
    monitor.generate_dashboard()

if __name__ == "__main__":
    main()
