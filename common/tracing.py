import copy
import logging
import uuid
from typing import Any, Dict, Optional


class _CorrelationIdFilter(logging.Filter):
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        if not hasattr(record, "service"):
            record.service = self.service_name
        return True


def configure_logging(service_name: str) -> None:
    fmt = (
        "[%(asctime)s] [%(levelname)s] [service=%(service)s] "
        "[correlation_id=%(correlation_id)s] %(message)s"
    )
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    for handler in root.handlers:
        has_filter = any(
            isinstance(existing, _CorrelationIdFilter) and existing.service_name == service_name
            for existing in handler.filters
        )
        if not has_filter:
            handler.addFilter(_CorrelationIdFilter(service_name))


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def extract_correlation_id(event: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(event, dict):
        return None
    correlation_id = event.get("correlation_id")
    if correlation_id is None:
        return None
    return str(correlation_id)


def inject_correlation_id(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    new_event = copy.deepcopy(event)
    new_event["correlation_id"] = correlation_id
    return new_event


def get_logger(correlation_id: Optional[str], name: Optional[str] = None) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logging.getLogger(name), {"correlation_id": correlation_id or "-"})

