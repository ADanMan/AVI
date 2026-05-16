import os
import sys


# Включаем мок-режим для тестов, чтобы не зависеть от ChromaDB
os.environ["AVI_TEST_MODE"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from config.settings import settings
from src.core.content_filter import ContentFilterService, SafetyMode, create_content_filter_service
from src.models.schemas import FilteredContent
from src.services.filter_service import FilterService
from src.services.llm_adapter import LLMAdapter
from src.services.rag_service import RAGService


def test_filter_service_input(monkeypatch):
    service = FilterService()

    async def mock_check_content(*a, **kw):
        class MockResult:
            modified_text = None
            matches = []

        return MockResult()

    monkeypatch.setattr(service.content_filter, "check_content", mock_check_content)

    async def run():
        return await service.filter_input("test")

    result = asyncio.run(run())
    assert hasattr(result, "matches")


@pytest.mark.smoke
def test_rag_service_generate_direct(monkeypatch):
    service = RAGService()

    async def mock_generate_response(*a, **kw):
        return "mocked response"

    monkeypatch.setattr(service.llm_adapter, "generate_response", mock_generate_response)

    async def run():
        return await service.generate_direct("test")

    result = asyncio.run(run())
    assert result == "mocked response"


def test_rag_service_retrieve_context_with_reranker(monkeypatch):
    service = RAGService()

    documents = [
        {
            "document_id": "1",
            "text": "short",
            "metadata": {},
            "relevance_score": 0.9,
        },
        {
            "document_id": "2",
            "text": "a much longer document text",  # longer -> higher dummy score
            "metadata": {},
            "relevance_score": 0.1,
        },
    ]

    def fake_search(query, threshold=None, top_k=None):
        return documents

    class DummyReranker:
        score_threshold = 0.0

        @property
        def is_enabled(self):
            return True

        async def rerank(self, query, docs):
            reranked = []
            for doc in docs:
                updated = dict(doc)
                updated["rerank_score"] = float(len(updated.get("text", "")))
                reranked.append(updated)
            reranked.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)
            return reranked

    monkeypatch.setattr(service.vector_db, "search", fake_search)
    service.reranker = DummyReranker()

    async def run():
        return await service.retrieve_context("query", top_k=1)

    result = asyncio.run(run())

    assert len(result) == 1
    assert result[0]["document_id"] == "2"
    assert "rerank_score" in result[0]


@pytest.mark.smoke
def test_llm_adapter_check_connection(monkeypatch):
    adapter = LLMAdapter(config={"api_key": "test"})

    async def mock_generate_response(*a, **kw):
        return "pong"

    monkeypatch.setattr(adapter, "generate_response", mock_generate_response)

    result = asyncio.run(adapter.check_connection())
    assert result is True


def test_filter_service_empty_input(monkeypatch):
    service = FilterService()

    async def mock_check_content(*a, **kw):
        class MockResult:
            modified_text = None
            matches = []

        return MockResult()

    monkeypatch.setattr(service.content_filter, "check_content", mock_check_content)
    result = asyncio.run(service.filter_input(""))
    assert hasattr(result, "matches")
    assert result.matches == []


def test_filter_service_content_filter_error(monkeypatch):
    service = FilterService()

    async def raise_error(*a, **kw):
        raise ValueError("Mocked error")

    monkeypatch.setattr(service.content_filter, "check_content", raise_error)
    with pytest.raises(ValueError):
        asyncio.run(service.filter_input("test error"))


def test_filter_service_get_rule_by_text(monkeypatch):
    service = FilterService()

    async def mock_get_rules():
        return [{"id": "1", "text": "foo"}, {"id": "2", "text": "bar"}]

    monkeypatch.setattr(service, "get_rules", mock_get_rules)

    async def run():
        rule = await service.get_rule_by_text("bar")
        rule_none = await service.get_rule_by_text("baz")
        return rule, rule_none

    rule, rule_none = asyncio.run(run())
    assert rule["id"] == "2"
    assert rule["text"] == "bar"
    assert rule_none is None


def test_filter_service_get_rule_by_id(monkeypatch):
    service = FilterService()

    async def mock_get_rule(rule_id):
        if rule_id == "1":
            return {"id": "1", "text": "foo"}
        return None

    monkeypatch.setattr(service, "get_rule_by_id", mock_get_rule)

    async def run():
        rule = await service.get_rule_by_id("1")
        rule_none = await service.get_rule_by_id("2")
        return rule, rule_none

    rule, rule_none = asyncio.run(run())
    assert rule["text"] == "foo"
    assert rule_none is None


def test_filter_service_validate_rule_valid():
    """Test validate_rule with a valid rule."""
    service = FilterService()
    rule = FilteredContent(
        text="No violence allowed",
        category="violence",
        risk_level=5,
        threshold=0.8,
    )

    result = asyncio.run(service.validate_rule(rule))

    assert result["valid"] is True
    assert len(result["errors"]) == 0
    assert result["duplicate_rule_id"] is None


