from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

Base = declarative_base()

class IncidentAnalysis(Base):
    __tablename__ = 'incident_analysis'
    incident_id = Column(String, primary_key=True)
    correlation_id = Column(UUID(as_uuid=False), nullable=True, index=True)
    service = Column(String(100))
    trigger_reason = Column(String(100))
    severity = Column(String(50))
    root_cause = Column(String)
    mitigation = Column(String)
    confidence = Column(Integer)
    created_at = Column(DateTime)
