"""
LinksManager: service for managing links between rules and documents.
"""

from src.services.vector_db import VectorDBClient, VectorDBService


class LinksManager:
    def __init__(self, vector_db: VectorDBClient | None = None):
        self.vector_db = vector_db or VectorDBService()

    async def create_link(self, rule_id: str, document_id: str, is_approved: bool = True):
        """
        Create a link between a rule and a document.

        Args:
            rule_id: Rule identifier.
            document_id: Document identifier.
            is_approved: Whether the link is approved.

        Returns:
            Result of the linking operation.
        """
        return await self.vector_db.link_rule_to_documents(rule_id, [document_id], is_approved)

    async def delete_link(self, rule_id: str, document_id: str):
        """
        Delete a link between a rule and a document.

        Args:
            rule_id: Rule identifier.
            document_id: Document identifier.

        Returns:
            Result of the unlinking operation.
        """
        return await self.vector_db.remove_rule_document_link(rule_id, document_id)

    async def batch_create_links(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ):
        """
        Create links between a rule and multiple documents.

        Args:
            rule_id: Rule identifier.
            document_ids: List of document identifiers.
            is_approved: Whether the links are approved.

        Returns:
            Result of the batch linking operation.
        """
        return await self.vector_db.link_rule_to_documents(rule_id, document_ids, is_approved)

    async def batch_delete_links(self, rule_id: str, document_ids: list[str]):
        """
        Delete links between a rule and multiple documents.

        Args:
            rule_id: Rule identifier.
            document_ids: List of document identifiers.

        Returns:
            List of results for each unlinking operation.
        """
        results = []
        for doc_id in document_ids:
            results.append(await self.vector_db.remove_rule_document_link(rule_id, doc_id))
        return results

    async def get_links_for_rule(self, rule_id: str):
        """
        Get all documents linked to a rule.

        Args:
            rule_id: Rule identifier.

        Returns:
            List of linked documents.
        """
        return await self.vector_db.get_documents_for_rule(rule_id)

    async def get_links_for_document(self, document_id: str):
        """
        Get all rules linked to a document.

        Args:
            document_id: Document identifier.

        Returns:
            List of linked rules.
        """
        return await self.vector_db.get_rules_for_document(document_id)

    async def approve_link(self, rule_id: str, document_id: str, is_approved: bool = True):
        """
        Approve or unapprove a link between a rule and a document.

        Args:
            rule_id: Rule identifier.
            document_id: Document identifier.
            is_approved: Whether the link is approved (default: True).

        Returns:
            Updated link object or None if link doesn't exist.
        """
        return await self.vector_db.update_link_approval(rule_id, document_id, is_approved)
