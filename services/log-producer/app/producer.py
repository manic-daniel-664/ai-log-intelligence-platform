from confluent_kafka import Producer
import json
import uuid
from datetime import datetime
from common.tracing import generate_correlation_id, get_logger

conf = {
    'bootstrap.servers': 'kafka:29092'
}

producer = Producer(conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def publish_log_event(service_name: str, raw_log: str) -> str:
    correlation_id = generate_correlation_id()
    logger = get_logger(correlation_id, __name__)

    event = {
        "event_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "event_type": "log.received",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "v1",
        "payload": {
            "service": service_name,
            "raw_log": raw_log
        }
    }

    producer.produce(
        topic="log.received",
        value=json.dumps(event),
        headers=[("correlation_id", correlation_id.encode())],
        callback=delivery_report
    )

    producer.flush()
    logger.info("Published log.received event")
    return correlation_id
