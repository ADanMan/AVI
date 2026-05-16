"""State manager for tracking indexing progress and status."""

import asyncio
from datetime import datetime
from typing import Optional

from src.models.schemas import IndexingStatus


class IndexingStateManager:
    """
    Singleton class to manage and track indexing state across the application.

    This manager maintains the current status of indexing operations, including
    progress, counts, timing information, and any errors that occur.
    """

    _instance: Optional["IndexingStateManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the state manager with default idle state."""
        if self._initialized:
            return

        self._status = "idle"
        self._progress_percentage = 0.0
        self._indexed_rules = 0
        self._indexed_documents = 0
        self._indexed_links = 0
        self._total_rules = 0
        self._total_documents = 0
        self._total_links = 0
        self._start_time: datetime | None = None
        self._end_time: datetime | None = None
        self._error_message: str | None = None
        self._current_operation: str | None = None
        self._initialized = True

    async def start_indexing(
        self, total_rules: int = 0, total_documents: int = 0, total_links: int = 0
    ):
        """
        Mark the start of an indexing operation.

        Args:
            total_rules: Total number of rules to index
            total_documents: Total number of documents to index
            total_links: Total number of links to index
        """
        async with self._lock:
            self._status = "in_progress"
            self._progress_percentage = 0.0
            self._indexed_rules = 0
            self._indexed_documents = 0
            self._indexed_links = 0
            self._total_rules = total_rules
            self._total_documents = total_documents
            self._total_links = total_links
            self._start_time = datetime.now()
            self._end_time = None
            self._error_message = None
            self._current_operation = "Starting indexing"

    async def update_progress(
        self,
        indexed_rules: int | None = None,
        indexed_documents: int | None = None,
        indexed_links: int | None = None,
        current_operation: str | None = None,
    ):
        """
        Update the progress of the indexing operation.

        Args:
            indexed_rules: Number of rules indexed so far
            indexed_documents: Number of documents indexed so far
            indexed_links: Number of links indexed so far
            current_operation: Description of current operation
        """
        async with self._lock:
            if indexed_rules is not None:
                self._indexed_rules = indexed_rules
            if indexed_documents is not None:
                self._indexed_documents = indexed_documents
            if indexed_links is not None:
                self._indexed_links = indexed_links
            if current_operation is not None:
                self._current_operation = current_operation

            # Calculate progress percentage
            total_items = self._total_rules + self._total_documents + self._total_links
            if total_items > 0:
                indexed_items = self._indexed_rules + self._indexed_documents + self._indexed_links
                self._progress_percentage = min(100.0, (indexed_items / total_items) * 100.0)

    async def complete_indexing(self):
        """Mark the indexing operation as successfully completed."""
        async with self._lock:
            self._status = "completed"
            self._progress_percentage = 100.0
            self._end_time = datetime.now()
            self._current_operation = "Indexing completed successfully"

    async def fail_indexing(self, error_message: str):
        """
        Mark the indexing operation as failed.

        Args:
            error_message: Description of the error that occurred
        """
        async with self._lock:
            self._status = "failed"
            self._end_time = datetime.now()
            self._error_message = error_message
            self._current_operation = "Indexing failed"

    async def reset_to_idle(self):
        """Reset the state to idle after a completed or failed indexing operation."""
        async with self._lock:
            self._status = "idle"
            self._progress_percentage = 0.0
            self._indexed_rules = 0
            self._indexed_documents = 0
            self._indexed_links = 0
            self._total_rules = 0
            self._total_documents = 0
            self._total_links = 0
            self._start_time = None
            self._end_time = None
            self._error_message = None
            self._current_operation = None

    async def get_status(self) -> IndexingStatus:
        """
        Get the current indexing status.

        Returns:
            IndexingStatus object with current state
        """
        async with self._lock:
            duration = None
            if self._start_time:
                end = self._end_time or datetime.now()
                duration = (end - self._start_time).total_seconds()

            return IndexingStatus(
                status=self._status,
                progress_percentage=self._progress_percentage,
                indexed_rules=self._indexed_rules,
                indexed_documents=self._indexed_documents,
                indexed_links=self._indexed_links,
                total_rules=self._total_rules,
                total_documents=self._total_documents,
                total_links=self._total_links,
                start_time=self._start_time,
                end_time=self._end_time,
                duration_seconds=duration,
                error_message=self._error_message,
                current_operation=self._current_operation,
            )

    def is_indexing_in_progress(self) -> bool:
        """
        Check if an indexing operation is currently in progress.

        Returns:
            True if indexing is in progress, False otherwise
        """
        return self._status == "in_progress"


# Global singleton instance
indexing_state = IndexingStateManager()
