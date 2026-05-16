"""Prometheus metrics utilities shared across the application."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from config.settings import settings


_NAMESPACE = settings.METRICS_NAMESPACE or "avi"


_REQUEST_LATENCY = Histogram(
    "http_request_latency_seconds",
    "Latency of FastAPI requests handled by AVI.",
    labelnames=("method", "route", "status_code"),
    namespace=_NAMESPACE,
)

_CACHE_HITS = Counter(
    "cache_hits_total",
    "Number of cache hits returned by AVI caches.",
    labelnames=("backend",),
    namespace=_NAMESPACE,
)

_CACHE_MISSES = Counter(
    "cache_misses_total",
    "Number of cache misses encountered by AVI caches.",
    labelnames=("backend",),
    namespace=_NAMESPACE,
)

_SAFETY_INTERVENTIONS = Counter(
    "safety_interventions_total",
    "Count of safety interventions that modified content.",
    labelnames=("stage", "mode"),
    namespace=_NAMESPACE,
)

_RERANK_LATENCY = Histogram(
    "rerank_latency_seconds",
    "Latency spent on cross-encoder reranking operations.",
    labelnames=("model",),
    namespace=_NAMESPACE,
)


def observe_request_latency(
    method: str, route: str, status_code: int, duration_seconds: float
) -> None:
    """Record API request latency for Prometheus when enabled."""

    if not settings.PROMETHEUS_ENABLED:
        return
    _REQUEST_LATENCY.labels(
        method=method,
        route=route,
        status_code=str(status_code),
    ).observe(duration_seconds)


def record_cache_hit(backend: str) -> None:
    """Increment cache hit counter for the given backend when metrics are enabled."""

    if not settings.PROMETHEUS_ENABLED:
        return
    _CACHE_HITS.labels(backend=backend).inc()


def record_cache_miss(backend: str) -> None:
    """Increment cache miss counter for the given backend when metrics are enabled."""

    if not settings.PROMETHEUS_ENABLED:
        return
    _CACHE_MISSES.labels(backend=backend).inc()


def record_safety_intervention(stage: str, mode: str | None) -> None:
    """Increment safety intervention counter for the provided processing stage."""

    if not settings.PROMETHEUS_ENABLED:
        return
    _SAFETY_INTERVENTIONS.labels(stage=stage, mode=mode or "unknown").inc()


def observe_rerank_latency(model: str, duration_seconds: float) -> None:
    """Track latency spent reranking search results."""

    if not settings.PROMETHEUS_ENABLED:
        return
    _RERANK_LATENCY.labels(model=model or "unknown").observe(duration_seconds)


__all__ = [
    "observe_request_latency",
    "observe_rerank_latency",
    "record_cache_hit",
    "record_cache_miss",
    "record_safety_intervention",
]
