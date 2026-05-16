"""Utility classes for reranking retrieved documents."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable, Sequence
from time import perf_counter

from config.settings import settings
from src.utils.logger import logger

try:  # Optional dependency for production usage
    from sentence_transformers import CrossEncoder  # type: ignore
except Exception:  # pragma: no cover - dependency may be unavailable in tests
    CrossEncoder = None  # type: ignore

from src.monitoring.observability import observe_rerank_latency


class Reranker:
    """Wrapper around a cross-encoder model used for reranking search results."""

    def __init__(
        self,
        model_name: str,
        *,
        enabled: bool = True,
        score_threshold: float = 0.0,
        max_length: int = 512,
    ) -> None:
        self.model_name = model_name
        self._model = None
        self.score_threshold = score_threshold
        self._enabled = enabled and bool(model_name)
        self.max_length = max_length
        self._use_dummy_model = os.environ.get("AVI_TEST_MODE") == "1"

        # Production environment must not use dummy reranker
        if settings.is_production_environment() and self._use_dummy_model:
            raise RuntimeError(
                "Dummy reranker mode (AVI_TEST_MODE=1) is enabled in production environment. "
                "This is not allowed. Disable AVI_TEST_MODE in production."
            )

        if not self._enabled:
            logger.info("Document reranking is disabled via configuration.")
        elif self._use_dummy_model:
            logger.debug("Using dummy reranker scoring in test mode.")
        elif CrossEncoder is None:
            logger.warning(
                "sentence-transformers is not available. Falling back to vector similarity order."
            )

    @property
    def is_enabled(self) -> bool:
        """Return True if reranking should be applied."""

        if not self._enabled:
            return False
        if self._use_dummy_model:
            return True
        return CrossEncoder is not None

    def _load_model(self) -> None:
        if self._model is None and CrossEncoder is not None:
            device = settings.RERANK_DEVICE
            logger.info(f"Loading reranker model: {self.model_name} on device: {device}")
            self._model = CrossEncoder(self.model_name, max_length=self.max_length, device=device)

    def _predict_scores(self, pairs: Sequence[Sequence[str]]) -> list[float]:
        if self._use_dummy_model:
            # Deterministic lightweight scoring for tests
            return [float(len(pair[1] or "")) for pair in pairs]

        if CrossEncoder is None:
            return [0.0 for _ in pairs]

        self._load_model()
        assert self._model is not None  # for type checkers
        return list(self._model.predict(pairs))

    async def rerank(self, query: str, documents: Iterable[dict]) -> list[dict]:
        """Return documents sorted by descending rerank score."""

        docs = list(documents)
        if not docs or not self.is_enabled:
            return docs

        start_time = perf_counter()

        pairs = [(query, doc.get("text", "")) for doc in docs]
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, self._predict_scores, pairs)

        reranked: list[dict] = []
        for doc, score in zip(docs, scores, strict=False):
            updated_doc = dict(doc)
            updated_doc["rerank_score"] = float(score)
            reranked.append(updated_doc)

        reranked.sort(key=lambda item: item.get("rerank_score", 0.0), reverse=True)

        if self.score_threshold > 0:
            reranked = [
                doc for doc in reranked if doc.get("rerank_score", 0.0) >= self.score_threshold
            ]

        observe_rerank_latency(self.model_name or "unknown", perf_counter() - start_time)
        return reranked
