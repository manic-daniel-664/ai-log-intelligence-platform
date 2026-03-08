import signal
import sys
from confluent_kafka import Consumer, Producer
import json, uuid
import redis
import time
from business_logic import process_log
from common.tracing import configure_logging, extract_correlation_id, get_logger

configure_logging("anomaly-detector")
logger = get_logger("-", __name__)

shutdown = False

def handle_signal(sig, frame):
    global shutdown
    logger.info(f"Received signal {sig}, shutting down")
    shutdown = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# configuration
consumer_conf = {
    'bootstrap.servers': 'kafka:29092',
    'group.id': 'anomaly-detector-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}
producer_conf = {
    'bootstrap.servers': 'kafka:29092'
}


def _extract_correlation_id_from_headers(msg) -> str | None:
    headers = msg.headers() or []
    for key, value in headers:
        if key == "correlation_id" and value is not None:
            return value.decode()
    return None

def main():
    r = redis.Redis(host='redis', port=6379, db=0)
    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    consumer.subscribe(['log.parsed'])

    logger.info("Anomaly Detector started")
    try:
        while not shutdown:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print("Kafka error", msg.error())
                continue
            try:
                event = json.loads(msg.value().decode())
                correlation_id = extract_correlation_id(event) or _extract_correlation_id_from_headers(msg) or "-"
                clogger = get_logger(correlation_id, __name__)
                clogger.info(f"Message received from topic {msg.topic()} partition {msg.partition()} offset {msg.offset()}")
                # idempotency: skip if this raw event already seen
                eid = event.get('event_id')
                if eid and r.get(f"processed:{eid}"):
                    clogger.info(f"Skipping already processed event {eid}")
                    consumer.commit(msg)
                    continue
                incident = process_log(event, r)
                if incident:
                    clogger.info(f"Incident triggered for service {incident['service']} reason {incident['trigger_reason']}")
                    # produce incident.detected
                    incident_event = {
                        "event_id": str(uuid.uuid4()),
                        "correlation_id": correlation_id,
                        "event_type": "incident.detected",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "version": "v1",
                        "payload": incident
                    }
                    producer.produce(
                        "incident.detected",
                        json.dumps(incident_event),
                        headers=[("correlation_id", correlation_id.encode())],
                    )
                    producer.flush()
                # mark raw event processed with TTL
                if eid:
                    r.set(f"processed:{eid}", 1, ex=300)
                consumer.commit(msg)
                clogger.info(f"Offset committed for {msg.topic()}:{msg.partition()}:{msg.offset()}")
            except Exception as e:
                correlation_id = extract_correlation_id(event) if 'event' in locals() else "-"
                clogger = get_logger(correlation_id, __name__)
                clogger.exception("Processing error")
                # send to dead-letter
                try:
                    producer.produce(
                        "dead.letter.queue",
                        msg.value(),
                        headers=[("correlation_id", (correlation_id or "-").encode())],
                    )
                    producer.flush()
                except Exception:
                    clogger.exception("Failed to publish to DLQ")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()
