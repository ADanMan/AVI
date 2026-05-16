"""
Rate limiting for API endpoints.

Uses SlowAPI for rate limiting with optional Redis backend.
"""

from __future__ import annotations

import hashlib

from fastapi import Request

from config.settings import settings
from src.utils.logger import logger

# Import SlowAPI with graceful fallback
try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("slowapi not installed. Rate limiting will be disabled.")


def get_limiter_key(request: Request) -> str:
    """
    Get rate limit key from API key or IP address.

    Prefers API key for authenticated requests, falls back to IP address.

    Args:
        request: FastAPI request object

    Returns:
        str: Rate limit key in format "apikey:<hash>" or "ip:<address>"
    """
    # Try API key first (if authenticated)
    api_key = request.headers.get(settings.API_KEY_HEADER, None)
    if api_key:
        # Use hash of API key (first 16 chars for grouping)
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"apikey:{key_hash}"

    # Fall back to IP address
    if SLOWAPI_AVAILABLE:
        return f"ip:{get_remote_address(request)}"
    return "ip:unknown"


def get_storage_uri() -> str:
    """
    Get storage URI for rate limiter.

    Checks for Redis availability, falls back to in-memory storage.

    Returns:
        str: Storage URI (redis:// or memory://)
    """
    # Check if Redis is enabled and available
    redis_url = getattr(settings, "REDIS_URL", None)
    if redis_url:
        try:
            import redis

            # Test connection with short timeout
            r = redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
            r.ping()
            logger.info(f"Using Redis for rate limiting: {redis_url}")
            return redis_url
        except ImportError:
            logger.warning("redis package not installed. Install with: pip install redis")
        except Exception as e:
            logger.warning(f"Redis unavailable, using memory storage: {e}")

    logger.info("Using in-memory storage for rate limiting")
    return "memory://"


def create_limiter() -> Limiter | None:
    """
    Create and configure rate limiter instance.

    Returns:
        Limiter instance if SlowAPI is available, None otherwise
    """
    if not SLOWAPI_AVAILABLE:
        logger.warning("Rate limiting disabled - slowapi not installed")
        return None

    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting disabled by configuration")
        return None

    try:
        limiter_instance = Limiter(
            key_func=get_limiter_key,
            storage_uri=get_storage_uri(),
            default_limits=[settings.RATE_LIMIT_DEFAULT],
        )
        logger.info(f"Rate limiter initialized with default limit: {settings.RATE_LIMIT_DEFAULT}")
        return limiter_instance
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")
        return None


# Global limiter instance
limiter = create_limiter()


def get_limiter() -> Limiter | None:
    """
    Get the global limiter instance.

    Returns:
        Limiter instance or None if unavailable
    """
    return limiter


__all__ = ["get_limiter", "get_limiter_key", "limiter"]
