FROM python:3.11-slim

WORKDIR /app

COPY services/log-producer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/log-producer/app/ ./app/
COPY common/ ./common/

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
