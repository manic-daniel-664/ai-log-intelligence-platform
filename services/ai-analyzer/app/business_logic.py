import time
import json
import logging
import os
import google.generativeai as genai
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from common.tracing import extract_correlation_id, get_logger

logger = logging.getLogger(__name__)


def _init_gemini_model():
    """Initialize Gemini model once at service startup."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not set; Gemini client will remain disabled")
        return None
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))


MODEL = _init_gemini_model()

Base = declarative_base()

class IncidentAnalysis(Base):
    __tablename__ = 'incident_analysis'
    incident_id = Column(String, primary_key=True)
    correlation_id = Column(UUID(as_uuid=False), nullable=True, index=True)
    service = Column(String)
    trigger_reason = Column(String)
    severity = Column(String)
    root_cause = Column(String)
    mitigation = Column(String)
    confidence = Column(Integer)
    created_at = Column(DateTime)


def parse_llm_response(text: str) -> dict:
    """
    Safely parse LLM response text into structured JSON.

    Strips markdown fences, extracts JSON, validates required keys.
    """
    cleaned = text.strip()

    # Strip markdown code fences if present
    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):]
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-len("```")]
    cleaned = cleaned.strip()

    # Safely extract the first balanced JSON object if extra text is present
    start = cleaned.find("{")
    if start == -1:
        logger.error("JSON parsing failure: no JSON object detected in response")
        raise ValueError("No JSON object found in LLM response")

    depth = 0
    end = -1
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        logger.error("JSON parsing failure: unmatched braces in response")
        raise ValueError("Unmatched JSON braces in LLM response")

    json_block = cleaned[start:end + 1]

    try:
        data = json.loads(json_block)

        # Validate required keys
        required_keys = ["root_cause", "severity", "mitigation", "confidence"]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key: {key}")

        # Validate severity
        if data["severity"] not in ["Low", "Medium", "High", "Critical"]:
            raise ValueError(f"Invalid severity: {data['severity']}")

        # Validate confidence
        if not isinstance(data["confidence"], int) or not (0 <= data["confidence"] <= 100):
            raise ValueError(f"Invalid confidence: {data['confidence']}")

        return data

    except json.JSONDecodeError as e:
        logger.error("JSON parsing failure: invalid JSON payload")
        raise ValueError(f"Invalid JSON response: {e}") from e
    except ValueError as e:
        logger.error("JSON parsing failure: schema validation failed")
        raise ValueError(str(e)) from e


def call_llm(prompt: str, correlation_id: str = "-") -> dict:
    """
    LLM integration with Google Gemini.
    
    Uses stub if USE_REAL_LLM != "true", otherwise calls Gemini API.
    """
    clogger = get_logger(correlation_id, __name__)
    use_real_llm = os.getenv("USE_REAL_LLM", "").lower() == "true"
    if not use_real_llm:
        clogger.info("Using LLM stub response (USE_REAL_LLM is not true)")
        return {
            "root_cause": "Example cause",
            "severity": "Medium",
            "mitigation": "Restart service",
            "confidence": 80
        }

    if not MODEL:
        raise ValueError("Gemini model not initialized - check GEMINI_API_KEY")

    clogger.info("LLM call started")

    # Strict output instructions
    full_prompt = (
        f"{prompt}\n\n"
        "Return strictly valid JSON.\n"
        "No explanations.\n"
        "No markdown.\n"
        "No code fences.\n\n"
        "Expected format:\n"
        "{\n"
        '  "root_cause": "...",\n'
        '  "severity": "Low|Medium|High|Critical",\n'
        '  "mitigation": "...",\n'
        '  "confidence": 0-100\n'
        "}"
    )

    attempts = 3
    delay_seconds = 1
    for attempt in range(1, attempts + 1):
        try:
            clogger.info(f"LLM call attempt {attempt}/{attempts}")
            response = MODEL.generate_content(full_prompt)
            raw_text = response.text
            parsed = parse_llm_response(raw_text)
            clogger.info("LLM call success")
            return parsed
        except Exception as e:
            if attempt == attempts:
                clogger.error(f"Final LLM failure after {attempts} attempts: {e}")
                raise
            clogger.warning(f"Retry triggered after attempt {attempt}: {e}")
            time.sleep(delay_seconds)
            delay_seconds *= 2


def analyze_incident(event, db_session):
    """Perform AI analysis on detected incident.

    - Check idempotency using PostgreSQL
    - Construct prompt for LLM
    - Store result in database
    - Return analysis payload for Kafka publication
    """
    payload = event['payload']
    correlation_id = extract_correlation_id(event) or "-"
    clogger = get_logger(correlation_id, __name__)
    incident_id = payload['incident_id']
    # idempotency
    existing = db_session.query(IncidentAnalysis).filter_by(incident_id=incident_id).first()
    if existing:
        clogger.info(f"Skipping existing incident {incident_id} due to idempotency")
        return None

    prompt = (
        f"You are a senior Site Reliability Engineer.\n"
        f"Analyze this incident:\nService: {payload['service']}\n"
        f"Error Count: {payload.get('error_count')}\n"
        f"Trigger Reason: {payload['trigger_reason']}"
    )

    result = call_llm(prompt, correlation_id=correlation_id)

    analysis = IncidentAnalysis(
        incident_id=incident_id,
        correlation_id=correlation_id,
        service=payload['service'],
        trigger_reason=payload['trigger_reason'],
        severity=result['severity'],
        root_cause=result['root_cause'],
        mitigation=result['mitigation'],
        confidence=result['confidence'],
        created_at=datetime.utcnow()
    )
    db_session.add(analysis)
    db_session.commit()
    return {
        "incident_id": incident_id,
        "correlation_id": correlation_id,
        "root_cause": result['root_cause'],
        "severity": result['severity'],
        "mitigation": result['mitigation'],
        "confidence": result['confidence']
    }
