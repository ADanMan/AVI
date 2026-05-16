"""Tests for QueryProcessor service."""

import pytest

from config.settings import settings
from src.services.query_processor import QueryProcessor


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_direct_strategy_short_query():
    """Test that short queries use direct strategy."""
    processor = QueryProcessor()
    short_query = "What is machine learning?"

    result = await processor.process_query(short_query)

    assert result.strategy == "direct"
    assert len(result.search_queries) == 1
    assert result.search_queries[0] == short_query
    assert result.full_context == short_query
    assert result.chunks is None


@pytest.mark.asyncio
async def test_chunking_strategy_medium_query():
    """Test that medium-length queries use chunking strategy."""
    processor = QueryProcessor()

    # Create a query just over the direct threshold
    medium_query = "A" * (settings.QUERY_DIRECT_THRESHOLD + 100)

    result = await processor.process_query(medium_query)

    assert result.strategy == "chunking"
    assert len(result.search_queries) >= 1
    assert result.full_context == medium_query
    assert result.chunks is not None


@pytest.mark.asyncio
async def test_chunking_strategy_very_long_query():
    """Test that very long queries use chunking strategy."""
    processor = QueryProcessor()

    # Create a very long query
    long_query = "B" * 50000

    result = await processor.process_query(long_query)

    assert result.strategy == "chunking"
    assert len(result.search_queries) >= 1
    assert len(result.search_queries) <= settings.MAX_SEARCH_QUERIES
    assert result.full_context == long_query
    assert result.chunks is not None
    assert len(result.chunks) > 1


def test_chunk_text():
    """Test text chunking with overlap."""
    processor = QueryProcessor()

    # Create text longer than chunk size
    text = "A" * (settings.CHUNK_SIZE * 3)

    chunks = processor._chunk_text(text)

    assert len(chunks) >= 2
    # Check that chunks have expected size (approximately)
    for chunk in chunks[:-1]:  # All but last
        assert len(chunk) <= settings.CHUNK_SIZE
    # Check overlap works (adjacent chunks should share content)
    if len(chunks) >= 2:
        # Due to overlap, some content should be shared
        assert len(chunks) > len(text) // settings.CHUNK_SIZE


def test_select_search_queries_few_chunks():
    """Test query selection when chunks <= max queries."""
    processor = QueryProcessor()

    chunks = ["chunk1", "chunk2", "chunk3"]

    selected = processor._select_search_queries(chunks)

    assert len(selected) == len(chunks)
    assert selected == chunks


def test_select_search_queries_many_chunks():
    """Test query selection when chunks > max queries."""
    processor = QueryProcessor()

    # Create more chunks than MAX_SEARCH_QUERIES
    chunks = [f"chunk{i}" for i in range(settings.MAX_SEARCH_QUERIES * 2)]

    selected = processor._select_search_queries(chunks)

    assert len(selected) == settings.MAX_SEARCH_QUERIES
    # Should include first and last
    assert selected[0] == chunks[0]
    assert selected[-1] == chunks[-1]


@pytest.mark.asyncio
@pytest.mark.smoke
async def test_max_query_length():
    """Test that queries up to MAX_QUERY_LENGTH are accepted."""
    processor = QueryProcessor()

    # Create a query at the max length
    max_query = "C" * settings.MAX_QUERY_LENGTH

    result = await processor.process_query(max_query)

    # Should not fail, should use chunking strategy
    assert result.strategy == "chunking"
    assert result.full_context == max_query


@pytest.mark.asyncio
async def test_sentence_boundary_chunking():
    """Test that chunking prefers sentence boundaries."""
    processor = QueryProcessor()

    # Create text with clear sentence boundaries
    sentence = "This is a sentence. "
    text = sentence * 1000  # Many sentences

    chunks = processor._chunk_text(text)

    # At least some chunks should end with a period (sentence boundary)
    chunks_ending_with_period = sum(1 for c in chunks if c.endswith("."))
    assert chunks_ending_with_period > 0
