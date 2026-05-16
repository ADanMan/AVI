"""Custom exceptions for consistent error handling across the AVI system."""

from __future__ import annotations

from typing import Any


class AVIException(Exception):
    """
    Base exception for all AVI system errors.

    All custom exceptions in the AVI system should inherit from this class
    to enable consistent error handling and logging.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        """
        Initialize AVI exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of the exception."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigurationError(AVIException):
    """
    Raised when configuration is invalid or missing.

    Examples:
        - Missing required environment variables
        - Invalid configuration values
        - Conflicting settings
    """


class VectorDBError(AVIException):
    """
    Raised when vector database operations fail.

    Examples:
        - Failed to connect to Qdrant/Chroma
        - Collection doesn't exist
        - Index operation failed
    """


class LLMError(AVIException):
    """
    Raised when LLM operations fail.

    Examples:
        - API key invalid
        - Rate limit exceeded
        - Model not available
        - Empty response from LLM
    """


class ContentFilterError(AVIException):
    """
    Raised when content filtering fails.

    Examples:
        - Filter rules not loaded
        - Rule validation failed
        - Safety check timeout
    """


class RAGError(AVIException):
    """
    Raised when RAG system operations fail.

    Examples:
        - Document retrieval failed
        - Context generation failed
        - Reranking failed
    """


class IndexingError(AVIException):
    """
    Raised when document indexing fails.

    Examples:
        - Failed to parse document
        - Embedding generation failed
        - Batch indexing failed
    """


class CacheError(AVIException):
    """
    Raised when cache operations fail.

    Examples:
        - Redis connection failed
        - Cache key not found
        - Serialization error
    """


class ValidationError(AVIException):
    """
    Raised when input validation fails.

    Examples:
        - Invalid query format
        - Missing required fields
        - Data type mismatch
    """


__all__ = [
    "AVIException",
    "CacheError",
    "ConfigurationError",
    "ContentFilterError",
    "IndexingError",
    "LLMError",
    "RAGError",
    "ValidationError",
    "VectorDBError",
]
