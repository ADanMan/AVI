import os
import sys


# Устанавливаем переменную окружения AVI_TEST_MODE=1 для остальных тестов, чтобы не влияли на текущие
os.environ["AVI_TEST_MODE"] = "1"
os.environ["REQUIRE_API_KEY"] = "false"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_query_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/query", json={"query": "What is the capital of France?"})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "input_filter_result" in data
        assert "output_filter_result" in data


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_reindex_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/reindex")
        # 409 if indexing is disabled, 200/202 if enabled
        assert response.status_code in (200, 202, 409)


@pytest.mark.asyncio
async def test_safety_status_reports_mode():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/llm/safety/status")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "active_mode" in data
