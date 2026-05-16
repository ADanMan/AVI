# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
COPY constraints.txt /tmp/constraints.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY safety_service /app/safety_service
COPY src /app/src

EXPOSE 8001 50051

CMD ["uvicorn", "safety_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
