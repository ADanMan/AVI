import math

import pytest

from src.core.content_filter import ContentFilterService, SafetyMode
from src.models.schemas import FilterMatch
from src.monitoring.metrics import ContentFilterMetrics, content_filter_metrics


class StubVectorDB:
    async def find_matching_rules(self, text: str, n_results: int = 10):
        if "unsafe" in text:
            return [
                FilterMatch(
                    rule_id="r1",
                    rule_text="unsafe",
                    category="toxicity",
                    risk_level=5,
                    relevance_score=0.9,
                )
            ]
        return []

    async def get_rule_threshold(self, rule_text: str) -> float:
        return 0.5


def test_mode_stats_basic_counts():
    metrics = ContentFilterMetrics()
    metrics.reset()

    metrics.record("disabled", True, 0.1, True)
    metrics.record("disabled", True, 0.2, False, sanitization_latency_seconds=0.5)
    metrics.record("disabled", False, 0.05, True)
    metrics.record("disabled", False, 0.03, False, sanitization_latency_seconds=0.2)

    snapshot = metrics.snapshot()["disabled"]
    assert snapshot["true_positive"] == 1
    assert snapshot["false_positive"] == 1
    assert snapshot["false_negative"] == 1
    assert snapshot["true_negative"] == 1
    detection_latency = snapshot["detection_latency"]
    assert detection_latency["count"] == 4
    assert math.isclose(detection_latency["avg"], (0.1 + 0.2 + 0.05 + 0.03) / 4, rel_tol=1e-6)
    sanitization_latency = snapshot["sanitization_latency"]
    assert sanitization_latency["count"] == 2
    assert math.isclose(sanitization_latency["avg"], (0.5 + 0.2) / 2, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_content_filter_records_metrics():
    content_filter_metrics.reset()
    vector_db = StubVectorDB()
    service = ContentFilterService(vector_db=vector_db, mode=SafetyMode.DISABLED)

    await service.check_content("unsafe query", ground_truth=True)
    await service.check_content("fully safe", ground_truth=False)
    await service.check_content("benign but labeled", ground_truth=True)

    snapshot = content_filter_metrics.snapshot()
    assert SafetyMode.DISABLED.value in snapshot
    stats = snapshot[SafetyMode.DISABLED.value]
    assert stats["true_positive"] == 1
    assert stats["true_negative"] == 1
    assert stats["false_negative"] == 1
    assert stats["false_positive"] == 0
    detection_latency = stats["detection_latency"]
    assert detection_latency["count"] == 3
    assert detection_latency["avg"] is not None
    sanitization_latency = stats["sanitization_latency"]
    assert sanitization_latency["count"] == 0

    result = await service.check_content("unsafe query", ground_truth=True)
    assert result.safety_mode == SafetyMode.DISABLED.value
    assert result.detection_latency_ms is not None
    assert result.latency_ms == result.detection_latency_ms
    content_filter_metrics.reset()


def test_content_filter_import_without_loguru(monkeypatch):
    """Ensure the content filter works when Loguru is unavailable."""

    import asyncio
    import builtins
    import importlib
    import sys

    # Save the original modules before we mess with them
    # Note: We exclude src.services.vector_db from removal because it has global state
    # (Qdrant client cache) that should persist across tests
    modules_to_restore = [
        "loguru",
        "src.utils.logger",
        "config.settings",
        "src.monitoring.metrics",
        "src.core.content_filter",
        "src.services.llm_adapter",
    ]
    saved_modules = {name: sys.modules.get(name) for name in modules_to_restore}

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "loguru":
            raise ModuleNotFoundError("No module named 'loguru'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # Clear Prometheus registry to avoid duplicate metrics errors
    from prometheus_client import REGISTRY

    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass

    for module_name in modules_to_restore:
        sys.modules.pop(module_name, None)

    try:
        metrics_module = importlib.import_module("src.monitoring.metrics")
        content_filter_module = importlib.import_module("src.core.content_filter")

        metrics_module.content_filter_metrics.reset()
        service = content_filter_module.ContentFilterService(
            vector_db=StubVectorDB(),
            mode=content_filter_module.SafetyMode.DISABLED,
        )

        asyncio.run(service.check_content("unsafe query", ground_truth=True))

        snapshot = metrics_module.content_filter_metrics.snapshot()
        mode_key = content_filter_module.SafetyMode.DISABLED.value
        assert mode_key in snapshot
        assert snapshot[mode_key]["true_positive"] >= 1
    finally:
        # Restore original modules to avoid polluting other tests
        for module_name, original_module in saved_modules.items():
            if original_module is not None:
                sys.modules[module_name] = original_module
            else:
                sys.modules.pop(module_name, None)

        # Force reload of key modules to ensure fresh state
        if "src.core.content_filter" in sys.modules:
            importlib.reload(sys.modules["src.core.content_filter"])
