"""Prometheus metrics endpoint utilities for the FastAPI application."""

from __future__ import annotations

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest


async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics collected by the default registry."""

    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


__all__ = ["metrics_endpoint"]
