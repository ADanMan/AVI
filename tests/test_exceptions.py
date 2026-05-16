"""Tests for custom exceptions."""

import pytest

from src.utils.exceptions import (
    AVIException,
    CacheError,
    ConfigurationError,
    ContentFilterError,
    IndexingError,
    LLMError,
    RAGError,
    ValidationError,
    VectorDBError,
)


def test_avi_exception_basic():
    """Test basic AVIException creation."""
    exc = AVIException("Test error")
    assert str(exc) == "Test error"
    assert exc.message == "Test error"
    assert exc.details == {}


def test_avi_exception_with_details():
    """Test AVIException with details."""
    exc = AVIException("Test error", {"key": "value", "count": 42})
    assert exc.message == "Test error"
    assert exc.details == {"key": "value", "count": 42}
    assert "key=value" in str(exc)
    assert "count=42" in str(exc)


def test_avi_exception_inheritance():
    """Test that all exceptions inherit from AVIException."""
    exceptions = [
        ConfigurationError,
        VectorDBError,
        LLMError,
        ContentFilterError,
        RAGError,
        IndexingError,
        CacheError,
        ValidationError,
    ]

    for exc_class in exceptions:
        exc = exc_class("test message")
        assert isinstance(exc, AVIException)
        assert isinstance(exc, Exception)


def test_configuration_error():
    """Test ConfigurationError."""
    exc = ConfigurationError("Invalid config", {"field": "API_KEY"})
    assert str(exc) == "Invalid config (field=API_KEY)"
    assert exc.message == "Invalid config"


def test_vector_db_error():
    """Test VectorDBError."""
    exc = VectorDBError("Connection failed", {"host": "localhost", "port": 6333})
    assert "Connection failed" in str(exc)
    assert "host=localhost" in str(exc)


def test_llm_error():
    """Test LLMError."""
    exc = LLMError("Rate limit exceeded", {"retry_after": 60})
    assert "Rate limit exceeded" in str(exc)
    assert "retry_after=60" in str(exc)


def test_content_filter_error():
    """Test ContentFilterError."""
    exc = ContentFilterError("Filter rule not found", {"rule_id": "123"})
    assert "Filter rule not found" in str(exc)


def test_rag_error():
    """Test RAGError."""
    exc = RAGError("Document retrieval failed")
    assert str(exc) == "Document retrieval failed"


def test_indexing_error():
    """Test IndexingError."""
    exc = IndexingError("Failed to index document", {"doc_id": "doc_123"})
    assert "Failed to index document" in str(exc)


def test_cache_error():
    """Test CacheError."""
    exc = CacheError("Redis connection lost")
    assert str(exc) == "Redis connection lost"


def test_validation_error():
    """Test ValidationError."""
    exc = ValidationError("Invalid query format", {"field": "query"})
    assert "Invalid query format" in str(exc)


def test_exception_raising():
    """Test that exceptions can be raised and caught."""
    with pytest.raises(ConfigurationError) as exc_info:
        raise ConfigurationError("Test config error")

    assert "Test config error" in str(exc_info.value)


def test_exception_catching_as_base():
    """Test that specific exceptions can be caught as AVIException."""
    with pytest.raises(AVIException):
        raise LLMError("Test LLM error")


def test_exception_catching_as_exception():
    """Test that AVIException can be caught as Exception."""
    with pytest.raises(Exception):
        raise VectorDBError("Test VectorDB error")


def test_exception_details_empty():
    """Test exception with None details."""
    exc = AVIException("Test", None)
    assert exc.details == {}
    assert str(exc) == "Test"


def test_exception_details_types():
    """Test exception with different detail types."""
    exc = AVIException(
        "Complex error",
        {
            "string": "value",
            "number": 123,
            "float": 45.67,
            "bool": True,
            "list": [1, 2, 3],
        },
    )
    assert exc.details["string"] == "value"
    assert exc.details["number"] == 123
    assert exc.details["float"] == 45.67
    assert exc.details["bool"] is True
    assert exc.details["list"] == [1, 2, 3]


def test_all_exceptions_exported():
    """Test that all exceptions are in __all__."""
    from src.utils import exceptions

    expected = [
        "AVIException",
        "ConfigurationError",
        "VectorDBError",
        "LLMError",
        "ContentFilterError",
        "RAGError",
        "IndexingError",
        "CacheError",
        "ValidationError",
    ]

    for name in expected:
        assert name in exceptions.__all__
        assert hasattr(exceptions, name)
