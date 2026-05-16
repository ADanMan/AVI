"""
Tests for filter configuration API routes.
"""

import pytest


@pytest.mark.asyncio
async def test_get_filter_config(test_client):
    """Test GET /api/v1/filters/config."""
    response = await test_client.get("/api/v1/filters/config")

    assert response.status_code == 200
    data = response.json()

    assert "filters" in data
    assert isinstance(data["filters"], list)

    # Check filter structure
    if len(data["filters"]) > 0:
        filter_def = data["filters"][0]
        assert "id" in filter_def
        assert "name" in filter_def
        assert "description" in filter_def
        assert "category" in filter_def
        assert "enabled_by_default" in filter_def
        assert "configurable" in filter_def


@pytest.mark.asyncio
async def test_get_filter_config_categories(test_client):
    """Test that filters have valid categories."""
    response = await test_client.get("/api/v1/filters/config")

    assert response.status_code == 200
    data = response.json()

    valid_categories = ["safety", "security", "content", "privacy"]

    for filter_def in data["filters"]:
        assert filter_def["category"] in valid_categories
