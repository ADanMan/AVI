import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


import pytest

from src.services.links_manager import LinksManager
from src.services.vector_db import VectorDBService


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_create_and_delete_link(monkeypatch):
    manager = LinksManager(vector_db=VectorDBService())

    # Monkeypatch vector_db methods (async)
    async def mock_link_rule_to_documents(rule_id, document_ids, is_approved):
        return [
            {
                "rule_id": rule_id,
                "document_id": document_ids[0],
                "is_approved": is_approved,
            }
        ]

    async def mock_remove_rule_document_link(rule_id, document_id):
        return True

    monkeypatch.setattr(manager.vector_db, "link_rule_to_documents", mock_link_rule_to_documents)
    monkeypatch.setattr(
        manager.vector_db, "remove_rule_document_link", mock_remove_rule_document_link
    )
    link = await manager.create_link("rule1", "doc1", True)
    assert link[0]["rule_id"] == "rule1"
    assert link[0]["document_id"] == "doc1"
    assert link[0]["is_approved"] is True
    result = await manager.delete_link("rule1", "doc1")
    assert result is True


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_batch_create_links(monkeypatch):
    """Test batch linking multiple documents to a rule."""
    manager = LinksManager(vector_db=VectorDBService())

    # Mock batch link creation
    async def mock_link_rule_to_documents(rule_id, document_ids, is_approved):
        return [
            {
                "rule_id": rule_id,
                "document_id": doc_id,
                "is_approved": is_approved,
                "relevance_score": None,
            }
            for doc_id in document_ids
        ]

    monkeypatch.setattr(manager.vector_db, "link_rule_to_documents", mock_link_rule_to_documents)

    # Test batch create with 3 documents
    links = await manager.batch_create_links("rule1", ["doc1", "doc2", "doc3"], is_approved=True)

    assert len(links) == 3
    assert all(link["rule_id"] == "rule1" for link in links)
    assert all(link["is_approved"] is True for link in links)
    assert [link["document_id"] for link in links] == ["doc1", "doc2", "doc3"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_batch_create_links_unapproved(monkeypatch):
    """Test batch linking with is_approved=False."""
    manager = LinksManager(vector_db=VectorDBService())

    async def mock_link_rule_to_documents(rule_id, document_ids, is_approved):
        return [
            {
                "rule_id": rule_id,
                "document_id": doc_id,
                "is_approved": is_approved,
                "relevance_score": None,
            }
            for doc_id in document_ids
        ]

    monkeypatch.setattr(manager.vector_db, "link_rule_to_documents", mock_link_rule_to_documents)

    links = await manager.batch_create_links("rule2", ["doc10", "doc20"], is_approved=False)

    assert len(links) == 2
    assert all(link["rule_id"] == "rule2" for link in links)
    assert all(link["is_approved"] is False for link in links)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_batch_delete_links(monkeypatch):
    """Test batch deleting multiple document links from a rule."""
    manager = LinksManager(vector_db=VectorDBService())

    async def mock_remove_rule_document_link(rule_id, document_id):
        return True

    monkeypatch.setattr(
        manager.vector_db, "remove_rule_document_link", mock_remove_rule_document_link
    )

    results = await manager.batch_delete_links("rule1", ["doc1", "doc2", "doc3"])

    assert len(results) == 3
    assert all(result is True for result in results)


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_approve_link(monkeypatch):
    """Test approving a link between a rule and a document."""
    manager = LinksManager(vector_db=VectorDBService())

    async def mock_update_link_approval(rule_id, document_id, is_approved):
        from src.models.schemas import RuleDocument

        return RuleDocument(
            rule_id=rule_id,
            document_id=document_id,
            is_approved=is_approved,
            relevance_score=0.85,
        )

    monkeypatch.setattr(manager.vector_db, "update_link_approval", mock_update_link_approval)

    # Test approving a link
    link = await manager.approve_link("rule1", "doc1", True)

    assert link.rule_id == "rule1"
    assert link.document_id == "doc1"
    assert link.is_approved is True
    assert link.relevance_score == 0.85


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_approve_link_not_found(monkeypatch):
    """Test approving a non-existent link."""
    manager = LinksManager(vector_db=VectorDBService())

    async def mock_update_link_approval(rule_id, document_id, is_approved):
        return None

    monkeypatch.setattr(manager.vector_db, "update_link_approval", mock_update_link_approval)

    # Test approving a non-existent link
    link = await manager.approve_link("rule_nonexistent", "doc_nonexistent", True)

    assert link is None
