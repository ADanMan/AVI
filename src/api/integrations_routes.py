"""
External integrations status API.
Checks availability of Prometheus, MLflow, and other external services.
"""

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config.settings import settings
from src.api.auth import APIKey, Role, optional_auth
from src.utils.logger import logger

router = APIRouter(
    prefix="/integrations",
    tags=["Integrations"],
    responses={404: {"description": "Not found"}},
)


# =====================
# Models
# =====================


class ServiceStatus(BaseModel):
    """Status of an external service."""

    available: bool = Field(..., description="Whether service is available")
    url: str | None = Field(None, description="Service URL if available")
    version: str | None = Field(None, description="Service version if detected")
    error: str | None = Field(None, description="Error message if unavailable")


class IntegrationsStatus(BaseModel):
    """Status of all external integrations."""

    prometheus: ServiceStatus = Field(..., description="Prometheus monitoring")
    mlflow: ServiceStatus = Field(..., description="MLflow experiment tracking")
    grafana: ServiceStatus = Field(..., description="Grafana dashboards")


# =====================
# Helper Functions
# =====================


async def check_prometheus() -> ServiceStatus:
    """Check Prometheus availability."""
    prometheus_url = getattr(settings, "PROMETHEUS_URL", None) or "http://localhost:9090"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{prometheus_url}/api/v1/status/buildinfo")

            if response.status_code == 200:
                data = response.json()
                version = data.get("data", {}).get("version", "unknown")
                return ServiceStatus(
                    available=True,
                    url=prometheus_url,
                    version=version,
                )
    except Exception as e:
        logger.debug(f"Prometheus not available: {e}")

    return ServiceStatus(
        available=False,
        error="Prometheus not reachable",
    )


async def check_mlflow() -> ServiceStatus:
    """Check MLflow availability."""
    mlflow_url = getattr(settings, "MLFLOW_TRACKING_URI", None) or "http://localhost:5000"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{mlflow_url}/health")

            if response.status_code == 200:
                # Try to get version from API
                version_response = await client.get(f"{mlflow_url}/version")
                version = (
                    version_response.json().get("version", "unknown")
                    if version_response.status_code == 200
                    else "unknown"
                )

                return ServiceStatus(
                    available=True,
                    url=mlflow_url,
                    version=version,
                )
    except Exception as e:
        logger.debug(f"MLflow not available: {e}")

    return ServiceStatus(
        available=False,
        error="MLflow not reachable",
    )


async def check_grafana() -> ServiceStatus:
    """Check Grafana availability."""
    grafana_url = getattr(settings, "GRAFANA_URL", None) or "http://localhost:3001"

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{grafana_url}/api/health")

            if response.status_code == 200:
                data = response.json()
                version = data.get("version", "unknown")
                return ServiceStatus(
                    available=True,
                    url=grafana_url,
                    version=version,
                )
    except Exception as e:
        logger.debug(f"Grafana not available: {e}")

    return ServiceStatus(
        available=False,
        error="Grafana not reachable",
    )


# =====================
# Endpoints
# =====================


@router.get("/status", response_model=IntegrationsStatus)
async def get_integrations_status(
    api_key: APIKey | None = Depends(optional_auth(Role.READONLY)),
) -> IntegrationsStatus:
    """
    Check status of all external integrations.

    Returns availability and URLs for:
    - Prometheus (monitoring)
    - MLflow (experiments)
    - Grafana (dashboards)

    The UI uses this to show "Open in X" buttons when services are available.
    """
    # Check all services in parallel
    import asyncio

    prometheus_status, mlflow_status, grafana_status = await asyncio.gather(
        check_prometheus(),
        check_mlflow(),
        check_grafana(),
        return_exceptions=True,
    )

    # Handle exceptions
    if isinstance(prometheus_status, Exception):
        prometheus_status = ServiceStatus(available=False, error=str(prometheus_status))
    if isinstance(mlflow_status, Exception):
        mlflow_status = ServiceStatus(available=False, error=str(mlflow_status))
    if isinstance(grafana_status, Exception):
        grafana_status = ServiceStatus(available=False, error=str(grafana_status))

    return IntegrationsStatus(
        prometheus=prometheus_status,
        mlflow=mlflow_status,
        grafana=grafana_status,
    )


# Export router
__all__ = ["router"]
