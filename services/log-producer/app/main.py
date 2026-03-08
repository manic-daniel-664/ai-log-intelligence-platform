from fastapi import FastAPI
from pydantic import BaseModel
from app.producer import publish_log_event
from common.tracing import configure_logging, get_logger

app = FastAPI()
configure_logging("log-producer")
logger = get_logger("-", __name__)

class LogRequest(BaseModel):
    service: str
    log: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/logs")
def receive_log(data: LogRequest):
    correlation_id = publish_log_event(data.service, data.log)
    get_logger(correlation_id, __name__).info("Accepted inbound log")
    return {"message": "Log event published", "correlation_id": correlation_id}
