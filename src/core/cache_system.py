from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Protocol

from config.settings import settings
from src.monitoring.observability import record_cache_hit, record_cache_miss
from src.utils.logger import logger


try:  # pragma: no cover - optional dependency guard
    from redis import Redis
    from redis.exceptions import RedisError  # type: ignore[misc,assignment]
except ImportError:  # pragma: no cover
    Redis = None  # type: ignore[assignment]

    class RedisError(Exception):  # type: ignore[no-redef]
        """Fallback Redis error when redis-py is unavailable."""


class CacheSystem(Protocol):
    """Protocol describing a cache backend implementation."""

    def get(self, key: str) -> dict[str, Any] | None:
        """Retrieve a cached entry by key."""

    def set(self, key: str, value: dict[str, Any]) -> None:
        """Store a value in the cache using the provided key."""

    def clear(self) -> None:
        """Remove all cached entries."""

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics such as hits, misses, and size."""


class InMemoryCacheSystem:
    """Simple in-memory cache implementation with TTL support."""

    def __init__(self, ttl: int | None = None, max_size: int | None = None):
        self.ttl = ttl or settings.CACHE_TTL
        self.max_size = max_size if max_size is not None else settings.CACHE_MAX_SIZE
        self.cache: dict[str, dict[str, Any]] = {}
        self.stats = {"hits": 0, "misses": 0, "size": 0}

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self.cache.get(key)
        if entry:
            expires_at: datetime = entry["expires_at"]
            if expires_at > datetime.utcnow():
                self.stats["hits"] += 1
                record_cache_hit("memory")
                return entry["value"]

            # Entry expired, remove and fall through to miss handling
            del self.cache[key]
            self._update_size()

        self.stats["misses"] += 1
        record_cache_miss("memory")
        return None

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._cleanup_expired()

        if len(self.cache) >= self.max_size:
            self._evict_oldest()

        self.cache[key] = {
            "value": value,
            "expires_at": datetime.utcnow() + timedelta(seconds=self.ttl),
        }
        self._update_size()

    def clear(self) -> None:
        self.cache.clear()
        self.stats = {"hits": 0, "misses": 0, "size": 0}

    def get_stats(self) -> dict[str, Any]:
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests else 0.0
        return {
            "size": self.stats["size"],
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
        }

    def _cleanup_expired(self) -> None:
        now = datetime.utcnow()
        expired_keys = [key for key, entry in self.cache.items() if entry["expires_at"] <= now]
        for key in expired_keys:
            del self.cache[key]
        if expired_keys:
            self._update_size()

    def _evict_oldest(self) -> None:
        if not self.cache:
            return
        oldest_key = min(self.cache, key=lambda k: self.cache[k]["expires_at"])
        del self.cache[oldest_key]
        self._update_size()

    def _update_size(self) -> None:
        self.stats["size"] = len(self.cache)


class RedisCacheSystem:
    """Redis-backed cache implementation."""

    def __init__(
        self,
        client: Redis | None = None,
        ttl: int | None = None,
        key_prefix: str | None = None,
    ) -> None:
        if Redis is None:
            raise RuntimeError("redis-py is not installed")

        self.ttl = ttl or settings.CACHE_TTL
        self.client: Redis = client or self._create_client()
        default_prefix = (
            settings.APP_NAME.lower().replace(" ", "-") if settings.APP_NAME else "cache"
        )
        self.key_prefix = (key_prefix or f"{default_prefix}-cache").rstrip(":")
        self.index_key = f"{self.key_prefix}:__keys__"
        self.stats = {"hits": 0, "misses": 0, "size": 0}

    def get(self, key: str) -> dict[str, Any] | None:
        redis_key = self._format_key(key)
        try:
            data = self.client.get(redis_key)
        except RedisError as exc:  # pragma: no cover - defensive path
            logger.error(f"Redis GET failed: {exc}")
            self.stats["misses"] += 1
            record_cache_miss("redis")
            return None

        if data is None:
            self.stats["misses"] += 1
            self._untrack_key(redis_key)
            record_cache_miss("redis")
            return None

        self.stats["hits"] += 1
        record_cache_hit("redis")
        return self._deserialize_value(data)

    def set(self, key: str, value: dict[str, Any]) -> None:
        redis_key = self._format_key(key)
        payload = self._serialize_value(value)
        try:
            pipeline = self.client.pipeline()
            pipeline.setex(redis_key, self.ttl, payload)
            pipeline.sadd(self.index_key, redis_key)
            pipeline.execute()
        except RedisError as exc:  # pragma: no cover - defensive path
            logger.error(f"Redis SET failed: {exc}")
            return

        self._refresh_size()

    def clear(self) -> None:
        try:
            tracked_keys = list(self.client.smembers(self.index_key))
            if tracked_keys:
                self.client.delete(*tracked_keys)
            self.client.delete(self.index_key)
        except RedisError as exc:  # pragma: no cover - defensive path
            logger.error(f"Redis CLEAR failed: {exc}")
        finally:
            self.stats = {"hits": 0, "misses": 0, "size": 0}

    def get_stats(self) -> dict[str, Any]:
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests else 0.0
        return {
            "size": self.stats["size"],
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": hit_rate,
        }

    def _create_client(self) -> Redis:
        if settings.REDIS_URL:
            return Redis.from_url(settings.REDIS_URL, decode_responses=True)

        return Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            username=settings.REDIS_USERNAME,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )

    def _format_key(self, key: str) -> str:
        return f"{self.key_prefix}:{key}"

    def _refresh_size(self) -> None:
        try:
            tracked_keys = list(self.client.smembers(self.index_key))
            if tracked_keys:
                pipeline = self.client.pipeline()
                for redis_key in tracked_keys:
                    pipeline.exists(redis_key)
                exists_flags = pipeline.execute()
                missing_keys = [
                    redis_key
                    for redis_key, exists_flag in zip(tracked_keys, exists_flags, strict=False)
                    if not exists_flag
                ]
                if missing_keys:
                    self.client.srem(self.index_key, *missing_keys)
            self.stats["size"] = int(self.client.scard(self.index_key))
        except RedisError:  # pragma: no cover - defensive path
            logger.debug("Unable to refresh Redis cache size")

    def _untrack_key(self, redis_key: str) -> None:
        try:
            removed = self.client.srem(self.index_key, redis_key)
            if removed:
                self._refresh_size()
        except RedisError:  # pragma: no cover - defensive path
            logger.debug("Unable to untrack Redis cache key")

    @staticmethod
    def _serialize_value(value: dict[str, Any]) -> str:
        return json.dumps(value, default=str)

    @staticmethod
    def _deserialize_value(data: str) -> dict[str, Any]:
        return json.loads(data)


def create_cache_system() -> CacheSystem:
    """Factory that creates a cache backend based on configuration."""

    backend = settings.CACHE_BACKEND
    if backend == "redis":
        if Redis is None:
            logger.warning("redis-py is not installed. Falling back to in-memory cache.")
        else:
            try:
                cache = RedisCacheSystem()
                cache.client.ping()
                logger.info("Using Redis cache backend")
                return cache
            except (RedisError, RuntimeError) as exc:
                logger.warning(
                    "Redis cache backend unavailable ({}). Falling back to in-memory cache.",
                    exc,
                )

    logger.info("Using in-memory cache backend")
    return InMemoryCacheSystem()
