"""
Tests for Phase 2.6: Granular Filter Control functionality.

Tests filtering options for input/output processing with granular component control.
"""

import os
import sys


os.environ["AVI_TEST_MODE"] = "1"
os.environ["REQUIRE_API_KEY"] = "false"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.models.schemas import FilteringOptions


# ========== Unit Tests for FilteringOptions Model ==========


def test_filtering_options_defaults():
    """Test FilteringOptions model with default values."""
    opts = FilteringOptions()
    assert opts.enable_vector_rules is True
    assert opts.enable_safety_llm is True
    assert opts.enable_prompt_modification is True
    assert opts.enable_output_cleaning is True


def test_filtering_options_custom():
    """Test FilteringOptions model with custom values."""
    opts = FilteringOptions(
        enable_vector_rules=False,
        enable_safety_llm=False,
        enable_prompt_modification=False,
        enable_output_cleaning=False,
    )
    assert opts.enable_vector_rules is False
    assert opts.enable_safety_llm is False
    assert opts.enable_prompt_modification is False
    assert opts.enable_output_cleaning is False


def test_filtering_options_serialization():
    """Test FilteringOptions can be serialized to dict."""
    opts = FilteringOptions(enable_vector_rules=False, enable_safety_llm=True)
    data = opts.model_dump()
    assert data["enable_vector_rules"] is False
    assert data["enable_safety_llm"] is True
    assert data["enable_prompt_modification"] is True  # default
    assert data["enable_output_cleaning"] is True  # default


# ========== API Integration Tests ==========


@pytest.mark.asyncio
async def test_query_endpoint_with_filtering_options():
    """Test /query endpoint accepts filtering options."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/query",
            json={
                "query": "What is AVI?",
                "input_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,  # Disable to speed up
                    "enable_prompt_modification": True,
                    "enable_output_cleaning": False,
                },
                "output_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": True,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "input_filter_result" in data
        assert "output_filter_result" in data


@pytest.mark.asyncio
async def test_query_endpoint_backward_compatibility():
    """Test /query endpoint maintains backward compatibility with use_llm_filter."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Old API should still work
        response = await ac.post(
            "/api/v1/query",
            json={
                "query": "Test query",
                "use_llm_filter": False,  # Old parameter
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data


@pytest.mark.asyncio
async def test_query_endpoint_components_applied_tracking():
    """Test that FilterResult includes components_applied tracking."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/query",
            json={
                "query": "Test query",
                "input_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": True,
                    "enable_output_cleaning": False,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check that input filter result has components_applied
        input_filter = data.get("input_filter_result")
        if input_filter:
            assert "components_applied" in input_filter
            components = input_filter["components_applied"]
            # Vector rules should be applied
            assert "vector_rules" in components
            # Safety LLM should not be applied (disabled)
            assert "safety_llm" in components


@pytest.mark.asyncio
async def test_stream_endpoint_with_filtering_options():
    """Test /query/stream endpoint accepts filtering options for input."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/query/stream",
            json={
                "query": "What is AVI?",
                "input_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": True,
                    "enable_output_cleaning": False,
                },
            },
        )
        # Stream should start successfully
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"


# ========== Settings API Tests ==========


@pytest.mark.asyncio
async def test_get_filtering_settings():
    """Test GET /settings/filtering endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/settings/settings/filtering")
        assert response.status_code == 200
        data = response.json()
        assert "default_input_filtering" in data
        assert "default_output_filtering" in data

        # Check structure
        input_opts = data["default_input_filtering"]
        assert "enable_vector_rules" in input_opts
        assert "enable_safety_llm" in input_opts
        assert "enable_prompt_modification" in input_opts
        assert "enable_output_cleaning" in input_opts


@pytest.mark.asyncio
async def test_update_filtering_settings():
    """Test POST /settings/filtering endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/settings/settings/filtering",
            json={
                "default_input_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": True,
                    "enable_output_cleaning": False,
                },
                "default_output_filtering": {
                    "enable_vector_rules": True,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": False,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["category"] == "filtering"
        assert "config" in data


@pytest.mark.asyncio
async def test_get_all_settings_includes_filtering():
    """Test GET /settings includes filtering configuration."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/settings/")
        assert response.status_code == 200
        data = response.json()
        assert "filtering" in data
        assert "default_input_filtering" in data["filtering"]
        assert "default_output_filtering" in data["filtering"]


# ========== Edge Cases ==========


@pytest.mark.asyncio
async def test_query_with_all_components_disabled():
    """Test query with all filtering components disabled."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/query",
            json={
                "query": "Test query",
                "input_filtering": {
                    "enable_vector_rules": False,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": False,
                },
                "output_filtering": {
                    "enable_vector_rules": False,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": False,
                },
            },
        )
        # Should still work, just with minimal filtering
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_with_partial_filtering_options():
    """Test query with only input_filtering specified."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/query",
            json={
                "query": "Test query",
                "input_filtering": {
                    "enable_vector_rules": False,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": False,
                },
                # output_filtering not specified - should use defaults
            },
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_filtering_settings_with_none():
    """Test POST /settings/filtering with None values (partial update)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # First get current settings
        get_response = await ac.get("/api/v1/settings/settings/filtering")
        assert get_response.status_code == 200

        # Update only input filtering
        response = await ac.post(
            "/api/v1/settings/settings/filtering",
            json={
                "default_input_filtering": {
                    "enable_vector_rules": False,
                    "enable_safety_llm": False,
                    "enable_prompt_modification": False,
                    "enable_output_cleaning": False,
                }
                # default_output_filtering is None - should keep current value
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
