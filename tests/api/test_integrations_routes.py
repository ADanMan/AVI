"""
Tests for integrations API routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.integrations_routes import check_grafana, check_mlflow, check_prometheus


@pytest.mark.asyncio
async def test_check_prometheus_available():
    """Test Prometheus health check when service is available."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "data": {"version": "2.45.0"}}

    with patch("src.api.integrations_routes.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await check_prometheus()

        assert result.available is True
        assert result.url == "http://localhost:9090"
        assert result.version == "2.45.0"
        assert result.error is None


@pytest.mark.asyncio
async def test_check_prometheus_unavailable():
    """Test Prometheus health check when service is unavailable."""
    with patch("src.api.integrations_routes.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        result = await check_prometheus()

        assert result.available is False
        assert result.error == "Prometheus not reachable"


@pytest.mark.asyncio
async def test_check_mlflow_available():
    """Test MLflow health check when service is available."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": "2.8.0"}

    with patch("src.api.integrations_routes.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await check_mlflow()

        assert result.available is True
        assert result.url == "http://localhost:5000"
        assert result.version == "2.8.0"


@pytest.mark.asyncio
async def test_check_grafana_available():
    """Test Grafana health check when service is available."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"version": "10.0.0"}

    with patch("src.api.integrations_routes.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

        result = await check_grafana()

        assert result.available is True
        assert result.url == "http://localhost:3001"


@pytest.mark.asyncio
async def test_get_integrations_status(test_client):
    """Test GET /api/v1/integrations/status endpoint."""
    response = await test_client.get("/api/v1/integrations/status")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "prometheus" in data
    assert "mlflow" in data
    assert "grafana" in data

    # Each service should have required fields
    for service in [data["prometheus"], data["mlflow"], data["grafana"]]:
        assert "available" in service
        assert isinstance(service["available"], bool)