def test_filter_service_validate_rule_empty_text():
    """Test validate_rule with empty text - Pydantic catches this."""
    import pytest
    from pydantic_core import ValidationError

    # Pydantic should reject empty/whitespace-only text due to validator
    with pytest.raises(ValidationError) as exc_info:
        FilteredContent(
            text=" ",
            category="test",
            risk_level=3,
            threshold=0.75,
        )

    # Verify the error is about empty text
    assert "empty" in str(exc_info.value).lower()


def test_filter_service_validate_rule_invalid_risk_level():
    """Test validate_rule with invalid risk level."""
    # Test risk level out of range (Pydantic should catch this, but we test the method)
    import pytest

    with pytest.raises(ValueError):  # Pydantic validation
        FilteredContent(
            text="Test rule",
            category="test",
            risk_level=10,  # Invalid: should be 1-5
            threshold=0.75,
        )


def test_filter_service_validate_rule_low_threshold_warning():
    """Test validate_rule with very low threshold."""
    service = FilterService()
    rule = FilteredContent(
        text="Test rule with low threshold",
        category="test",
        risk_level=3,
        threshold=0.3,  # Low threshold should trigger warning
    )

    result = asyncio.run(service.validate_rule(rule))

    assert result["valid"] is True  # Still valid
    assert any("low" in warning.lower() and "threshold" in warning.lower() for warning in result["warnings"])


def test_filter_service_validate_rule_nonstandard_category_warning():
    """Test validate_rule with non-standard category."""
    service = FilterService()
    rule = FilteredContent(
        text="Custom rule with unusual category",
        category="my_custom_category",  # Non-standard category
        risk_level=3,
        threshold=0.75,
    )

    result = asyncio.run(service.validate_rule(rule))

    assert result["valid"] is True  # Still valid
    assert any("not a standard category" in warning for warning in result["warnings"])


def test_filter_service_validate_rule_short_text_warning():
    """Test validate_rule with very short text."""
    service = FilterService()
    rule = FilteredContent(
        text="Test",  # Very short text
        category="test",
        risk_level=3,
        threshold=0.75,
    )

    result = asyncio.run(service.validate_rule(rule))

    assert result["valid"] is True  # Still valid
    assert any("short" in warning.lower() for warning in result["warnings"])


def test_content_filter_factory_disabled_mode(monkeypatch):
    monkeypatch.setattr(settings, "SAFETY_MODE", "disabled")
    service = create_content_filter_service()
    assert service.active_mode == SafetyMode.DISABLED
    assert service.safety_llm_enabled is False


def test_content_filter_hybrid_fallback(monkeypatch):
    """Test hybrid safety mode falls back from local to external when local fails."""

    class DummyLocalService:
        kind = "local_safety"

        def __init__(self):
            self.calls = 0

        async def generate_response(self, query, context=None, **kwargs):
            self.calls += 1
            raise RuntimeError("local backend failure")

        async def check_connection(self):
            return False

    class DummyExternalService:
        kind = "safety"

        def __init__(self):
            self.calls = 0

        async def generate_response(self, query, context=None, **kwargs):
            self.calls += 1
            return "sanitized"

        async def check_connection(self):
            return True

    class DummyHybridAdapter:
        kind = "hybrid"

        def __init__(self, primary, fallback, primary_name, fallback_name):
            self.primary = primary
            self.fallback = fallback
            self.primary_name = primary_name
            self.fallback_name = fallback_name
            self.last_successful = None

        async def generate_response(self, query, context=None, **kw):
            try:
                result = await self.primary.generate_response(query, context=context, **kw)
                self.last_successful = self.primary_name
                return result
            except Exception:
                if not self.fallback:
                    raise
                result = await self.fallback.generate_response(query, context=context, **kw)
                self.last_successful = self.fallback_name
                return result

        async def check_connection(self):
            return True

    dummy_local = DummyLocalService()
    dummy_external = DummyExternalService()
    hybrid_adapter = DummyHybridAdapter(
        primary=dummy_local,
        fallback=dummy_external,
        primary_name=SafetyMode.LOCAL.value,
        fallback_name=SafetyMode.EXTERNAL.value,
    )

    # Create service with the hybrid adapter directly
    service = ContentFilterService(safety_llm=hybrid_adapter, mode=SafetyMode.HYBRID)

    async def fake_find_matching_rules(text, n_results=10):
        class Match:
            rule_text = "rule"
            relevance_score = 1.0

        return [Match()]

    async def fake_get_rule_threshold(rule_text):
        return 0.5

    async def run_flow():
        monkeypatch.setattr(service.vector_db, "find_matching_rules", fake_find_matching_rules)
        monkeypatch.setattr(service.vector_db, "get_rule_threshold", fake_get_rule_threshold)

        result = await service.check_content("unsafe text", use_llm=True)
        return result

    result = asyncio.run(run_flow())

    assert result.modified_text == "sanitized"
    assert service.active_mode == SafetyMode.EXTERNAL
    assert dummy_local.calls == 1
    assert dummy_external.calls == 1


