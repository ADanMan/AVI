# syntax=docker/dockerfile:1
# Dockerfile for AVI - Content Safety System
# Multi-stage build for CPU and GPU variants

# =============================================================================
# BASE STAGE - Common dependencies
# =============================================================================
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# Install system dependencies with retry and fallback
RUN apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        curl \
    || (apt-get clean && apt-get update && apt-get install -y --no-install-recommends --fix-missing build-essential curl) \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and constraints
COPY requirements.txt ./
COPY constraints.txt ./

# Create required directories
RUN mkdir -p data/raw data/processed data/indexes data/feedback data/logs

# =============================================================================
# CPU STAGE - CPU-only inference (default)
# =============================================================================
FROM base AS cpu

ENV DEVICE=cpu

# Install CPU dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set up entrypoint script
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# =============================================================================
# GPU STAGE - CUDA-enabled inference
# =============================================================================
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04 AS gpu

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TOKENIZERS_PARALLELISM=false \
    DEVICE=cuda

WORKDIR /app

# Install Python and system dependencies with retry and fallback
RUN apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
        python3.11 \
        python3.11-venv \
        python3-pip \
        build-essential \
        curl \
    || (apt-get clean && apt-get update && apt-get install -y --no-install-recommends --fix-missing python3.11 python3.11-venv python3-pip build-essential curl) \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./
COPY constraints.txt ./

# Install GPU dependencies (PyTorch with CUDA)
RUN pip install --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121 \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p data/raw data/processed data/indexes data/feedback data/logs

# Set up entrypoint script
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
