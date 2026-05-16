"""Service for processing queries of any length with adaptive strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config.settings import settings
from src.services.llm_adapter import LLMAdapter
from src.utils.logger import logger


@dataclass
class ProcessedQuery:
    """Result of query processing with strategy information."""

    search_queries: list[str]
    full_context: str
    strategy: Literal["direct", "chunking"]
    chunks: list[str] | None = None


class QueryProcessor:
    """
    Handle queries of any length with adaptive processing strategies.

    Strategies:
    - Direct: < 8K chars - use query as-is (fast path)
    - Chunking: >= 8K chars - split into overlapping chunks for multi-query RAG

    Note: LLM-based compression was removed for performance reasons.
    """

    def __init__(self, llm_adapter: LLMAdapter | None = None):
        """
        Initialize query processor.

        Args:
            llm_adapter: LLM adapter for query compression (optional, creates default if None)
        """
        self.llm_adapter = llm_adapter or LLMAdapter(role="external")

    async def process_query(self, query: str) -> ProcessedQuery:
        """
        Process a query adaptively based on its length.

        Args:
            query: User query of any length

        Returns:
            ProcessedQuery with search queries, full context, and strategy used
        """
        query_length = len(query)
        logger.info(f"Processing query of length {query_length} characters")

        if query_length <= settings.QUERY_DIRECT_THRESHOLD:
            # Short query - use directly (fast path)
            logger.info("Using direct processing strategy (query length <= 8K)")
            return ProcessedQuery(
                search_queries=[query], full_context=query, strategy="direct"
            )

        else:
            # Long query - chunk and extract search queries
            logger.info(
                f"Using chunking strategy (query length > 8K: {query_length} chars)"
            )
            chunks = self._chunk_text(query)
            search_queries = self._select_search_queries(chunks)

            return ProcessedQuery(
                search_queries=search_queries,
                full_context=query,
                strategy="chunking",
                chunks=chunks,
            )

    def _chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks for better context preservation.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks with overlap
        """
        chunks = []
        chunk_size = settings.CHUNK_SIZE
        overlap = settings.CHUNK_OVERLAP

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]

            # Try to break at sentence boundaries for better coherence
            if end < len(text):
                # Look for last sentence ending in the overlap region
                overlap_region = chunk[-overlap:]
                last_period = overlap_region.rfind(".")
                last_newline = overlap_region.rfind("\n")
                break_point = max(last_period, last_newline)

                if break_point > 0:
                    # Break at sentence boundary
                    chunk = chunk[: -(overlap - break_point)]

            chunks.append(chunk.strip())

            # Move start forward
            if end >= len(text):
                break
            start = end - overlap

        logger.info(f"Split query into {len(chunks)} chunks")
        return chunks

    def _select_search_queries(self, chunks: list[str]) -> list[str]:
        """
        Select representative chunks for multi-query search.

        For very long documents, we don't want to search with every chunk.
        Instead, select a representative subset.

        Args:
            chunks: All chunks from the query

        Returns:
            List of search queries (max MAX_SEARCH_QUERIES)
        """
        max_queries = settings.MAX_SEARCH_QUERIES

        if len(chunks) <= max_queries:
            # Use all chunks
            return chunks

        # Use evenly distributed chunks
        # Always include first and last, spread others evenly
        indices = [0]  # First chunk

        if max_queries > 2:
            # Add evenly spaced middle chunks
            step = len(chunks) // (max_queries - 1)
            for i in range(1, max_queries - 1):
                indices.append(min(i * step, len(chunks) - 2))

        indices.append(len(chunks) - 1)  # Last chunk

        selected = [chunks[i] for i in sorted(set(indices))]
        logger.info(
            f"Selected {len(selected)} representative chunks from {len(chunks)} total"
        )
        return selected
