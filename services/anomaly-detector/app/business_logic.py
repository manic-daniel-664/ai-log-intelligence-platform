import time
import uuid
from common.tracing import extract_correlation_id

# sliding window length in seconds
WINDOW_SECONDS = 60
# thresholds for triggering incidents
ERROR_THRESHOLD = 2
HTTP_THRESHOLD = 3


def process_log(event, redis_client):
    """Process a parsed log event.

    Uses Redis sorted sets to maintain a timestamped window per service.
    When a threshold is exceeded an incident dict is returned.
    Deduplication is handled using a TTL key.
    """
    payload = event['payload']
    correlation_id = extract_correlation_id(event)
    service = payload.get('service')
    level = payload.get('level')
    status = payload.get('status_code')

    now = int(time.time())
    now_ms = int(time.time() * 1000)
    unique_member = f"{now_ms}:{event.get('event_id', str(uuid.uuid4()))}"
    key_error = f"anomaly:{service}:errors"
    key_http = f"anomaly:{service}:http500"

    # increment counters, set TTL
    if level == 'ERROR':
        redis_client.zadd(key_error, {unique_member: now})
        redis_client.expire(key_error, WINDOW_SECONDS)
    if status and status >= 500:
        redis_client.zadd(key_http, {unique_member: now})
        redis_client.expire(key_http, WINDOW_SECONDS)

    # count events in window
    start = now - WINDOW_SECONDS
    err_count = redis_client.zcount(key_error, start, now)
    http_count = redis_client.zcount(key_http, start, now)

    trigger = None
    if err_count >= ERROR_THRESHOLD:
        trigger = "ERROR_SPIKE"
    elif http_count >= HTTP_THRESHOLD:
        trigger = "HTTP_500_SPIKE"

    if trigger:
        # deduplicate using SETNX lock with TTL
        lock_key = f"incident_lock:{service}:{trigger}"
        if redis_client.setnx(lock_key, 1):
            redis_client.expire(lock_key, WINDOW_SECONDS)
            incident = {
                "incident_id": str(uuid.uuid4()),
                "correlation_id": correlation_id,
                "service": service,
                "error_count": err_count if trigger == "ERROR_SPIKE" else http_count,
                "window_seconds": WINDOW_SECONDS,
                "first_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
                "last_seen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "trigger_reason": trigger
            }
            return incident
        else:
            # another incident has been fired recently
            return None
    return None