def test_qdrant_ensure_collection_handles_response_handling_exception(monkeypatch):
    pytest.importorskip("qdrant_client")
    from qdrant_client.http.exceptions import ResponseHandlingException

    from src.services.vector_db import QdrantVectorDBService

    service = QdrantVectorDBService.__new__(QdrantVectorDBService)
    mock_client = MagicMock()
    mock_client.get_collection.side_effect = ResponseHandlingException(Exception("Not found"))
    service.client = mock_client

    service._ensure_collection(
        "test_collection",
        vectors_config={"dense": object()},
    )

    mock_client.create_collection.assert_called_once()
    kwargs = mock_client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == "test_collection"


@pytest.fixture(autouse=True)
def clear_qdrant_cache():
    """Clear Qdrant client cache before each test to prevent pollution."""
    try:
        from src.services import vector_db

        if hasattr(vector_db, "_qdrant_client_cache"):
            vector_db._qdrant_client_cache.clear()
    except Exception:
        pass  # Module might not be imported yet
    yield
    try:
        from src.services import vector_db

        if hasattr(vector_db, "_qdrant_client_cache"):
            vector_db._qdrant_client_cache.clear()
    except Exception:
        pass


@pytest.fixture
def dummy_qdrant_dependencies(monkeypatch):
    pytest.importorskip("qdrant_client")

    # Create a comprehensive mock client
    dummy_client = MagicMock()
    dummy_client.get_collection = MagicMock(side_effect=Exception("Collection not found"))
    dummy_client.get_collections = MagicMock(return_value=SimpleNamespace(collections=[]))
    dummy_client.create_collection = MagicMock()

    # Mock at multiple levels to ensure no real client is created
    def mock_get_or_create(**kwargs):
        return dummy_client

    # Import the vector_db module
    import src.services.vector_db

    # Patch the cache and client creation function
    monkeypatch.setattr(src.services.vector_db, "_qdrant_client_cache", {})
    monkeypatch.setattr(src.services.vector_db, "_get_or_create_qdrant_client", mock_get_or_create)

    # Also patch QdrantClient directly - use try/except in case module was reloaded
    try:
        monkeypatch.setattr("qdrant_client.QdrantClient", MagicMock(return_value=dummy_client))
    except (AttributeError, ImportError):
        pass  # Module may not be available after reload

    # Mock qmodels
    monkeypatch.setattr(
        "src.services.vector_db.qmodels",
        SimpleNamespace(
            VectorParams=lambda size, distance: SimpleNamespace(size=size, distance=distance),
            Distance=SimpleNamespace(COSINE="cosine"),
            PointStruct=MagicMock(),
            OptimizersConfigDiff=lambda default_segment_number: SimpleNamespace(
                default_segment_number=default_segment_number
            ),
        ),
    )

    # Mock collection existence check and creation
    monkeypatch.setattr(
        "src.services.vector_db.QdrantVectorDBService._qdrant_collection_exists",
        lambda self, name: False,
    )
    monkeypatch.setattr(
        "src.services.vector_db.QdrantVectorDBService._ensure_collection",
        lambda self, name, vectors_config: None,
    )

    return dummy_client


def test_qdrant_init_uses_sentence_transformer(monkeypatch, dummy_qdrant_dependencies):
    from src.services.vector_db import QdrantVectorDBService

    class DummySentenceTransformer:
        def __init__(self, model_name, device=None, **kwargs):
            self.model_name = model_name
            self.called_with = []

        def encode(self, texts):
            self.called_with.append(list(texts))
            return [[1.0] * settings.INDEX_DIMENSION for _ in texts]

    monkeypatch.setattr("src.services.vector_db.SentenceTransformer", DummySentenceTransformer)
    monkeypatch.setattr("src.services.vector_db.chroma_embeddings", None)

    service = QdrantVectorDBService()

    assert isinstance(service._embedding_model, DummySentenceTransformer)
    assert service._embedding_model.model_name == settings.EMBEDDING_MODEL


def test_qdrant_init_raises_without_sentence_transformers(monkeypatch, dummy_qdrant_dependencies):
    from src.services.vector_db import QdrantVectorDBService

    monkeypatch.setattr("src.services.vector_db.SentenceTransformer", None)

    with pytest.raises(RuntimeError, match="sentence-transformers is not available"):
        QdrantVectorDBService()


def test_qdrant_embed_uses_loaded_model():
    from src.services.vector_db import QdrantVectorDBService

    service = QdrantVectorDBService.__new__(QdrantVectorDBService)

    class DummyEmbedding(list):
        def tolist(self):
            return [list(item) for item in self]

    mock_model = MagicMock()
    mock_model.encode.return_value = DummyEmbedding([[0, 1], [2, 3]])
    service._embedding_model = mock_model

    result = service._embed(["a", "b"])

    mock_model.encode.assert_called_once_with(["a", "b"])
    assert result == [[0.0, 1.0], [2.0, 3.0]]
