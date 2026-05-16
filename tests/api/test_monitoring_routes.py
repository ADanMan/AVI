"""
Tests for monitoring API routes.

Note: Dedicated /monitoring/metrics and /monitoring/timeseries endpoints are not
implemented in this version; monitoring data is exposed via /api/v1/settings/monitoring
and Prometheus /metrics. These tests are skipped until those routes are added.
"""

import pytest


@pytest.mark.skip(reason="/api/v1/monitoring/metrics endpoint not implemented in this version")
@pytest.mark.asyncio
async def test_get_dashboard_metrics(test_client):
    """Test GET /api/v1/monitoring/metrics."""
    response = await test_client.get("/api/v1/monitoring/metrics")

    assert response.status_code == 200
    data = response.json()

    assert "safety" in data
    assert "performance" in data
    assert "filter_breakdown" in data
    assert "recent_activity" in data
    assert "timestamp" in data


@pytest.mark.skip(reason="/api/v1/monitoring/timeseries endpoint not implemented in this version")
@pytest.mark.asyncio
async def test_get_timeseries_data(test_client):
    """Test GET /api/v1/monitoring/timeseries."""
    response = await test_client.get("/api/v1/monitoring/timeseries?hours=24")

    assert response.status_code == 200
    data = response.json()

    assert "safety_scores" in data
    assert "filter_rate" in data
    assert "response_times" in data


@pytest.mark.skip(reason="/api/v1/monitoring/timeseries endpoint not implemented in this version")
@pytest.mark.asyncio
async def test_get_timeseries_data_different_periods(test_client):
    """Test timeseries with different time periods."""
    for hours in [1, 6, 12, 24, 48]:
        response = await test_client.get(f"/api/v1/monitoring/timeseries?hours={hours}")

        assert response.status_code == 200
        data = response.json()
        assert "safety_scores" in data
