FROM python:3.11-slim

WORKDIR /app

COPY services/anomaly-detector/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/anomaly-detector/app/ .
COPY common/ ./common/

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
