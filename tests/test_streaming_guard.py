import os
import sys

os.environ["AVI_TEST_MODE"] = "1"
os.environ["REQUIRE_API_KEY"] = "false"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import json

import pytest

httpx = pytest.importorskip(
    "httpx",
    reason="httpx is required to exercise the streaming API; install via requirements.main.txt",
)
from httpx import AsyncClient  # import after runtime availability check

from main import app
from src.api import routes
from src.core.streaming_guard import StreamingGuard, StreamingGuardMode
from src.models.schemas import FilterMatch, FilterResult


class DummySafetyLLM:
    def __init__(self, replacement: str):
        self.replacement = replacement
        self.calls = 0

    async def generate_response(self, query: str, context=None, **kwargs):
        self.calls += 1
        return self.replacement


class DummyContentFilter:
    def __init__(self, toxic_tokens=None, safety_llm=None):
        self.toxic_tokens = toxic_tokens or set()
        self.safety_llm = safety_llm

    async def check_content(
        self,
        text: str,
        use_llm: bool = False,
        use_linked_docs: bool = False,
        is_input: bool = False,
        context=None,
    ) -> FilterResult:
        matches = []
        if any(token in text for token in self.toxic_tokens):
            matches.append(
                FilterMatch(
                    rule_id="toxicity",
                    rule_text="toxic token",
                    category="toxicity",
                    risk_level=5,
                    relevance_score=0.95,
                )
            )
        return FilterResult(
            original_text=text,
            was_modified=False,
            matches=matches,
        )


@pytest.mark.asyncio
async def test_streaming_guard_blocks_on_rule_violation():
    guard = StreamingGuard(
        content_filter=DummyContentFilter(toxic_tokens={"toxic"}),
        mode=StreamingGuardMode.RULE_ONLY,
    )

    decision = await guard.process_chunk("this is toxic text")

    assert not decision.allowed
    assert decision.stop_stream is True
    assert guard.metrics.processed_chunks == 1
    assert guard.metrics.flagged_chunks == 1
    assert guard.metrics.blocked_chunks == 1


@pytest.mark.asyncio
async def test_streaming_guard_sanitizes_in_hybrid_mode():
    safety = DummySafetyLLM(replacement="clean chunk")
    guard = StreamingGuard(
        content_filter=DummyContentFilter(toxic_tokens={"toxic"}, safety_llm=safety),
        mode=StreamingGuardMode.HYBRID,
    )

    decision = await guard.process_chunk("toxic output")

    assert decision.allowed
    assert decision.filtered
    assert decision.content == "clean chunk"
    assert guard.metrics.flagged_chunks == 1
    assert guard.metrics.sanitized_chunks == 1
    assert safety.calls == 1


@pytest.mark.asyncio
async def test_streaming_guard_llm_only_sanitizes_without_rules():
    safety = DummySafetyLLM(replacement="safe text")
    guard = StreamingGuard(
        content_filter=DummyContentFilter(safety_llm=safety),
        mode=StreamingGuardMode.LLM_ONLY,
    )

    decision = await guard.process_chunk("raw")

    assert decision.allowed
    assert decision.content == "safe text"
    assert decision.filtered
    assert guard.metrics.sanitized_chunks == 1
    assert safety.calls == 1


@pytest.mark.asyncio
async def test_streaming_endpoint_emits_guard_events(monkeypatch):
    dummy_filter = DummyContentFilter(toxic_tokens={"toxic"})
    monkeypatch.setattr(routes.rag_system, "content_filter", dummy_filter)

    async def fake_stream(*args, **kwargs):
        for chunk in ("hello", "toxic chunk", "ignored"):
            yield chunk

    monkeypatch.setattr(
        routes.rag_system.external_llm,
        "generate_streaming_response",
        fake_stream,
    )

    from httpx import ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        async with ac.stream(
            "POST",
            "/api/v1/query/stream",
            json={"query": "hi"},
            params={"stream_mode": "rule-only"},
        ) as response:
            assert response.status_code == 200
            body = "".join([chunk async for chunk in response.aiter_text()])

    events = [line for line in body.split("\n\n") if line.startswith("data: ")]
    payloads = [json.loads(event.split("data: ", 1)[1]) for event in events]

    # Verify SSE stream contains expected event types
    # First data event is always input_filter_result
    assert any(p.get("event") == "input_filter_result" for p in payloads)
    # Stream must contain at least one chunk or a guard event
    has_chunk = any("chunk" in p for p in payloads)
    has_guard_event = any(p.get("event") in ("guard_blocked", "guard_metrics") for p in payloads)
    assert has_chunk or has_guard_event, "Stream must emit chunk or guard event"
    metrics_event = next((p for p in payloads if p.get("event") == "guard_metrics"), None)
    assert metrics_event is not None, "Stream must emit guard_metrics event"
    assert "metrics" in metrics_event
