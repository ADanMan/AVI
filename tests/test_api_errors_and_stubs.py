import os
import sys

# Устанавливаем переменную окружения AVI_TEST_MODE=1 для остальных тестов, чтобы не влияли на текущие
os.environ["AVI_TEST_MODE"] = "1"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
@pytest.mark.skip(reason="Endpoints removed from API - test outdated")
async def test_not_implemented_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Batch link endpoint (правильный payload для RuleLinkRequest)
        resp = await ac.post(
            "/rag/rules/rule1/documents",
            json={"rule_id": "rule1", "document_ids": ["doc1"], "is_approved": True},
        )
        assert resp.status_code == 501
        assert "Not implemented" in resp.text or "not implemented" in resp.text
        # Approve endpoint
        resp2 = await ac.patch("/rag/rules/rule1/documents/doc1/approve")
        assert resp2.status_code == 501
        # Dynamic LLM config
        resp3 = await ac.post("/rag/llm/external/config", json={"model": "gpt-4"})
        assert resp3.status_code == 501
        resp4 = await ac.post("/rag/llm/safety/config", json={"model": "gpt-4"})
        assert resp4.status_code == 501


@pytest.mark.asyncio
async def test_validation_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Upload rules with missing columns (missing risk_level)
        import io

        file = io.BytesIO(b"id,text\n1,hello\n2,world")
        resp = await ac.post(
            "/api/v1/upload/rules",
            files={"file": ("rules.csv", file, "text/csv")},
            data={"text_columns": "text"},
        )
        assert resp.status_code == 400 or resp.status_code == 422
