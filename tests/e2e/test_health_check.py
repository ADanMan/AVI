"""
E2E tests for health check endpoints
"""


class TestHealthCheck:
    """Test health check and system status endpoints"""

    def test_health_endpoint_returns_200(self, api_client, api_base_url):
        """Test that /health endpoint returns 200 OK"""
        response = api_client.get(f"{api_base_url}/health")

        assert response.status_code == 200, "Health check should return 200"
        data = response.json()
        assert data.get("status") in ["healthy", "ok"], "Health status should be healthy/ok"

    def test_health_endpoint_structure(self, api_client, api_base_url):
        """Test health endpoint returns proper structure"""
        response = api_client.get(f"{api_base_url}/health")
        data = response.json()

        assert "status" in data, "Health response should contain status"
        # May also include: timestamp, version, services, etc.

    def test_metrics_endpoint_exists(self, api_client, api_base_url):
        """Test that Prometheus metrics endpoint exists"""
        response = api_client.get(f"{api_base_url}/metrics")

        # Metrics endpoint returns 200 and plain text
        assert response.status_code in [200, 404], "Metrics endpoint should exist or be disabled"

        if response.status_code == 200:
            # Should be Prometheus format
            assert (
                "# HELP" in response.text or "# TYPE" in response.text
            ), "Metrics should be in Prometheus format"
