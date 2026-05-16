"""Unified vector database services with provider abstraction."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from config.settings import directory_manager, settings
from src.models.schemas import FilteredContent, FilterMatch, RuleDocument
from src.utils.logger import logger

try:  # Optional import for Chroma provider
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from chromadb.utils import embedding_functions as chroma_embeddings
except Exception:  # pragma: no cover - optional dependency may be absent in tests
    chromadb = None
    ChromaSettings = None
    chroma_embeddings = None

UnexpectedResponse = None
ResponseHandlingException = None

try:  # Optional import for direct sentence transformer usage
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency may be absent in tests
    SentenceTransformer = None  # type: ignore[assignment]

try:  # Optional import for Qdrant provider
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels

    # Import exceptions - modern versions use http.exceptions
    try:
        from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
    except ImportError:
        # Older versions may use different module
        from qdrant_client.exceptions import (
            ResponseHandlingException,  # type: ignore[assignment]
            UnexpectedResponse,  # type: ignore[assignment]
        )

    _QDRANT_UNEXPECTED_RESPONSE_EXCEPTIONS = (UnexpectedResponse, ResponseHandlingException)
except Exception:  # pragma: no cover - optional dependency may be absent in tests
    QdrantClient = None
    qmodels = None
    UnexpectedResponse = None
    ResponseHandlingException = None
    _QDRANT_UNEXPECTED_RESPONSE_EXCEPTIONS: tuple[type[BaseException], ...] = ()


DEFAULT_TOP_K = 5

# Connection pooling cache for Qdrant clients
_qdrant_client_cache: dict[str, Any] = {}


def _get_qdrant_client_key(host: str | None, path: Path | None, port: int | None) -> str:
    """Generate cache key for Qdrant client based on connection parameters."""
    if host:
        return f"host:{host}:{port or 6333}"
    return f"path:{path}"


def _get_or_create_qdrant_client(
    host: str | None = None,
    path: Path | None = None,
    api_key: str | None = None,
    port: int | None = None,
) -> Any:
    """
    Get cached Qdrant client or create new one.

    Args:
        host: Qdrant server host
        path: Local path for Qdrant storage
        api_key: API key for remote Qdrant
        port: Qdrant server port

    Returns:
        QdrantClient instance
    """
    if QdrantClient is None:
        raise RuntimeError("Qdrant dependencies are not available")

    cache_key = _get_qdrant_client_key(host, path, port)

    if cache_key in _qdrant_client_cache:
        logger.debug(f"Reusing cached Qdrant client for {cache_key}")
        return _qdrant_client_cache[cache_key]

    if host:
        # Build URL with explicit http:// protocol to avoid SSL issues
        if not host.startswith(("http://", "https://")):
            url = f"http://{host}:{port or 6333}"
        else:
            url = f"{host}:{port}" if port else host
        client = QdrantClient(url=url, api_key=api_key, prefer_grpc=False)
        logger.info(f"Created new Qdrant client for remote host: {url}")
    else:
        if path:
            directory_manager.ensure_directory(Path(path))
        client = QdrantClient(path=str(path))
        logger.info(f"Created new Qdrant client for local path: {path}")

    _qdrant_client_cache[cache_key] = client
    return client


@runtime_checkable
class VectorDBClient(Protocol):
    """Protocol describing vector database operations used by the application."""

    def search(
        self, query: str, threshold: float | None = None, top_k: int | None = None
    ) -> list[dict[str, Any]]: ...

    def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> None: ...

    def add_filter_rule(self, rule: FilteredContent) -> str: ...

    def add_filter_rules_batch(
        self, rules: list[FilteredContent], ids: list[str] | None = None
    ) -> list[str]: ...

    async def find_matching_rules(self, text: str, n_results: int = 10) -> list[FilterMatch]: ...

    async def link_rule_to_documents(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ) -> list[RuleDocument]: ...

    async def remove_rule_document_link(self, rule_id: str, document_id: str) -> bool: ...

    async def update_link_approval(
        self, rule_id: str, document_id: str, is_approved: bool
    ) -> RuleDocument | None: ...

    async def get_all_rules(self) -> list[dict[str, Any]]: ...

    async def get_rule(self, rule_id: str) -> dict[str, Any] | None: ...

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]: ...

    async def get_documents_for_rule(
        self, rule_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]: ...

    async def get_all_links(self) -> list[dict[str, Any]]: ...

    async def get_collection_stats(self) -> dict[str, Any]: ...

    async def get_rule_threshold(self, rule_text: str) -> float: ...

    def reset_documents_collection(self) -> None: ...

    def reset_filter_collection(self) -> None: ...

    def reset_links_collection(self) -> None: ...

    async def get_all_documents(self) -> list[dict[str, Any]]: ...


class InMemoryVectorDB(VectorDBClient):
    """Simple in-memory implementation used for tests when AVI_TEST_MODE=1."""

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.rules: dict[str, dict[str, Any]] = {}
        self.links: dict[str, dict[str, Any]] = {}

    def _generate_rule_id(self) -> str:
        return f"rule_{uuid.uuid4().hex}"

    def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> None:
        for doc in documents:
            doc_id = str(doc["metadata"].get("document_id"))
            self.documents[doc_id] = {
                "document_id": doc_id,
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {}),
            }

    def add_filter_rule(self, rule: FilteredContent) -> str:
        rule_id = self._generate_rule_id()
        self.rules[rule_id] = {
            "id": rule_id,
            "text": rule.text,
            "category": rule.category,
            "risk_level": rule.risk_level,
            "threshold": rule.threshold,
        }
        return rule_id

    def add_filter_rules_batch(
        self, rules: list[FilteredContent], ids: list[str] | None = None
    ) -> list[str]:
        rule_ids: list[str] = []
        for idx, rule in enumerate(rules):
            rule_id = ids[idx] if ids and idx < len(ids) else self._generate_rule_id()
            self.rules[rule_id] = {
                "id": rule_id,
                "text": rule.text,
                "category": rule.category,
                "risk_level": rule.risk_level,
                "threshold": rule.threshold,
            }
            rule_ids.append(rule_id)
        return rule_ids

    def search(
        self, query: str, threshold: float | None = None, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        if not query:
            return []
        top_k = top_k or DEFAULT_TOP_K
        threshold = threshold or settings.RAG_THRESHOLD
        matches: list[tuple[float, dict[str, Any]]] = []
        query_tokens = set(query.lower().split())
        for doc in self.documents.values():
            doc_tokens = set(str(doc.get("text", "")).lower().split())
            if not doc_tokens:
                continue
            overlap = len(query_tokens & doc_tokens) / max(len(query_tokens), 1)
            if overlap >= threshold:
                matches.append((overlap, doc))
        matches.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "document_id": doc["document_id"],
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {}),
                "relevance_score": score,
            }
            for score, doc in matches[:top_k]
        ]

    async def find_matching_rules(self, text: str, n_results: int = 10) -> list[FilterMatch]:
        if not text:
            return []
        text_lower = text.lower()
        matches: list[FilterMatch] = []
        for rule_id, rule in self.rules.items():
            if rule["text"].lower() in text_lower:
                matches.append(
                    FilterMatch(
                        rule_id=rule_id,
                        rule_text=rule["text"],
                        category=rule.get("category", "other"),
                        risk_level=int(rule.get("risk_level", 0)),
                        relevance_score=1.0,
                    )
                )
        return matches[:n_results]

    async def link_rule_to_documents(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ) -> list[RuleDocument]:
        links: list[RuleDocument] = []
        for document_id in document_ids:
            link_id = f"{rule_id}_{document_id}"
            self.links[link_id] = {
                "id": link_id,
                "rule_id": rule_id,
                "document_id": document_id,
                "is_approved": is_approved,
            }
            links.append(
                RuleDocument(rule_id=rule_id, document_id=document_id, is_approved=is_approved)
            )
        return links

    async def remove_rule_document_link(self, rule_id: str, document_id: str) -> bool:
        link_id = f"{rule_id}_{document_id}"
        return self.links.pop(link_id, None) is not None

    async def update_link_approval(
        self, rule_id: str, document_id: str, is_approved: bool
    ) -> RuleDocument | None:
        link_id = f"{rule_id}_{document_id}"
        if link_id in self.links:
            self.links[link_id]["is_approved"] = is_approved
            return RuleDocument(
                rule_id=rule_id,
                document_id=document_id,
                is_approved=is_approved,
                relevance_score=self.links[link_id].get("relevance_score"),
            )
        return None

    async def get_all_rules(self) -> list[dict[str, Any]]:
        return list(self.rules.values())

    async def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        return self.rules.get(rule_id)

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        rules: list[dict[str, Any]] = []
        for link in self.links.values():
            if link["document_id"] == document_id and (
                not only_approved or link.get("is_approved", False)
            ):
                rule = self.rules.get(link["rule_id"])
                if rule:
                    rules.append({**link, "rule_text": rule.get("text")})
        return rules

    async def get_documents_for_rule(
        self, rule_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        import time

        from src.monitoring.metrics import content_filter_metrics

        start_time = time.perf_counter()

        docs: list[dict[str, Any]] = []
        for link in self.links.values():
            if link["rule_id"] == rule_id and (not only_approved or link.get("is_approved", False)):
                doc = self.documents.get(link["document_id"])
                if doc:
                    docs.append(
                        {**link, "text": doc.get("text"), "metadata": doc.get("metadata", {})}
                    )

        # Record metrics for linked documents retrieval
        latency_seconds = time.perf_counter() - start_time
        content_filter_metrics.record_linked_docs_retrieval(
            rule_id=rule_id, latency_seconds=latency_seconds, num_docs=len(docs)
        )

        return docs

    async def get_all_links(self) -> list[dict[str, Any]]:
        return list(self.links.values())

    async def get_collection_stats(self) -> dict[str, Any]:
        return {
            "main_collection": {
                "total_documents": len(self.documents),
            },
            "filter_collection": {
                "total_rules": len(self.rules),
            },
        }

    async def get_rule_threshold(self, rule_text: str) -> float:
        for rule in self.rules.values():
            if rule.get("text") == rule_text:
                return float(rule.get("threshold", 0.75))
        return 0.75

    def reset_documents_collection(self) -> None:
        self.documents.clear()

    def reset_filter_collection(self) -> None:
        self.rules.clear()

    def reset_links_collection(self) -> None:
        self.links.clear()

    async def get_all_documents(self) -> list[dict[str, Any]]:
        return list(self.documents.values())


class ChromaVectorDBService(VectorDBClient):
    """Chroma-based vector DB implementation."""

    def __init__(
        self,
        main_collection_name: str = "main_collection",
        filter_collection_name: str = "filter_collection",
        links_collection_name: str = "rule_document_links",
        embedding_model: str | None = None,
    ) -> None:
        if chromadb is None or ChromaSettings is None or chroma_embeddings is None:
            raise RuntimeError("Chroma dependencies are not available")

        # Use configured embedding model from settings
        if embedding_model is None:
            embedding_model = settings.EMBEDDING_MODEL

        db_path = settings.VECTOR_DB_PATH
        # Use DirectoryManager instead of direct mkdir
        directory_manager.ensure_directory(Path(db_path))

        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self.embedding_function = chroma_embeddings.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        self.main_collection_name = main_collection_name
        self.filter_collection_name = filter_collection_name
        self.links_collection_name = links_collection_name

        self.main_collection = self._init_collection(main_collection_name)
        self.filter_collection = self._init_collection(filter_collection_name)
        self.links_collection = self._init_collection(links_collection_name, use_embedding=False)

        logger.info("Chroma vector DB client initialized")

    def _init_collection(self, name: str, use_embedding: bool = True):
        collections = self.client.list_collections()
        collection_exists = any(c.name == name for c in collections)
        if collection_exists:
            if use_embedding:
                return self.client.get_collection(
                    name=name, embedding_function=self.embedding_function
                )
            return self.client.get_collection(name=name)
        if use_embedding:
            return self.client.create_collection(
                name=name, embedding_function=self.embedding_function
            )
        return self.client.create_collection(name=name)

    # -- Basic operations --
    def search(
        self, query: str, threshold: float | None = None, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        if not query:
            return []
        top_k = top_k or DEFAULT_TOP_K
        threshold = threshold or settings.RAG_THRESHOLD

        results = self.main_collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        processed: list[dict[str, Any]] = []
        if results["ids"] and results["ids"][0]:
            for idx, document_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][idx]
                relevance_score = max(0.0, 1 - (distance / 2))
                if relevance_score < threshold:
                    continue
                processed.append(
                    {
                        "document_id": document_id,
                        "text": results["documents"][0][idx],
                        "metadata": results["metadatas"][0][idx],
                        "relevance_score": relevance_score,
                    }
                )
        return processed

    def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> None:
        if not documents:
            return
        # Documents are retrieved by ID via links, not by vector search
        # Use dummy embeddings to skip expensive embedding computation
        existing_ids = set(self.main_collection.get()["ids"])
        new_documents = [
            doc for doc in documents if doc["metadata"].get("document_id") not in existing_ids
        ]
        for i in range(0, len(new_documents), batch_size):
            batch = new_documents[i : i + batch_size]
            ids = [str(doc["metadata"].get("document_id")) for doc in batch]
            texts = [doc.get("text", "") for doc in batch]
            metadatas: list[dict[str, Any]] = []
            for doc in batch:
                metadata = dict(doc.get("metadata", {}))
                if "rule_ids" in metadata and isinstance(metadata["rule_ids"], list):
                    metadata["rule_ids"] = ",".join(metadata["rule_ids"])
                metadatas.append(metadata)
            if ids:
                # Use dummy embeddings for speed - documents are only retrieved by ID
                dummy_embeddings = [[0.0] * settings.INDEX_DIMENSION] * len(ids)
                self.main_collection.add(
                    ids=ids, documents=texts, metadatas=metadatas, embeddings=dummy_embeddings
                )

    def add_filter_rule(self, rule: FilteredContent) -> str:
        rule_id = f"rule_{uuid.uuid4().hex}"
        self.filter_collection.add(
            ids=[rule_id],
            documents=[rule.text],
            metadatas=[
                {
                    "category": rule.category,
                    "risk_level": rule.risk_level,
                    "threshold": rule.threshold,
                }
            ],
        )
        return rule_id

    def add_filter_rules_batch(
        self, rules: list[FilteredContent], ids: list[str] | None = None
    ) -> list[str]:
        if not rules:
            return []
        if ids and len(ids) != len(rules):
            raise ValueError("Length of IDs must match number of rules")
        rule_ids = ids or [f"rule_{uuid.uuid4().hex}" for _ in rules]
        self.filter_collection.add(
            ids=rule_ids,
            documents=[rule.text for rule in rules],
            metadatas=[
                {
                    "category": rule.category,
                    "risk_level": rule.risk_level,
                    "threshold": rule.threshold,
                }
                for rule in rules
            ],
        )
        return rule_ids

    async def find_matching_rules(self, text: str, n_results: int = 10) -> list[FilterMatch]:
        if not text:
            return []

        def _query() -> list[FilterMatch]:
            results = self.filter_collection.query(
                query_texts=[text],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
            matches: list[FilterMatch] = []
            if results["ids"] and results["ids"][0]:
                for idx, rule_id in enumerate(results["ids"][0]):
                    metadata = results["metadatas"][0][idx]
                    distance = results["distances"][0][idx]
                    relevance = max(0.0, 1 - (distance / 2))
                    matches.append(
                        FilterMatch(
                            rule_id=str(rule_id),
                            rule_text=str(results["documents"][0][idx]),
                            category=str(metadata.get("category", "other")),
                            risk_level=int(metadata.get("risk_level", 0)),
                            relevance_score=float(relevance),
                        )
                    )
            return matches

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _query)

    async def link_rule_to_documents(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ) -> list[RuleDocument]:
        links: list[RuleDocument] = []
        for document_id in document_ids:
            metadata = {
                "id": f"{rule_id}_{document_id}",
                "rule_id": rule_id,
                "document_id": document_id,
                "is_approved": is_approved,
            }
            link_id = f"{rule_id}_{document_id}"
            self.links_collection.add(
                ids=[link_id],
                documents=[f"Link between {rule_id} and {document_id}"],
                metadatas=[metadata],
            )
            links.append(
                RuleDocument(rule_id=rule_id, document_id=document_id, is_approved=is_approved)
            )
        return links

    async def remove_rule_document_link(self, rule_id: str, document_id: str) -> bool:
        link_id = f"{rule_id}_{document_id}"
        self.links_collection.delete(ids=[link_id])
        return True

    async def update_link_approval(
        self, rule_id: str, document_id: str, is_approved: bool
    ) -> RuleDocument | None:
        link_id = f"{rule_id}_{document_id}"

        def _update() -> RuleDocument | None:
            # Get existing link
            result = self.links_collection.get(ids=[link_id], include=["documents", "metadatas"])
            if not result["ids"]:
                return None

            # Update metadata
            metadata = result["metadatas"][0] if result.get("metadatas") else {}
            metadata["is_approved"] = is_approved

            # Upsert with updated metadata
            self.links_collection.upsert(
                ids=[link_id],
                documents=[result["documents"][0]],
                metadatas=[metadata],
            )

            return RuleDocument(
                rule_id=rule_id,
                document_id=document_id,
                is_approved=is_approved,
                relevance_score=metadata.get("relevance_score"),
            )

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _update)

    async def get_all_rules(self) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            results = self.filter_collection.get(include=["documents", "metadatas"])
            rules: list[dict[str, Any]] = []
            for idx, rule_id in enumerate(results["ids"]):
                metadata = results["metadatas"][idx] if results.get("metadatas") else {}
                rules.append(
                    {
                        "id": rule_id,
                        "text": results["documents"][idx],
                        **metadata,
                    }
                )
            return rules

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    async def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        def _get() -> dict[str, Any] | None:
            result = self.filter_collection.get(ids=[rule_id], include=["documents", "metadatas"])
            if result["ids"]:
                return {
                    "id": rule_id,
                    "text": result["documents"][0],
                    **(result["metadatas"][0] if result.get("metadatas") else {}),
                }
            return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            result = self.links_collection.get(
                where={"document_id": document_id}, include=["metadatas"]
            )
            links: list[dict[str, Any]] = []
            for metadata in result.get("metadatas", []):
                if only_approved and not metadata.get("is_approved", False):
                    continue
                link = dict(metadata)
                rule_id = metadata.get("rule_id")
                if rule_id:
                    rule_result = self.filter_collection.get(
                        ids=[rule_id], include=["documents", "metadatas"]
                    )
                    if rule_result["ids"]:
                        link["rule_text"] = rule_result["documents"][0]
                        link.update(rule_result["metadatas"][0])
                links.append(link)
            return links

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    async def get_documents_for_rule(
        self, rule_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        import time

        from src.monitoring.metrics import content_filter_metrics

        start_time = time.perf_counter()

        def _get() -> list[dict[str, Any]]:
            result = self.links_collection.get(where={"rule_id": rule_id}, include=["metadatas"])
            documents: list[dict[str, Any]] = []
            for metadata in result.get("metadatas", []):
                if only_approved and not metadata.get("is_approved", False):
                    continue
                doc_id = metadata.get("document_id")
                if doc_id:
                    doc_result = self.main_collection.get(
                        ids=[doc_id], include=["documents", "metadatas"]
                    )
                    if doc_result["ids"]:
                        documents.append(
                            {
                                "document_id": doc_id,
                                "text": doc_result["documents"][0],
                                "metadata": doc_result["metadatas"][0],
                                **metadata,
                            }
                        )
            return documents

        loop = asyncio.get_running_loop()
        documents = await loop.run_in_executor(None, _get)

        # Record metrics for linked documents retrieval
        latency_seconds = time.perf_counter() - start_time
        content_filter_metrics.record_linked_docs_retrieval(
            rule_id=rule_id, latency_seconds=latency_seconds, num_docs=len(documents)
        )

        return documents

    async def get_all_links(self) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            result = self.links_collection.get(include=["metadatas"])
            links: list[dict[str, Any]] = []
            for idx, metadata in enumerate(result.get("metadatas", [])):
                entry = dict(metadata)
                if result.get("ids") and idx < len(result["ids"]):
                    entry.setdefault("id", result["ids"][idx])
                links.append(entry)
            return links

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    async def get_collection_stats(self) -> dict[str, Any]:
        def _get() -> dict[str, Any]:
            main_stats = {"total_documents": self.main_collection.count(), "categories": {}}
            filter_stats = {
                "total_rules": self.filter_collection.count(),
                "categories": {},
                "risk_levels": {},
            }

            main_meta = self.main_collection.get(include=["metadatas"])
            for metadata in main_meta.get("metadatas", []):
                category = metadata.get("category", "uncategorized")
                main_stats["categories"][category] = main_stats["categories"].get(category, 0) + 1

            filter_meta = self.filter_collection.get(include=["metadatas"])
            for metadata in filter_meta.get("metadatas", []):
                category = metadata.get("category", "uncategorized")
                risk = metadata.get("risk_level", 0)
                filter_stats["categories"][category] = (
                    filter_stats["categories"].get(category, 0) + 1
                )
                filter_stats["risk_levels"][risk] = filter_stats["risk_levels"].get(risk, 0) + 1

            return {"main_collection": main_stats, "filter_collection": filter_stats}

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    async def get_rule_threshold(self, rule_text: str) -> float:
        def _get() -> float:
            results = self.filter_collection.query(
                query_texts=[rule_text], n_results=1, include=["metadatas"]
            )
            if results["metadatas"] and results["metadatas"][0]:
                return float(results["metadatas"][0][0].get("threshold", 0.75))
            return 0.75

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    def reset_documents_collection(self) -> None:
        self.client.delete_collection(self.main_collection_name)
        self.main_collection = self._init_collection(self.main_collection_name)

    def reset_filter_collection(self) -> None:
        self.client.delete_collection(self.filter_collection_name)
        self.filter_collection = self._init_collection(self.filter_collection_name)

    def reset_links_collection(self) -> None:
        self.client.delete_collection(self.links_collection_name)
        self.links_collection = self._init_collection(
            self.links_collection_name, use_embedding=False
        )

    async def get_all_documents(self) -> list[dict[str, Any]]:
        def _get() -> list[dict[str, Any]]:
            result = self.main_collection.get(include=["documents", "metadatas"])
            documents: list[dict[str, Any]] = []
            for idx, doc_id in enumerate(result["ids"]):
                documents.append(
                    {
                        "document_id": doc_id,
                        "text": result["documents"][idx],
                        "metadata": result["metadatas"][idx],
                    }
                )
            return documents

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)


class QdrantVectorDBService(VectorDBClient):
    """Qdrant-based vector DB implementation with hybrid search support."""

    def __init__(
        self,
        main_collection_name: str = "main_collection",
        filter_collection_name: str = "filter_collection",
        links_collection_name: str = "rule_document_links",
        embedding_model: str | None = None,
    ) -> None:
        if QdrantClient is None or qmodels is None:
            raise RuntimeError("Qdrant dependencies are not available")

        # Use configured embedding model from settings
        if embedding_model is None:
            embedding_model = settings.EMBEDDING_MODEL

        self.main_collection_name = main_collection_name
        self.filter_collection_name = filter_collection_name
        self.links_collection_name = links_collection_name
        self.vector_size = settings.INDEX_DIMENSION

        # Use connection pooling for Qdrant client
        if settings.QDRANT_HOST:
            self.client = _get_or_create_qdrant_client(
                host=settings.QDRANT_HOST,
                api_key=getattr(settings, "QDRANT_API_KEY", None),
                port=getattr(settings, "QDRANT_PORT", None),
            )
        else:
            path = settings.QDRANT_PATH or (settings.VECTOR_DB_PATH / "qdrant")
            self.client = _get_or_create_qdrant_client(path=path)

        self._embedding_model_name = embedding_model
        self._embedding_model = self._init_sentence_transformer(embedding_model)

        self._ensure_collection(
            self.main_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(
                    size=self.vector_size, distance=qmodels.Distance.COSINE
                )
            },
        )
        self._ensure_collection(
            self.filter_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(
                    size=self.vector_size, distance=qmodels.Distance.COSINE
                )
            },
        )
        self._ensure_collection(
            self.links_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(size=1, distance=qmodels.Distance.COSINE)
            },
        )

        logger.info("Qdrant vector DB client initialized")

    def _qdrant_collection_exists(self, name: str) -> bool:
        """Check if a Qdrant collection exists using get_collection/get_collections."""

        try:
            self.client.get_collection(name)
            return True
        except _QDRANT_UNEXPECTED_RESPONSE_EXCEPTIONS as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 404:
                return False
            # Some versions may not provide status_code but include the message
            message = str(exc).lower()
            if "not found" in message:
                return False
            try:
                collections_response = self.client.get_collections()
            except _QDRANT_UNEXPECTED_RESPONSE_EXCEPTIONS as inner_exc:
                raise exc from inner_exc
            collections = getattr(collections_response, "collections", []) or []
            if isinstance(collections, dict):
                collections = collections.get("collections", [])
            return any(getattr(collection, "name", None) == name for collection in collections)

    def _ensure_collection(self, name: str, vectors_config: dict[str, Any]) -> None:
        if not self._qdrant_collection_exists(name):
            self.client.create_collection(
                collection_name=name,
                vectors_config=vectors_config,
                optimizers_config=qmodels.OptimizersConfigDiff(default_segment_number=2),
            )

    # -- Helpers --
    def _init_sentence_transformer(self, model_name: str):
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not available")
        try:
            from config.settings import settings

            device = settings.EMBEDDING_DEVICE
            logger.info(f"Initializing SentenceTransformer on device: {device}")
            return SentenceTransformer(model_name, device=device)
        except Exception as exc:  # pragma: no cover - defensive guard
            raise RuntimeError("Failed to initialize sentence-transformers model") from exc

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not hasattr(self, "_embedding_model"):
            raise RuntimeError("Embedding model is not initialized")
        embeddings = self._embedding_model.encode(list(texts))
        if hasattr(embeddings, "tolist"):
            embeddings = embeddings.tolist()
        embeddings_list = list(embeddings)
        if embeddings_list and not isinstance(embeddings_list[0], list | tuple):
            embeddings_list = [embeddings_list]
        return [list(map(float, vector)) for vector in embeddings_list]

    @staticmethod
    def _tokenize(text: str) -> Counter:
        tokens = [token for token in text.lower().split() if token]
        return Counter(tokens)

    @staticmethod
    def _lexical_score(query_tokens: Counter, doc_tokens: Counter) -> float:
        if not query_tokens:
            return 0.0
        overlap = sum((query_tokens & doc_tokens).values())
        total = sum(query_tokens.values())
        return overlap / total if total else 0.0

    def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> None:
        if not documents:
            return
        # Documents are retrieved by ID via links, not by vector search
        # So we don't need to compute embeddings - use a dummy vector for speed
        dummy_vector = [0.0] * self.vector_size
        for start in range(0, len(documents), batch_size):
            batch = documents[start : start + batch_size]
            points = []
            for doc in batch:
                doc_id_str = str(doc.get("metadata", {}).get("document_id"))
                # Generate UUID from document ID (Qdrant requires UUID or int)
                doc_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id_str))
                payload = {
                    "text": doc.get("text", ""),
                    "document_id": doc_id_str,  # Keep original ID in payload
                    **doc.get("metadata", {}),
                }
                points.append(
                    qmodels.PointStruct(
                        id=doc_uuid,
                        vector={"dense": dummy_vector},
                        payload=payload,
                    )
                )
            if points:
                self.client.upsert(collection_name=self.main_collection_name, points=points)

    def add_filter_rule(self, rule: FilteredContent) -> str:
        rule_id = f"rule_{uuid.uuid4().hex}"
        self.add_filter_rules_batch([rule], ids=[rule_id])
        return rule_id

    def add_filter_rules_batch(
        self, rules: list[FilteredContent], ids: list[str] | None = None
    ) -> list[str]:
        if not rules:
            return []
        if ids and len(ids) != len(rules):
            raise ValueError("Length of IDs must match number of rules")
        rule_ids = ids or [f"rule_{uuid.uuid4().hex}" for _ in rules]
        embeddings = self._embed([rule.text for rule in rules])
        points = []
        for idx, rule in enumerate(rules):
            rule_id_str = str(rule_ids[idx])
            # Generate UUID from rule ID (Qdrant requires UUID or int)
            rule_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, rule_id_str))
            payload = {
                "rule_id": rule_id_str,  # Keep original ID in payload
                "text": rule.text,
                "category": rule.category,
                "risk_level": rule.risk_level,
                "threshold": rule.threshold,
            }
            points.append(
                qmodels.PointStruct(
                    id=rule_uuid,
                    vector={"dense": embeddings[idx]},
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(collection_name=self.filter_collection_name, points=points)
        return [str(rid) for rid in rule_ids]

    def search(
        self, query: str, threshold: float | None = None, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        if not query:
            return []
        top_k = top_k or DEFAULT_TOP_K
        threshold = threshold or settings.RAG_THRESHOLD
        dense_vector = self._embed([query])[0]
        scored_points = self.client.search(
            collection_name=self.main_collection_name,
            query_vector=("dense", dense_vector),
            with_payload=True,
            limit=top_k * 2,
        )
        query_tokens = self._tokenize(query)
        results: list[dict[str, Any]] = []
        for point in scored_points:
            payload = point.payload or {}
            text = payload.get("text", "")
            doc_tokens = self._tokenize(text)
            lexical = self._lexical_score(query_tokens, doc_tokens)
            dense_score = float(point.score)
            # Normalize dense cosine score (higher is better) into 0-1 range
            normalized_dense = max(0.0, min(1.0, dense_score))
            relevance = 0.6 * normalized_dense + 0.4 * lexical
            if relevance < threshold:
                continue
            results.append(
                {
                    "document_id": str(point.id),
                    "text": text,
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                    "relevance_score": relevance,
                }
            )
        results.sort(key=lambda item: item["relevance_score"], reverse=True)
        return results[:top_k]

    async def find_matching_rules(self, text: str, n_results: int = 10) -> list[FilterMatch]:
        if not text:
            return []
        dense_vector = self._embed([text])[0]
        scored_points = self.client.search(
            collection_name=self.filter_collection_name,
            query_vector=("dense", dense_vector),
            with_payload=True,
            limit=n_results,
        )
        matches: list[FilterMatch] = []
        for point in scored_points:
            payload = point.payload or {}
            # Get original rule_id from payload (point.id is UUID in Qdrant)
            original_rule_id = payload.get("rule_id", str(point.id))
            matches.append(
                FilterMatch(
                    rule_id=original_rule_id,
                    rule_text=str(payload.get("text", "")),
                    category=str(payload.get("category", "other")),
                    risk_level=int(payload.get("risk_level", 0)),
                    relevance_score=float(point.score),
                )
            )
        return matches

    async def link_rule_to_documents(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ) -> list[RuleDocument]:
        points = []
        links: list[RuleDocument] = []
        for document_id in document_ids:
            # Generate deterministic UUID from rule_id and document_id
            # Qdrant requires UUID or int, not arbitrary strings
            link_id_str = f"{rule_id}_{document_id}"
            link_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, link_id_str)

            payload = {
                "id": link_id_str,  # Keep string ID in payload for readability
                "rule_id": rule_id,
                "document_id": document_id,
                "is_approved": is_approved,
            }
            points.append(
                qmodels.PointStruct(
                    id=str(link_uuid),  # Use UUID string for Qdrant ID
                    vector={"dense": [1.0]},
                    payload=payload,
                )
            )
            links.append(
                RuleDocument(rule_id=rule_id, document_id=document_id, is_approved=is_approved)
            )
        if points:
            self.client.upsert(collection_name=self.links_collection_name, points=points)
        return links

    async def remove_rule_document_link(self, rule_id: str, document_id: str) -> bool:
        # Generate the same UUID that was used during creation
        link_id_str = f"{rule_id}_{document_id}"
        link_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, link_id_str))

        self.client.delete(
            collection_name=self.links_collection_name,
            points_selector=qmodels.PointIdsList(points=[link_uuid]),
        )
        return True

    async def update_link_approval(
        self, rule_id: str, document_id: str, is_approved: bool
    ) -> RuleDocument | None:
        # Generate the same UUID that was used during creation
        link_id_str = f"{rule_id}_{document_id}"
        link_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, link_id_str))

        # Check if link exists
        records = self.client.retrieve(
            collection_name=self.links_collection_name,
            ids=[link_uuid],
            with_payload=True,
        )
        if not records:
            return None

        # Update the payload
        self.client.set_payload(
            collection_name=self.links_collection_name,
            payload={"is_approved": is_approved},
            points=[link_uuid],
        )

        # Get relevance_score from existing payload
        payload = records[0].payload or {}
        relevance_score = payload.get("relevance_score")

        return RuleDocument(
            rule_id=rule_id,
            document_id=document_id,
            is_approved=is_approved,
            relevance_score=relevance_score,
        )

    async def get_all_rules(self) -> list[dict[str, Any]]:
        return await self._scroll_collection(self.filter_collection_name)

    async def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        # Convert rule_id to UUID (Qdrant stores UUIDs, not string IDs)
        rule_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, rule_id))
        records = self.client.retrieve(
            collection_name=self.filter_collection_name,
            ids=[rule_uuid],
            with_payload=True,
        )
        if not records:
            return None
        record = records[0]
        payload = record.payload or {}
        # Return original rule_id from payload (or fallback to UUID)
        original_id = payload.get("rule_id", str(record.id))
        return {"id": original_id, **payload}

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        filter_conditions = [
            qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id))
        ]
        if only_approved:
            filter_conditions.append(
                qmodels.FieldCondition(key="is_approved", match=qmodels.MatchValue(value=True))
            )
        points = self.client.scroll(
            collection_name=self.links_collection_name,
            scroll_filter=qmodels.Filter(must=filter_conditions),
            with_payload=True,
            limit=1000,
        )[0]
        rules: list[dict[str, Any]] = []
        for point in points:
            payload = point.payload or {}
            rule_id = payload.get("rule_id")
            rule = await self.get_rule(rule_id) if rule_id else None
            entry = {"rule_id": rule_id, **payload}
            if rule:
                entry.update(
                    {
                        "rule_text": rule.get("text"),
                        "category": rule.get("category"),
                        "risk_level": rule.get("risk_level"),
                    }
                )
            rules.append(entry)
        return rules

    async def get_documents_for_rule(
        self, rule_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        import time

        from src.monitoring.metrics import content_filter_metrics

        start_time = time.perf_counter()

        filter_conditions = [
            qmodels.FieldCondition(key="rule_id", match=qmodels.MatchValue(value=rule_id))
        ]
        if only_approved:
            filter_conditions.append(
                qmodels.FieldCondition(key="is_approved", match=qmodels.MatchValue(value=True))
            )
        points = self.client.scroll(
            collection_name=self.links_collection_name,
            scroll_filter=qmodels.Filter(must=filter_conditions),
            with_payload=True,
            limit=1000,
        )[0]
        documents: list[dict[str, Any]] = []
        for point in points:
            payload = point.payload or {}
            document_id = payload.get("document_id")
            if not document_id:
                continue
            # Convert document_id to UUID (Qdrant stores UUIDs)
            doc_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, document_id))
            doc_record = self.client.retrieve(
                collection_name=self.main_collection_name,
                ids=[doc_uuid],
                with_payload=True,
            )
            doc_payload = doc_record[0].payload if doc_record else {}
            documents.append(
                {
                    "document_id": document_id,
                    "text": doc_payload.get("text"),
                    "metadata": {k: v for k, v in (doc_payload or {}).items() if k != "text"},
                    **payload,
                }
            )

        # Record metrics for linked documents retrieval
        latency_seconds = time.perf_counter() - start_time
        content_filter_metrics.record_linked_docs_retrieval(
            rule_id=rule_id, latency_seconds=latency_seconds, num_docs=len(documents)
        )

        return documents

    async def get_all_links(self) -> list[dict[str, Any]]:
        points = self.client.scroll(
            collection_name=self.links_collection_name,
            with_payload=True,
            limit=1000,
        )[0]
        return [{"id": str(point.id), **(point.payload or {})} for point in points]

    async def get_collection_stats(self) -> dict[str, Any]:
        main_count = self.client.count(self.main_collection_name, exact=True).count
        filter_count = self.client.count(self.filter_collection_name, exact=True).count
        return {
            "main_collection": {"total_documents": main_count},
            "filter_collection": {"total_rules": filter_count},
        }

    async def get_rule_threshold(self, rule_text: str) -> float:
        dense_vector = self._embed([rule_text])[0]
        scored_points = self.client.search(
            collection_name=self.filter_collection_name,
            query_vector=("dense", dense_vector),
            with_payload=True,
            limit=1,
        )
        if scored_points:
            payload = scored_points[0].payload or {}
            return float(payload.get("threshold", 0.75))
        return 0.75

    def reset_documents_collection(self) -> None:
        if self._qdrant_collection_exists(self.main_collection_name):
            self.client.delete_collection(self.main_collection_name)
        self._ensure_collection(
            self.main_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(
                    size=self.vector_size, distance=qmodels.Distance.COSINE
                )
            },
        )

    def reset_filter_collection(self) -> None:
        if self._qdrant_collection_exists(self.filter_collection_name):
            self.client.delete_collection(self.filter_collection_name)
        self._ensure_collection(
            self.filter_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(
                    size=self.vector_size, distance=qmodels.Distance.COSINE
                )
            },
        )

    def reset_links_collection(self) -> None:
        if self._qdrant_collection_exists(self.links_collection_name):
            self.client.delete_collection(self.links_collection_name)
        self._ensure_collection(
            self.links_collection_name,
            vectors_config={
                "dense": qmodels.VectorParams(size=1, distance=qmodels.Distance.COSINE)
            },
        )

    async def _scroll_collection(self, collection_name: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=collection_name,
                with_payload=True,
                limit=100,
                offset=offset,
            )
            for point in points:
                payload = point.payload or {}
                if "text" not in payload and collection_name == self.main_collection_name:
                    payload["text"] = ""
                # Get original ID from payload (Qdrant uses UUID as point.id)
                if collection_name == self.filter_collection_name:
                    original_id = payload.get("rule_id", str(point.id))
                elif collection_name == self.main_collection_name:
                    original_id = payload.get("document_id", str(point.id))
                else:
                    original_id = str(point.id)
                records.append({"id": original_id, **payload})
            if offset is None:
                break
        return records

    async def get_all_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.main_collection_name,
                with_payload=True,
                limit=100,
                offset=offset,
            )
            for point in points:
                payload = point.payload or {}
                # Get original document_id from payload (Qdrant stores UUIDs as point IDs)
                doc_id = payload.get("document_id", str(point.id))
                documents.append(
                    {
                        "document_id": doc_id,
                        "text": payload.get("text", ""),
                        "metadata": {k: v for k, v in payload.items() if k != "text"},
                    }
                )
            if offset is None:
                break
        return documents


class VectorDBService(VectorDBClient):
    """Facade that selects vector DB implementation based on settings."""

    def __init__(
        self,
        provider: str | None = None,
        client: VectorDBClient | None = None,
        **kwargs: Any,
    ) -> None:
        if os.environ.get("AVI_TEST_MODE") == "1":
            self._client: VectorDBClient = InMemoryVectorDB()
            self.provider = "memory"
            return

        if client is not None:
            self._client = client
            self.provider = getattr(client, "provider", "custom")
            return

        provider_name = (provider or settings.VECTOR_DB_PROVIDER or "chroma").lower()
        if provider_name == "chroma":
            self._client = ChromaVectorDBService(**kwargs)
        elif provider_name == "qdrant":
            self._client = QdrantVectorDBService(**kwargs)
        else:
            raise ValueError(f"Unsupported vector DB provider: {provider_name}")
        self.provider = provider_name

    # Delegate protocol methods
    def search(
        self, query: str, threshold: float | None = None, top_k: int | None = None
    ) -> list[dict[str, Any]]:
        return self._client.search(query, threshold=threshold, top_k=top_k)

    def add_documents(self, documents: list[dict[str, Any]], batch_size: int = 100) -> None:
        self._client.add_documents(documents, batch_size=batch_size)

    def add_filter_rule(self, rule: FilteredContent) -> str:
        return self._client.add_filter_rule(rule)

    def add_filter_rules_batch(
        self, rules: list[FilteredContent], ids: list[str] | None = None
    ) -> list[str]:
        return self._client.add_filter_rules_batch(rules, ids=ids)

    async def find_matching_rules(self, text: str, n_results: int = 10) -> list[FilterMatch]:
        return await self._client.find_matching_rules(text, n_results=n_results)

    async def link_rule_to_documents(
        self, rule_id: str, document_ids: list[str], is_approved: bool = True
    ) -> list[RuleDocument]:
        return await self._client.link_rule_to_documents(
            rule_id, document_ids, is_approved=is_approved
        )

    async def remove_rule_document_link(self, rule_id: str, document_id: str) -> bool:
        return await self._client.remove_rule_document_link(rule_id, document_id)

    async def get_all_rules(self) -> list[dict[str, Any]]:
        return await self._client.get_all_rules()

    async def get_rule(self, rule_id: str) -> dict[str, Any] | None:
        return await self._client.get_rule(rule_id)

    async def get_rules_for_document(
        self, document_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        return await self._client.get_rules_for_document(document_id, only_approved=only_approved)

    async def get_documents_for_rule(
        self, rule_id: str, only_approved: bool = True
    ) -> list[dict[str, Any]]:
        return await self._client.get_documents_for_rule(rule_id, only_approved=only_approved)

    async def get_all_links(self) -> list[dict[str, Any]]:
        return await self._client.get_all_links()

    async def get_collection_stats(self) -> dict[str, Any]:
        return await self._client.get_collection_stats()

    async def get_rule_threshold(self, rule_text: str) -> float:
        return await self._client.get_rule_threshold(rule_text)

    def reset_documents_collection(self) -> None:
        self._client.reset_documents_collection()

    def reset_filter_collection(self) -> None:
        self._client.reset_filter_collection()

    def reset_links_collection(self) -> None:
        self._client.reset_links_collection()

    async def get_all_documents(self) -> list[dict[str, Any]]:
        return await self._client.get_all_documents()
