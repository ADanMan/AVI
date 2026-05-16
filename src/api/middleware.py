"""Custom FastAPI middlewares for observability features."""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.monitoring.observability import observe_request_latency
from src.utils.logger import reset_correlation_id, set_correlation_id


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Measure request latency and emit metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        start_time = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start_time
            status_code = response.status_code if response is not None else 500
            route = getattr(request.scope.get("route"), "path", request.url.path)
            observe_request_latency(request.method, route, status_code, duration)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Propagate correlation IDs across incoming requests and responses."""

    def __init__(self, app: ASGIApp, header_name: str = "X-Correlation-ID") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        header_key = self.header_name
        incoming = request.headers.get(header_key)
        correlation_id = incoming or str(uuid.uuid4())
        token = set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        finally:
            reset_correlation_id(token)

        response.headers[header_key] = correlation_id
        return response


__all__ = ["CorrelationIdMiddleware", "RequestMetricsMiddleware"]
