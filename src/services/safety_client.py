"""Client helpers for interacting with the safety microservice over HTTP or gRPC."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from src.utils.logger import logger

try:  # pragma: no cover - optional dependency
    import grpc
except Exception:  # pragma: no cover - dependency missing
    grpc = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from safety_service.grpc import safety_pb2, safety_pb2_grpc
except Exception:  # pragma: no cover - dependency missing
    safety_pb2 = None  # type: ignore
    safety_pb2_grpc = None  # type: ignore


@dataclass
class SafetyCheckResult:
    safe: bool
    score: float
    reasons: Sequence[str]
    sanitized_text: str
    model: str | None = None
    raw_payload: dict[str, Any] | None = None


class SafetyServiceError(RuntimeError):
    """Raised when communication with the safety service fails."""


class SafetyServiceClient:
    """High-level client capable of speaking HTTP and gRPC."""

    def __init__(
        self,
        service_url: str | None,
        *,
        timeout: float = 5.0,
        retries: int = 2,
        http_endpoint: str | None = None,
        grpc_endpoint: str | None = None,
    ) -> None:
        http_url, grpc_url = self._parse_service_url(service_url)
        self.http_endpoint = http_endpoint or http_url
        self.grpc_endpoint = grpc_endpoint or grpc_url
        self.timeout = timeout
        self.retries = max(0, retries)
        self._grpc_stub = None
        self._grpc_channel = None
        if self.http_endpoint is None and self.grpc_endpoint is None:
            raise ValueError("Safety service endpoint is not configured.")

    @staticmethod
    def _parse_service_url(value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        http_url: str | None = None
        grpc_url: str | None = None
        for chunk in str(value).split(","):
            candidate = chunk.strip()
            if not candidate:
                continue
            if candidate.startswith("grpc://"):
                grpc_url = candidate[len("grpc://") :]
            elif candidate.startswith("grpcs://"):
                grpc_url = candidate[len("grpcs://") :]
            else:
                http_url = candidate.rstrip("/")
        return http_url, grpc_url

    async def close(self) -> None:
        if self._grpc_channel is not None:
            await self._grpc_channel.close()
            self._grpc_channel = None
            self._grpc_stub = None

    async def _get_grpc_stub(self):  # pragma: no cover - network helper
        if self.grpc_endpoint is None or grpc is None or safety_pb2_grpc is None:
            return None
        if self._grpc_stub is not None:
            return self._grpc_stub
        self._grpc_channel = grpc.aio.insecure_channel(self.grpc_endpoint)
        self._grpc_stub = safety_pb2_grpc.SafetyServiceStub(self._grpc_channel)
        return self._grpc_stub

    async def check_health(self) -> bool:
        attempts = []
        stub = await self._get_grpc_stub()
        if stub is not None:
            for _attempt in range(self.retries + 1):
                try:
                    await stub.Health(safety_pb2.HealthCheckRequest(), timeout=self.timeout)
                    return True
                except Exception as exc:  # pragma: no cover - network failure path
                    attempts.append(exc)
        if self.http_endpoint:
            url = f"{self.http_endpoint}/health"
            for _attempt in range(self.retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                        return True
                except Exception as exc:  # pragma: no cover - network failure path
                    attempts.append(exc)
        if attempts:
            logger.warning(
                "Safety service health-check failed after %s attempts: %s",
                len(attempts),
                attempts[-1],
            )
        return False

    async def check_text(self, text: str, context: str | None = None) -> SafetyCheckResult:
        last_error: Exception | None = None
        stub = await self._get_grpc_stub()
        if stub is not None and safety_pb2 is not None:
            payload = safety_pb2.SafetyRequest(text=text, context=context or "")
            for _attempt in range(self.retries + 1):
                try:
                    response = await stub.CheckText(payload, timeout=self.timeout)
                    return SafetyCheckResult(
                        safe=bool(response.safe),
                        score=float(response.score),
                        reasons=list(response.reasons),
                        sanitized_text=str(response.sanitized_text),
                        model=getattr(response, "model", None),
                    )
                except Exception as exc:  # pragma: no cover - network failure path
                    last_error = exc
        if self.http_endpoint:
            url = f"{self.http_endpoint}/v1/check"
            request_payload = {"text": text}
            if context:
                request_payload["context"] = context
            for _attempt in range(self.retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(url, json=request_payload)
                        response.raise_for_status()
                        data = response.json()
                    return SafetyCheckResult(
                        safe=bool(data.get("safe", False)),
                        score=float(data.get("score", 0.0)),
                        reasons=tuple(data.get("reasons", []) or ()),
                        sanitized_text=str(data.get("sanitized_text", text)),
                        model=data.get("model"),
                        raw_payload=data,
                    )
                except Exception as exc:  # pragma: no cover - network failure path
                    last_error = exc
        raise SafetyServiceError(
            "Failed to contact the safety microservice" + (f": {last_error}" if last_error else "")
        )

    async def sanitize_text(self, text: str, context: str | None = None) -> str:
        result = await self.check_text(text, context=context)
        return result.sanitized_text or text


__all__ = ["SafetyCheckResult", "SafetyServiceClient", "SafetyServiceError"]
