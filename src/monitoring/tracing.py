"""OpenTelemetry configuration helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from config.settings import settings

# Optional import for Jaeger - only needed if Jaeger is configured
try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter

    JAEGER_AVAILABLE = True
except ImportError:
    JAEGER_AVAILABLE = False


def _build_exporters() -> list[BatchSpanProcessor]:
    processors: list[BatchSpanProcessor] = []

    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT

        # Ensure endpoint has a scheme (http:// or https://)
        # OTLPSpanExporter in opentelemetry-exporter-otlp >= 1.15.0
        # automatically determines security from the URL scheme
        if not urlparse(endpoint).scheme:
            # If OTEL_EXPORTER_OTLP_INSECURE is set, use it to determine scheme
            insecure = settings.OTEL_EXPORTER_OTLP_INSECURE
            if insecure:
                endpoint = f"http://{endpoint}"
            else:
                endpoint = f"https://{endpoint}"

        processors.append(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    if settings.OTEL_EXPORTER_JAEGER_HOST:
        if JAEGER_AVAILABLE:
            processors.append(
                BatchSpanProcessor(
                    JaegerExporter(
                        agent_host_name=settings.OTEL_EXPORTER_JAEGER_HOST,
                        agent_port=settings.OTEL_EXPORTER_JAEGER_PORT,
                    )
                )
            )
        else:
            # Jaeger exporter not available - skip silently since tracing is optional
            pass

    return processors


def configure_tracing(app: FastAPI) -> None:
    """Configure OpenTelemetry exporters and instrument the FastAPI application."""

    if getattr(app.state, "otel_configured", False):
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME or settings.APP_NAME})
    processors = _build_exporters()
    if not processors:
        return

    tracer_provider = TracerProvider(resource=resource)

    for processor in processors:
        tracer_provider.add_span_processor(processor)

    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls=settings.PROMETHEUS_ROUTE)
    app.state.otel_configured = True


__all__ = ["configure_tracing"]
