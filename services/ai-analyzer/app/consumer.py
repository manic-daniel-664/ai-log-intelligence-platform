import signal
import sys
from confluent_kafka import Consumer, Producer
import json, time
from business_logic import analyze_incident, IncidentAnalysis, Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from common.tracing import configure_logging, extract_correlation_id, get_logger

configure_logging("ai-analyzer")
logger = get_logger("-", __name__)
shutdown = False

def handle_signal(sig, frame):
    global shutdown
    logger.info(f"Received signal {sig}, shutting down")
    shutdown = True

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

consumer_conf = {
    'bootstrap.servers': 'kafka:29092',
    'group.id': 'ai-analyzer-group',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False
}
producer_conf = {'bootstrap.servers': 'kafka:29092'}


def _extract_correlation_id_from_headers(msg) -> str | None:
    headers = msg.headers() or []
    for key, value in headers:
        if key == "correlation_id" and value is not None:
            return value.decode()
    return None


def main():
    # set up database
    engine = create_engine('postgresql://admin:admin@postgres:5432/incidents')
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE incident_analysis ADD COLUMN IF NOT EXISTS correlation_id UUID"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_incident_analysis_correlation_id ON incident_analysis(correlation_id)"))
        conn.commit()
    Session = sessionmaker(bind=engine)

    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    consumer.subscribe(['incident.detected'])

    logger.info("AI analyzer started")
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
                clogger.info(f"Message received for analysis: offset {msg.offset()} partition {msg.partition()}")
                db_session = Session()
                try:
                    analysis = analyze_incident(event, db_session)
                finally:
                    db_session.close()
                if analysis:
                    clogger.info(f"Analysis completed for incident {analysis['incident_id']} severity={analysis['severity']}")
                    out_event = {
                        "event_id": str(time.time()),
                        "correlation_id": correlation_id,
                        "event_type": "incident.analyzed",
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "version": "v1",
                        "payload": analysis
                    }
                    producer.produce(
                        'incident.analyzed',
                        json.dumps(out_event),
                        headers=[("correlation_id", correlation_id.encode())],
                    )
                    producer.flush()
                consumer.commit(msg)
                clogger.info(f"Offset committed for analysis topic {msg.topic()}:{msg.partition()}:{msg.offset()}")
            except Exception as e:
                correlation_id = extract_correlation_id(event) if 'event' in locals() else "-"
                clogger = get_logger(correlation_id, __name__)
                clogger.exception("Processing error")
                try:
                    producer.produce(
                        'dead.letter.queue',
                        msg.value(),
                        headers=[("correlation_id", (correlation_id or "-").encode())],
                    )
                    producer.flush()
                    consumer.commit(msg)
                    clogger.info(f"Offset committed after DLQ publish for {msg.topic()}:{msg.partition()}:{msg.offset()}")
                except Exception:
                    clogger.exception("Failed to publish to DLQ")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()
