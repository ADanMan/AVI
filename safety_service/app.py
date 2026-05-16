"""FastAPI application exposing the heuristic safety service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.utils.logger import logger

from .grpc_server import start_grpc_server, stop_grpc_server
from .model import LlamaGuardHeuristic
from .schemas import HealthResponse, SafetyRequest, SafetyResponse
from .settings import ServiceSettings, get_settings


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    settings = get_settings()
    model = LlamaGuardHeuristic.from_file(settings.blocklist_path)
    app.state.safety_model = model
    app.state.settings = settings

    grpc_server = None
    if settings.grpc_enabled:
        try:
            grpc_server = await start_grpc_server(model, settings)
            if grpc_server:
                logger.info(
                    "gRPC safety server started on %s:%s",
                    settings.grpc_host,
                    settings.grpc_port,
                )
        except Exception as exc:  # pragma: no cover - logging only
            logger.warning("Failed to start gRPC server: %s", exc)
            grpc_server = None

    yield {"grpc_server": grpc_server}

    await stop_grpc_server(grpc_server)


def create_app(settings: ServiceSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Safety Service", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/v1/check", response_model=SafetyResponse)
    async def check(payload: SafetyRequest) -> SafetyResponse:
        model: LlamaGuardHeuristic = app.state.safety_model
        judgement = model.evaluate(payload.text)
        return SafetyResponse(
            safe=judgement.safe,
            score=judgement.score,
            reasons=list(judgement.reasons),
            sanitized_text=judgement.sanitized_text,
            model=settings.service_name,
            evaluated_at=datetime.utcnow(),
        )

    return app


app = create_app()


__all__ = ["app", "create_app"]
