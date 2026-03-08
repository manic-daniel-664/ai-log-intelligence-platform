import re

def parse_log(raw_log: str):

    level_match = re.search(r"(ERROR|INFO|WARN)", raw_log)
    status_match = re.search(r"\b(\d{3})\b", raw_log)
    time_match = re.search(r"(\d+)ms", raw_log)

    return {
        "level": level_match.group(1) if level_match else "UNKNOWN",
        "status_code": int(status_match.group(1)) if status_match else None,
        "response_time_ms": int(time_match.group(1)) if time_match else None,
        "message": raw_log
    }
