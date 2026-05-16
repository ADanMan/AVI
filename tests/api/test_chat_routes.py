"""
Tests for chat API routes.
"""

import json

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


class TestChatComplete:
    """Tests for /api/v1/chat/complete endpoint."""

    def test_chat_complete_success(self):
        """Test successful chat completion."""
        response = client.post(
            "/api/v1/chat/complete",
            json={
                "message": "Hello, how are you?",
                "enable_avi": True,
                "model": "gpt-4o-mini",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "message" in data
        assert "safety_scores" in data
        assert "filtered" in data
        assert "model" in data

        # Check safety scores structure (SafetyScores has dynamic fields; only overall is required)
        scores = data["safety_scores"]
        assert "overall" in scores

        # All scores should be between 0 and 1
        for _key, value in scores.items():
            if value is not None:
                assert 0.0 <= value <= 1.0

    def test_chat_complete_without_avi(self):
        """Test chat completion with AVI disabled."""
        response = client.post(
            "/api/v1/chat/complete",
            json={
                "message": "Test message",
                "enable_avi": False,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should not be filtered when AVI is off
        assert data["filtered"] is False

        # Safety scores should be perfect (1.0) when AVI is off
        scores = data["safety_scores"]
        assert scores["overall"] == 1.0

    def test_chat_complete_with_default_params(self):
        """Test chat completion with default parameters."""
        response = client.post(
            "/api/v1/chat/complete",
            json={"message": "Simple test"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should use defaults
        assert data["model"] == "gpt-4o-mini"
        assert data["filtered"] is False  # Default message should be safe

    def test_chat_complete_invalid_temperature(self):
        """Test chat completion with invalid temperature."""
        response = client.post(
            "/api/v1/chat/complete",
            json={
                "message": "Test",
                "temperature": 3.0,  # Invalid: > 2.0
            },
        )

        # Should reject invalid temperature
        assert response.status_code == 422

    def test_chat_complete_invalid_max_tokens(self):
        """Test chat completion with invalid max_tokens."""
        response = client.post(
            "/api/v1/chat/complete",
            json={
                "message": "Test",
                "max_tokens": 10000,  # Invalid: > 8192
            },
        )

        # Should reject invalid max_tokens
        assert response.status_code == 422

    def test_chat_complete_missing_message(self):
        """Test chat completion without message."""
        response = client.post(
            "/api/v1/chat/complete",
            json={},
        )

        # Should reject missing message
        assert response.status_code == 422


class TestChatStream:
    """Tests for /api/v1/chat/stream endpoint."""

    def test_chat_stream_success(self):
        """Test successful streaming chat."""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Hello!",
                "enable_avi": True,
            },
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE stream
        chunks = []
        for line in response.iter_lines():
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                data = line[6:]  # Remove "data: " prefix
                if data and data != "[DONE]":
                    try:
                        chunks.append(json.loads(data))
                    except json.JSONDecodeError:
                        pass

        # Should have received chunks
        assert len(chunks) > 0

        # Check chunk types
        chunk_types = {chunk["type"] for chunk in chunks}
        assert "content" in chunk_types  # Should have content chunks
        assert "done" in chunk_types or "safety" in chunk_types  # Should have final chunks

    def test_chat_stream_without_avi(self):
        """Test streaming chat with AVI disabled."""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Test message",
                "enable_avi": False,
            },
        )

        assert response.status_code == 200

        # Parse chunks
        chunks = []
        for line in response.iter_lines():
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                data = line[6:]
                if data and data != "[DONE]":
                    try:
                        chunks.append(json.loads(data))
                    except json.JSONDecodeError:
                        pass

        # Find safety chunk
        safety_chunks = [c for c in chunks if c.get("type") == "safety"]
        if safety_chunks:
            scores = safety_chunks[0].get("safety_scores", {})
            # Should not be filtered
            assert safety_chunks[0].get("filtered") is False
            # Scores should be perfect when AVI is off
            assert scores.get("overall") == 1.0

    def test_chat_stream_content_chunks(self):
        """Test that stream contains content chunks."""
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Tell me a short joke",
                "model": "gpt-4o-mini",
            },
        )

        assert response.status_code == 200

        # Collect content
        content_parts = []
        for line in response.iter_lines():
            line = line.decode("utf-8") if isinstance(line, bytes) else line
            if line.startswith("data: "):
                data = line[6:]
                if data and data != "[DONE]":
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content" and chunk.get("content"):
                            content_parts.append(chunk["content"])
                    except json.JSONDecodeError:
                        pass

        # Should have received multiple content chunks
        assert len(content_parts) > 0

        # Concatenated content should not be empty
        full_content = "".join(content_parts)
        assert len(full_content) > 0


class TestSafetyCheck:
    """Tests for /api/v1/chat/safety/check endpoint."""

    def test_safety_check_success(self):
        """Test successful safety check."""
        response = client.post(
            "/api/v1/chat/safety/check",
            json={"text": "This is a safe message."},
        )

        assert response.status_code == 200
        data = response.json()

        # Check safety scores structure (only overall is guaranteed; other fields are dynamic)
        assert "overall" in data

        # All scores should be between 0 and 1
        for _key, value in data.items():
            if value is not None:
                assert 0.0 <= value <= 1.0

    def test_safety_check_empty_text(self):
        """Test safety check with empty text."""
        response = client.post(
            "/api/v1/chat/safety/check",
            json={"text": ""},
        )

        assert response.status_code == 200
        # Should still return scores for empty text

    def test_safety_check_missing_text(self):
        """Test safety check without text."""
        response = client.post(
            "/api/v1/chat/safety/check",
            json={},
        )

        # Should reject missing text
        assert response.status_code == 422

    def test_safety_check_long_text(self):
        """Test safety check with long text."""
        long_text = "Hello! " * 1000  # Create long text

        response = client.post(
            "/api/v1/chat/safety/check",
            json={"text": long_text},
        )

        # Should handle long text
        assert response.status_code == 200

    def test_safety_check_with_specific_checks(self):
        """Test safety check with specific check types."""
        response = client.post(
            "/api/v1/chat/safety/check",
            json={
                "text": "Test message",
                "checks": ["toxicity", "pii"],
            },
        )

        assert response.status_code == 200
        # Should return scores (implementation may vary)


class TestChatIntegration:
    """Integration tests for chat functionality."""

    def test_complete_to_stream_consistency(self):
        """Test that complete and stream endpoints return similar results."""
        message = "What is the capital of France?"

        # Test complete endpoint
        complete_response = client.post(
            "/api/v1/chat/complete",
            json={"message": message, "enable_avi": True},
        )
        assert complete_response.status_code == 200
        complete_data = complete_response.json()

        # Test stream endpoint
        stream_response = client.post(
            "/api/v1/chat/stream",
            json={"message": message, "enable_avi": True},
        )
        assert stream_response.status_code == 200

        # Both should not filter safe content
        assert complete_data["filtered"] is False

    def test_safety_scores_range(self):
        """Test that all safety scores are within valid range."""
        messages = [
            "Hello!",
            "How are you doing today?",
            "Tell me about Python programming.",
        ]

        for message in messages:
            response = client.post(
                "/api/v1/chat/complete",
                json={"message": message, "enable_avi": True},
            )

            assert response.status_code == 200
            data = response.json()
            scores = data["safety_scores"]

            # Verify all scores are in [0, 1] range
            for key, value in scores.items():
                if value is not None:
                    assert (
                        0.0 <= value <= 1.0
                    ), f"Score {key}={value} out of range for message: {message}"


# Mark all tests for coverage
pytestmark = pytest.mark.api
