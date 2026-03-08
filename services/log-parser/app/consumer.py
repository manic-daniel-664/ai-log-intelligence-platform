from confluent_kafka import Consumer, Producer
from elasticsearch import Elasticsearch
import json
import uuid
from datetime import datetime
from parser import parse_log
from common.tracing import configure_logging, extract_correlation_id, get_logger

configure_logging("log-parser")
base_logger = get_logger("-", __name__)

consumer_conf = {
    "bootstrap.servers": "kafka:29092",
    "group.id": "log-parser-group",
    "auto.offset.reset": "earliest",
}

producer_conf = {
    "bootstrap.servers": "kafka:29092",
}

consumer = Consumer(consumer_conf)
producer = Producer(producer_conf)

es = Elasticsearch("http://elasticsearch:9200")

consumer.subscribe(["log.received"])
base_logger.info("Log Parser started and subscribed to log.received")


def _extract_correlation_id_from_headers(msg) -> str | None:
    headers = msg.headers() or []
    for key, value in headers:
        if key == "correlation_id" and value is not None:
            return value.decode()
    return None


def run():
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue

        if msg.error():
            base_logger.error(f"Kafka error: {msg.error()}")
            continue

        event = json.loads(msg.value().decode())
        correlation_id = extract_correlation_id(event) or _extract_correlation_id_from_headers(msg) or "-"
        logger = get_logger(correlation_id, __name__)
        logger.info(f"Message received from {msg.topic()}:{msg.partition()}:{msg.offset()}")

        raw_log = event["payload"]["raw_log"]
        service_name = event["payload"]["service"]
        parsed = parse_log(raw_log)

        structured_log = {
            "event_id": event["event_id"],
            "correlation_id": correlation_id,
            "service": service_name,
            "timestamp": datetime.utcnow().isoformat(),
            **parsed,
        }

        # Temporarily disabled for testing
        # es.index(index="logs", document=structured_log)
        logger.info("Parsed log and prepared structured payload")

        next_event = {
            "event_id": str(uuid.uuid4()),
            "correlation_id": correlation_id,
            "event_type": "log.parsed",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "v1",
            "payload": structured_log,
        }

        producer.produce(
            "log.parsed",
            json.dumps(next_event),
            headers=[("correlation_id", correlation_id.encode())],
        )
        producer.flush()
        logger.info("Published log.parsed event")
