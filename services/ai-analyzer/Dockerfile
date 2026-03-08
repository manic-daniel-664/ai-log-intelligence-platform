FROM python:3.11-slim

WORKDIR /app

COPY services/ai-analyzer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ai-analyzer/app/ .
COPY common/ ./common/

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
