"""Runtime configuration for the lightweight safety microservice."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class ServiceSettings(BaseSettings):
    """Settings describing how the safety microservice should run."""

    host: str = Field(default="0.0.0.0", description="HTTP host binding")
    port: int = Field(default=8001, description="HTTP port")

    grpc_enabled: bool = Field(default=True, description="Expose gRPC alongside HTTP")
    grpc_host: str = Field(default="0.0.0.0", description="gRPC host binding")
    grpc_port: int = Field(default=50051, description="gRPC port")

    service_name: str = Field(default="llamaguard-lite", description="Reported model name")
    blocklist_path: str | None = Field(
        default=None, description="Optional path to a custom comma-separated blocklist"
    )

    class Config:
        env_prefix = "SAFETY_SERVICE_"
        case_sensitive = False


@lru_cache(maxsize=1)
def get_settings() -> ServiceSettings:
    """Return cached instance of :class:`ServiceSettings`."""

    return ServiceSettings()


__all__ = ["ServiceSettings", "get_settings"]
