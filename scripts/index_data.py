"""Utilities for indexing the project's datasets into ChromaDB."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.indexing_service import IndexingService
from src.services.vector_db import VectorDBService
from src.utils.logger import logger


VectorDBFactory = Callable[[], VectorDBService]
IndexingServiceFactory = Callable[[VectorDBService], IndexingService]


async def reindex_all(
    *,
    vector_db_factory: VectorDBFactory = VectorDBService,
    indexing_service_factory: IndexingServiceFactory = IndexingService,
) -> dict[str, object]:
    """Run a full indexing cycle for all available data sources."""
    logger.info("Starting data indexing in ChromaDB...")
    vector_db = vector_db_factory()
    indexing_service = indexing_service_factory(vector_db)

    result = await indexing_service.reindex_all()
    logger.info("Indexing result: {}", result)

    stats = await vector_db.get_collection_stats()
    logger.info("Collection statistics: {}", stats)

    close = getattr(vector_db, "aclose", None)
    if callable(close):
        await close()

    return {"result": result, "stats": stats}


def run_sync(
    *,
    vector_db_factory: VectorDBFactory = VectorDBService,
    indexing_service_factory: IndexingServiceFactory = IndexingService,
) -> dict[str, object]:
    """Convenience wrapper for synchronous execution."""
    return asyncio.run(
        reindex_all(
            vector_db_factory=vector_db_factory,
            indexing_service_factory=indexing_service_factory,
        )
    )


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    run_sync()
