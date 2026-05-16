"""Utilities for moderating streaming LLM responses before they reach the client."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from src.core.content_filter import ContentFilterService, create_content_filter_service
from src.models.schemas import FilterResult
from src.utils.logger import logger


class StreamingGuardMode(str, Enum):
    """Available moderation strategies for streaming responses."""

    RULE_ONLY = "rule-only"
    LLM_ONLY = "llm-only"
    HYBRID = "hybrid"
    BYPASS = "bypass"

    @classmethod
    def from_value(cls, value: Any | None) -> StreamingGuardMode:
        """Return a valid guard mode, falling back to :class:`StreamingGuardMode.HYBRID`."""

        if isinstance(value, cls):
            return value
        if isinstance(value, str) and value.strip():
            candidate = value.strip().lower()
        else:
            candidate = cls.HYBRID.value
        try:
            return cls(candidate)
        except ValueError:
            logger.warning(
                "Unknown streaming guard mode '{}'. Falling back to '{}'.",
                candidate,
                cls.HYBRID.value,
            )
            return cls.HYBRID


@dataclass
class StreamingGuardMetrics:
    """Basic counters describing how the guard behaved for a response."""

    processed_chunks: int = 0
    flagged_chunks: int = 0
    sanitized_chunks: int = 0
    blocked_chunks: int = 0
    llm_calls: int = 0

    def to_dict(self) -> dict[str, int]:
        """Serialize metrics to a primitive dictionary."""

        return asdict(self)


@dataclass
class StreamingGuardDecision:
    """Result of handling a single chunk by the guard."""

    allowed: bool
    content: str = ""
    reason: str | None = None
    filtered: bool = False
    stop_stream: bool = False
    filter_result: FilterResult | None = None

    def to_payload(self) -> dict[str, Any]:
        """Convert a decision into a JSON-serializable payload for SSE."""

        payload: dict[str, Any] = {"chunk": self.content}
        if self.filtered:
            payload["filtered"] = True
        if self.reason:
            payload["reason"] = self.reason
        if self.filter_result and self.filter_result.matches:
            payload["matches"] = [match.dict() for match in self.filter_result.matches]
        return payload


class StreamingGuard:
    """Moderates streaming chunks with configurable safety strategies."""

    def __init__(
        self,
        content_filter: ContentFilterService | None = None,
        mode: Any | None = None,
        buffer_limit: int = 2000,
    ) -> None:
        self.content_filter = content_filter or create_content_filter_service()
        self.mode = StreamingGuardMode.from_value(mode)
        self.buffer_limit = max(buffer_limit, 256)
        self.metrics = StreamingGuardMetrics()
        self._buffer: str = ""
        self._stopped: bool = False

    @property
    def stopped(self) -> bool:
        """Indicate whether the guard has requested the stream to stop."""

        return self._stopped

    def reset(self) -> None:
        """Reset the guard state between streaming sessions."""

        self.metrics = StreamingGuardMetrics()
        self._buffer = ""
        self._stopped = False

    async def process_chunk(self, chunk: str) -> StreamingGuardDecision:
        """Process a single chunk emitted by the LLM."""

        if self._stopped:
            logger.debug("StreamingGuard already stopped. Ignoring incoming chunk.")
            return StreamingGuardDecision(
                allowed=False,
                content="",
                stop_stream=True,
                reason="stream_already_stopped",
            )

        self.metrics.processed_chunks += 1
        if not chunk:
            return StreamingGuardDecision(allowed=True, content="")

        self._buffer = (self._buffer + chunk)[-self.buffer_limit :]

        if self.mode is StreamingGuardMode.BYPASS:
            return StreamingGuardDecision(allowed=True, content=chunk)

        filter_result: FilterResult | None = None
        matches_detected = False
        if self.mode in {StreamingGuardMode.RULE_ONLY, StreamingGuardMode.HYBRID}:
            filter_result = await self._check_rules(self._buffer)
            matches_detected = bool(filter_result and filter_result.matches)
            if matches_detected:
                self.metrics.flagged_chunks += 1

        sanitized_chunk: str | None = None
        if self.mode in {StreamingGuardMode.LLM_ONLY, StreamingGuardMode.HYBRID}:
            sanitized_chunk = await self._sanitize_with_llm(chunk)
            if sanitized_chunk is not None:
                self.metrics.llm_calls += 1

        if matches_detected:
            reason = "rule_violation"
            if self.mode is StreamingGuardMode.RULE_ONLY:
                self.metrics.blocked_chunks += 1
                self._stopped = True
                return StreamingGuardDecision(
                    allowed=False,
                    stop_stream=True,
                    reason=reason,
                    filter_result=filter_result,
                )

            if sanitized_chunk and sanitized_chunk.strip():
                filtered = sanitized_chunk != chunk
                if filtered:
                    self.metrics.sanitized_chunks += 1
                return StreamingGuardDecision(
                    allowed=True,
                    content=sanitized_chunk,
                    filtered=filtered,
                    reason=reason,
                    filter_result=filter_result,
                )

            logger.warning(
                "Rule violation detected but no sanitized chunk available. Stopping stream.",
            )
            self.metrics.blocked_chunks += 1
            self._stopped = True
            return StreamingGuardDecision(
                allowed=False,
                stop_stream=True,
                reason=reason,
                filter_result=filter_result,
            )

        if self.mode is StreamingGuardMode.LLM_ONLY and sanitized_chunk is not None:
            filtered = sanitized_chunk != chunk
            reason: str | None
            if filtered:
                self.metrics.sanitized_chunks += 1
                reason = "llm_sanitized"
            else:
                reason = None
            return StreamingGuardDecision(
                allowed=True,
                content=sanitized_chunk,
                filtered=filtered,
                reason=reason,
            )

        return StreamingGuardDecision(allowed=True, content=chunk)

    async def _check_rules(self, text: str) -> FilterResult:
        """Run the rule-based content filter on the aggregated text."""

        try:
            return await self.content_filter.check_content(
                text,
                use_llm=False,
                use_linked_docs=False,
                is_input=False,
            )
        except Exception as error:
            logger.error("StreamingGuard rule analysis failed: {}", error)
            return FilterResult(original_text=text, was_modified=False, matches=[])

    async def _sanitize_with_llm(self, text: str) -> str | None:
        """Use the configured safety LLM to sanitize a chunk."""

        safety_llm = getattr(self.content_filter, "safety_llm", None)
        if safety_llm is None:
            if self.mode is StreamingGuardMode.LLM_ONLY:
                logger.warning(
                    "Streaming guard in LLM-only mode but safety LLM is not configured. Bypassing sanitization.",
                )
            return None

        try:
            sanitized = await safety_llm.generate_response(text, context=None)
            refresh = getattr(self.content_filter, "_refresh_active_mode", None)
            if callable(refresh):
                refresh()
            return sanitized
        except Exception as error:
            logger.error("StreamingGuard safety LLM failed: {}", error)
            return None
