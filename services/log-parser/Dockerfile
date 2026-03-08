FROM python:3.11-slim

WORKDIR /app

COPY services/log-parser/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/log-parser/app/ .
COPY common/ ./common/

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
