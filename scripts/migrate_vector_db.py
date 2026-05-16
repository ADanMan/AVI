"""Utility script to migrate vector DB collections between providers."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Literal


# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.schemas import FilteredContent
from src.services.vector_db import ChromaVectorDBService, QdrantVectorDBService, VectorDBClient
from src.utils.logger import logger


Provider = Literal["chroma", "qdrant"]


def build_client(provider: Provider) -> VectorDBClient:
    provider = provider.lower()
    if provider == "chroma":
        return ChromaVectorDBService()
    if provider == "qdrant":
        return QdrantVectorDBService()
    raise ValueError(f"Unsupported provider: {provider}")


async def migrate_collections(source: VectorDBClient, target: VectorDBClient) -> None:
    logger.info("Fetching data from source vector DB")
    rules = await source.get_all_rules()
    documents = await source.get_all_documents()
    links = await source.get_all_links()

    logger.info("Resetting target collections")
    target.reset_filter_collection()
    target.reset_documents_collection()
    target.reset_links_collection()

    if rules:
        rule_models = [
            FilteredContent(
                text=rule.get("text", ""),
                category=rule.get("category", "other"),
                risk_level=int(rule.get("risk_level", 0)),
                threshold=float(rule.get("threshold", 0.75)),
            )
            for rule in rules
        ]
        rule_ids = [str(rule.get("id")) for rule in rules]
        target.add_filter_rules_batch(rule_models, ids=rule_ids)
        logger.info("Migrated %d rules", len(rule_ids))
    else:
        logger.info("No rules to migrate")

    if documents:
        normalized_docs = [
            {
                "text": doc.get("text", ""),
                "metadata": {
                    **{k: v for k, v in doc.get("metadata", {}).items() if k != "text"},
                    "document_id": doc.get("document_id"),
                },
            }
            for doc in documents
        ]
        target.add_documents(normalized_docs)
        logger.info("Migrated %d documents", len(normalized_docs))
    else:
        logger.info("No documents to migrate")

    for link in links:
        rule_id = str(link.get("rule_id"))
        document_id = str(link.get("document_id"))
        if not rule_id or not document_id:
            continue
        await target.link_rule_to_documents(
            rule_id,
            [document_id],
            is_approved=bool(link.get("is_approved", True)),
        )
    logger.info("Migrated %d links", len(links))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate vector DB collections between providers")
    parser.add_argument("--source", choices=["chroma", "qdrant"], default="chroma")
    parser.add_argument("--target", choices=["chroma", "qdrant"], default="qdrant")
    args = parser.parse_args()

    if args.source == args.target:
        raise SystemExit("Source and target providers must be different")

    source_client = build_client(args.source)
    target_client = build_client(args.target)

    await migrate_collections(source_client, target_client)
    logger.info("Migration completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
