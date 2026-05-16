import asyncio
import os
import sys
import types

import pytest

os.environ.setdefault("AVI_TEST_MODE", "1")
if "loguru" not in sys.modules:  # pragma: no cover - fallback for minimal test deps
    dummy_logger = types.SimpleNamespace(
        debug=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        warning=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        add=lambda *args, **kwargs: None,
        remove=lambda *args, **kwargs: None,
        configure=lambda *args, **kwargs: None,
    )
    sys.modules["loguru"] = types.SimpleNamespace(logger=dummy_logger)

try:  # pragma: no cover - attempt to reuse real settings if available
    import config.settings  # type: ignore  # noqa: F401
except ModuleNotFoundError:
    config_module = sys.modules.setdefault("config", types.ModuleType("config"))
    settings_stub = types.SimpleNamespace(
        MAIN_LLM_API_KEY="",
        MAIN_LLM_API_BASE="",
        MAIN_LLM_MODEL="test-model",
        MAIN_LLM_TEMPERATURE=0.7,
        MAIN_LLM_MAX_TOKENS=2000,
        SAFETY_SERVICE_URL="",
        SAFETY_LOCAL_API_URL="",
        SAFETY_SERVICE_TIMEOUT=5.0,
        SAFETY_LOCAL_TIMEOUT=5.0,
        allows_missing_api_keys=lambda: False,
        get_runtime_environment=lambda: "test",
    )
    sys.modules["config.settings"] = types.SimpleNamespace(settings=settings_stub)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from config.settings import Settings
from src.services.llm_adapter import LLMAdapter


class DummyStreamingChoice:
    def __init__(self, content):
        self.delta = type("Delta", (), {"content": content})()


class DummyStreamingChunk:
    def __init__(self, contents):
        self.choices = [DummyStreamingChoice(content) for content in contents]


class DummyAsyncStream:
    def __init__(self, chunks):
        self._iterator = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise StopAsyncIteration from exc


class DummyChatCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        if kwargs.get("stream"):
            return DummyAsyncStream(self._chunks)
        raise AssertionError("Streaming flag was not enabled for streaming response")


class DummyChat:
    def __init__(self, chunks):
        self.completions = DummyChatCompletions(chunks)


class DummyClient:
    def __init__(self, chunks):
        self.chat = DummyChat(chunks)


def test_generate_streaming_response_yields_chunks_and_respects_defaults():
    chunks = [
        DummyStreamingChunk(["Hello"]),
        DummyStreamingChunk([None, " "]),
        DummyStreamingChunk(["world"]),
    ]
    client = DummyClient(chunks)
    service = LLMAdapter(role="external", client=client)

    async def _collect():
        received_parts = []
        async for part in service.generate_streaming_response("hi there", context="ctx"):
            received_parts.append(part)
        return received_parts

    received = asyncio.run(_collect())

    assert received == ["Hello", " ", "world"]

    params = client.chat.completions.last_kwargs
    assert params["temperature"] == service.temperature
    assert params["max_tokens"] == service.max_tokens
    assert params["stream"] is True
    assert params["messages"][0]["role"] == "system"
    assert "ctx" in params["messages"][0]["content"]
    assert params["messages"][1]["content"] == "hi there"


def test_missing_credentials_raise_outside_test_mode(monkeypatch):
    original = os.environ.get("AVI_TEST_MODE")
    try:
        if "AVI_TEST_MODE" in os.environ:
            del os.environ["AVI_TEST_MODE"]
        monkeypatch.setattr(Settings, "allows_missing_api_keys", lambda self: False)
        with pytest.raises(RuntimeError) as exc:
            LLMAdapter(role="external")
        assert "MAIN_LLM_API_KEY" in str(exc.value)
    finally:
        if original is not None:
            os.environ["AVI_TEST_MODE"] = original
        elif "AVI_TEST_MODE" in os.environ:
            del os.environ["AVI_TEST_MODE"]
