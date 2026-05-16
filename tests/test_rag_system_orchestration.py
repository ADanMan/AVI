import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


import pytest

from src.core.rag_system import RAGSystem


@pytest.mark.asyncio
async def test_rag_system_services_property():
    rag = RAGSystem()
    services = rag.services
    assert "vector_db" in services
    assert "llm_adapter" in services
    assert "rag_service" in services
    assert callable(getattr(rag, "process_query", None))
