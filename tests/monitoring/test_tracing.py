"""Tests for tracing exporter configuration."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT_PATH = Path(__file__).resolve().parents[2]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from src.monitoring import tracing


@pytest.fixture
def otlp_stubs(monkeypatch):
    """Stub OTLP exporter and batch processor to capture configuration."""

    exported = {}

    class DummyExporter:
        def __init__(self, **kwargs):
            exported.update(kwargs)

    processors = []

    class DummyBatchProcessor:
        def __init__(self, exporter):
            self.exporter = exporter
            processors.append(self)

    monkeypatch.setattr(tracing, "OTLPSpanExporter", DummyExporter)
    monkeypatch.setattr(tracing, "BatchSpanProcessor", DummyBatchProcessor)

    return exported, processors


def test_otlp_exporter_defaults_to_secure_for_https(monkeypatch, otlp_stubs):
    """HTTPS endpoints should configure a secure OTLP exporter by default."""

    exported, processors = otlp_stubs
    fake_settings = SimpleNamespace(
        OTEL_EXPORTER_OTLP_ENDPOINT="https://collector:4318/v1/traces",
        OTEL_EXPORTER_OTLP_INSECURE=None,
        OTEL_EXPORTER_JAEGER_HOST=None,
        OTEL_EXPORTER_JAEGER_PORT=None,
    )
    monkeypatch.setattr(tracing, "settings", fake_settings)

    exporters = tracing._build_exporters()

    assert exporters == processors
    assert exported == {
        "endpoint": "https://collector:4318/v1/traces",
    }


def test_otlp_exporter_supports_insecure_http(monkeypatch, otlp_stubs):
    """HTTP endpoints should opt into insecure transport unless overridden."""

    exported, processors = otlp_stubs
    fake_settings = SimpleNamespace(
        OTEL_EXPORTER_OTLP_ENDPOINT="http://collector:4318/v1/traces",
        OTEL_EXPORTER_OTLP_INSECURE=None,
        OTEL_EXPORTER_JAEGER_HOST=None,
        OTEL_EXPORTER_JAEGER_PORT=None,
    )
    monkeypatch.setattr(tracing, "settings", fake_settings)

    exporters = tracing._build_exporters()

    assert exporters == processors
    assert exported == {
        "endpoint": "http://collector:4318/v1/traces",
    }
