"""Asynchronous gRPC server for the safety microservice."""

from __future__ import annotations


try:  # pragma: no cover - optional dependency
    import grpc
except Exception:  # pragma: no cover - gRPC missing at runtime
    grpc = None  # type: ignore

from .model import LlamaGuardHeuristic
from .settings import ServiceSettings


if grpc is not None:  # pragma: no cover - only executed when gRPC is installed
    from .grpc import safety_pb2, safety_pb2_grpc
else:  # pragma: no cover
    safety_pb2 = safety_pb2_grpc = None  # type: ignore


class SafetyServiceGRPC(safety_pb2_grpc.SafetyServiceServicer if safety_pb2_grpc else object):
    """gRPC servicer delegating calls to the heuristic model."""

    def __init__(self, model: LlamaGuardHeuristic, settings: ServiceSettings):
        self._model = model
        self._settings = settings

    async def CheckText(self, request, context):  # pragma: no cover - network code
        judgement = self._model.evaluate(request.text)
        response = safety_pb2.SafetyResponse(
            safe=judgement.safe,
            score=judgement.score,
            reasons=list(judgement.reasons),
            sanitized_text=judgement.sanitized_text,
            model=self._settings.service_name,
        )
        return response

    async def Health(self, request, context):  # pragma: no cover - network code
        return safety_pb2.HealthCheckResponse(status="ok")


async def start_grpc_server(
    model: LlamaGuardHeuristic, settings: ServiceSettings
) -> grpc.aio.Server | None:  # pragma: no cover - network helper
    if grpc is None or safety_pb2_grpc is None:
        return None

    server = grpc.aio.server()
    safety_pb2_grpc.add_SafetyServiceServicer_to_server(
        SafetyServiceGRPC(model=model, settings=settings), server
    )
    listen_addr = f"{settings.grpc_host}:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    await server.start()
    return server


async def stop_grpc_server(server: grpc.aio.Server | None, grace: float = 1.0) -> None:
    if server is None:  # pragma: no cover
        return
    await server.stop(grace)


__all__ = ["start_grpc_server", "stop_grpc_server"]
