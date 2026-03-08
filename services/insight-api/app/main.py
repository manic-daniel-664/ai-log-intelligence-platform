from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models, database
from typing import List
from pydantic import BaseModel
from common.tracing import configure_logging, get_logger

configure_logging("insight-api")
logger = get_logger("-", __name__)

app = FastAPI()

logger.info("Insight API service starting")

# ensure tables exist
models.Base.metadata.create_all(bind=database.engine)
with database.engine.connect() as conn:
    conn.execute(text("ALTER TABLE incident_analysis ADD COLUMN IF NOT EXISTS correlation_id UUID"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_incident_analysis_correlation_id ON incident_analysis(correlation_id)"))
    conn.commit()


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


class IncidentResponse(BaseModel):
    incident_id: str
    correlation_id: str | None = None
    service: str
    trigger_reason: str
    severity: str
    root_cause: str
    mitigation: str
    confidence: int
    created_at: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/incidents", response_model=List[IncidentResponse])
def list_incidents(db: Session = Depends(get_db)):
    rows = db.query(models.IncidentAnalysis).all()
    incidents = []
    for row in rows:
        incident_dict = {
            "incident_id": row.incident_id,
            "correlation_id": str(row.correlation_id) if row.correlation_id else None,
            "service": row.service,
            "trigger_reason": row.trigger_reason,
            "severity": row.severity,
            "root_cause": row.root_cause,
            "mitigation": row.mitigation,
            "confidence": row.confidence,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        incidents.append(incident_dict)
    return incidents


@app.get("/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    row = db.query(models.IncidentAnalysis).filter_by(incident_id=incident_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "incident_id": row.incident_id,
        "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        "service": row.service,
        "trigger_reason": row.trigger_reason,
        "severity": row.severity,
        "root_cause": row.root_cause,
        "mitigation": row.mitigation,
        "confidence": row.confidence,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@app.get("/incidents/{incident_id}/analysis")
def get_analysis(incident_id: str, db: Session = Depends(get_db)):
    row = db.query(models.IncidentAnalysis).filter_by(incident_id=incident_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        "root_cause": row.root_cause,
        "severity": row.severity,
        "mitigation_steps": row.mitigation,
        "confidence": row.confidence
    }
