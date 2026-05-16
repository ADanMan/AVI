"""
Tests for monitoring API routes.
"""

import pytest


@pytest.mark.asyncio
async def test_get_dashboard_metrics(test_client):
    """Test GET /api/v1/monitoring/metrics."""
    response = await test_client.get("/api/v1/monitoring/metrics")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "safety" in data
    assert "performance" in data
    assert "filter_breakdown" in data
    assert "recent_activity" in data
    assert "timestamp" in data

    # Check safety metrics
    safety = data["safety"]
    assert "total_messages" in safety
    assert "filtered_messages" in safety
    assert "safe_messages" in safety
    assert "filter_rate" in safety
    assert "avg_safety_score" in safety

    # Check performance metrics
    performance = data["performance"]
    assert "avg_response_time_ms" in performance
    assert "p95_response_time_ms" in performance
    assert "p99_response_time_ms" in performance
    assert "requests_per_minute" in performance


@pytest.mark.asyncio
async def test_get_timeseries_data(test_client):
    """Test GET /api/v1/monitoring/timeseries."""
    response = await test_client.get("/api/v1/monitoring/timeseries?hours=24")

    assert response.status_code == 200
    data = response.json()

    assert "safety_scores" in data
    assert "filter_rate" in data
    assert "response_times" in data

    # Each series should be a list of {timestamp, value} points
    for series in [data["safety_scores"], data["filter_rate"], data["response_times"]]:
        assert isinstance(series, list)
        if len(series) > 0:
            point = series[0]
            assert "timestamp" in point
            assert "value" in point


@pytest.mark.asyncio
async def test_get_timeseries_data_different_periods(test_client):
    """Test timeseries with different time periods."""
    for hours in [1, 6, 12, 24, 48]:
        response = await test_client.get(f"/api/v1/monitoring/timeseries?hours={hours}")

        assert response.status_code == 200
        data = response.json()
        assert "safety_scores" in data
