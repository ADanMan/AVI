"""Pre-flight health checks for application dependencies."""

from __future__ import annotations

import asyncio
import shutil
from typing import Any

from config.settings import settings
from src.utils.logger import logger


class HealthCheckResult:
    """Result of a health check operation."""

    def __init__(
        self,
        name: str,
        status: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """
        Initialize health check result.

        Args:
            name: Name of the check
            status: Status ("healthy", "degraded", "unhealthy")
            message: Optional message
            details: Optional additional details
        """
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}

    def is_healthy(self) -> bool:
        """Return True if check passed."""
        return self.status == "healthy"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
        }
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


class HealthChecker:
    """Pre-flight health checker for application dependencies."""

    def __init__(self):
        """Initialize health checker."""
        self.min_disk_space_gb = 0.5  # Minimum 500MB free space

    async def check_all(self) -> dict[str, HealthCheckResult]:
        """
        Run all health checks.

        Returns:
            Dictionary mapping check name to result
        """
        checks = {
            "disk_space": self.check_disk_space(),
            "llm_config": self.check_llm_config(),
            "vector_db_config": self.check_vector_db_config(),
        }

        # Run optional checks if configured
        if settings.REDIS_URL or (settings.CACHE_BACKEND == "redis"):
            checks["redis"] = await self.check_redis()

        results = {}
        for name, check in checks.items():
            if asyncio.iscoroutine(check):
                results[name] = await check
            else:
                results[name] = check

        return results

    def check_disk_space(self) -> HealthCheckResult:
        """Check available disk space."""
        try:
            data_dir = settings.DATA_DIR
            if not data_dir.exists():
                return HealthCheckResult(
                    name="disk_space",
                    status="degraded",
                    message=f"Data directory does not exist: {data_dir}",
                )

            stat = shutil.disk_usage(data_dir)
            free_gb = stat.free / (1024**3)

            if free_gb < self.min_disk_space_gb:
                return HealthCheckResult(
                    name="disk_space",
                    status="unhealthy",
                    message=f"Low disk space: {free_gb:.2f}GB free (minimum: {self.min_disk_space_gb}GB)",
                    details={
                        "free_gb": round(free_gb, 2),
                        "total_gb": round(stat.total / (1024**3), 2),
                    },
                )

            return HealthCheckResult(
                name="disk_space",
                status="healthy",
                message=f"{free_gb:.2f}GB free",
                details={
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(stat.total / (1024**3), 2),
                },
            )

        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return HealthCheckResult(
                name="disk_space",
                status="unhealthy",
                message=f"Failed to check disk space: {e}",
            )

    def check_llm_config(self) -> HealthCheckResult:
        """Check LLM configuration."""
        try:
            if not settings.MAIN_LLM_API_KEY:
                if settings.allows_missing_api_keys():
                    return HealthCheckResult(
                        name="llm_config",
                        status="degraded",
                        message="LLM API key not configured (allowed in dev/test)",
                    )
                return HealthCheckResult(
                    name="llm_config",
                    status="unhealthy",
                    message="LLM API key not configured",
                )

            if not settings.MAIN_LLM_MODEL:
                return HealthCheckResult(
                    name="llm_config",
                    status="unhealthy",
                    message="LLM model not configured",
                )

            return HealthCheckResult(
                name="llm_config",
                status="healthy",
                message=f"LLM configured: {settings.MAIN_LLM_MODEL}",
                details={
                    "model": settings.MAIN_LLM_MODEL,
                    "api_base": settings.MAIN_LLM_API_BASE,
                },
            )

        except Exception as e:
            logger.error(f"LLM config check failed: {e}")
            return HealthCheckResult(
                name="llm_config",
                status="unhealthy",
                message=f"Failed to check LLM config: {e}",
            )

    def check_vector_db_config(self) -> HealthCheckResult:
        """Check vector DB configuration."""
        try:
            provider = settings.VECTOR_DB_PROVIDER

            if provider not in {"chroma", "qdrant"}:
                return HealthCheckResult(
                    name="vector_db_config",
                    status="unhealthy",
                    message=f"Invalid vector DB provider: {provider}",
                )

            if provider == "qdrant" and settings.QDRANT_HOST:
                # Remote Qdrant - cannot easily check without connecting
                return HealthCheckResult(
                    name="vector_db_config",
                    status="healthy",
                    message=f"Qdrant configured (remote): {settings.QDRANT_HOST}",
                    details={"provider": "qdrant", "host": settings.QDRANT_HOST},
                )

            # Local storage
            db_path = settings.VECTOR_DB_PATH if provider == "chroma" else settings.QDRANT_PATH
            return HealthCheckResult(
                name="vector_db_config",
                status="healthy",
                message=f"Vector DB configured: {provider}",
                details={"provider": provider, "path": str(db_path)},
            )

        except Exception as e:
            logger.error(f"Vector DB config check failed: {e}")
            return HealthCheckResult(
                name="vector_db_config",
                status="unhealthy",
                message=f"Failed to check vector DB config: {e}",
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        try:
            # Try to import redis
            try:
                import redis.asyncio as redis
            except ImportError:
                return HealthCheckResult(
                    name="redis",
                    status="unhealthy",
                    message="Redis client library not installed",
                )

            # Build Redis URL
            if settings.REDIS_URL:
                url = settings.REDIS_URL
            else:
                url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

            # Try to connect
            client = redis.from_url(url, decode_responses=True)
            try:
                await asyncio.wait_for(client.ping(), timeout=2.0)
                return HealthCheckResult(
                    name="redis",
                    status="healthy",
                    message="Redis connection successful",
                    details={"url": url},
                )
            except asyncio.TimeoutError:
                return HealthCheckResult(
                    name="redis",
                    status="unhealthy",
                    message="Redis connection timeout",
                )
            except Exception as e:
                return HealthCheckResult(
                    name="redis",
                    status="unhealthy",
                    message=f"Redis connection failed: {e}",
                )
            finally:
                await client.aclose()

        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            return HealthCheckResult(
                name="redis",
                status="unhealthy",
                message=f"Failed to check Redis: {e}",
            )

    async def run_startup_checks(self) -> bool:
        """
        Run all health checks at startup and log results.

        Returns:
            True if all critical checks passed, False otherwise
        """
        logger.info("Running pre-flight health checks...")

        results = await self.check_all()

        all_healthy = True
        critical_failed = False

        for name, result in results.items():
            status_emoji = (
                "✅" if result.is_healthy() else ("⚠️" if result.status == "degraded" else "❌")
            )
            logger.info(f"{status_emoji} {result.name}: {result.status} - {result.message or 'OK'}")

            if result.status == "unhealthy":
                # Disk space and LLM config are critical
                if name in {"disk_space", "llm_config"}:
                    critical_failed = True
                all_healthy = False

        if critical_failed:
            logger.error("Critical health checks failed! Application may not function correctly.")
            return False
        elif not all_healthy:
            logger.warning("Some health checks failed, but application can continue.")
            return True
        else:
            logger.info("All health checks passed ✅")
            return True


# Create singleton instance
health_checker = HealthChecker()


__all__ = ["HealthCheckResult", "HealthChecker", "health_checker"]
