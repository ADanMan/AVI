import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from cachetools import LRUCache, TTLCache  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class BaseCacheBackend(ABC):
    """
    Abstract base class for different cache backends.
    Allows easy addition of new cache storage types (Redis, Memcached, etc.)
    """

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear(self) -> bool:
        pass


class MemoryCacheBackend(BaseCacheBackend):
    """
    In-memory cache implementation using TTLCache for automatic cleanup
    of expired records and LRUCache for limiting cache size
    """

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        """
        Initialize in-memory cache

        Args:
            max_size: Maximum number of elements in cache
            ttl_seconds: Record lifetime in seconds
        """
        self.ttl_cache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        # LRU cache for frequently used records
        self.lru_cache = LRUCache(maxsize=max_size // 10)  # 10% of main size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache with LRU cache priority
        """
        try:
            # First check LRU cache
            value = self.lru_cache.get(key)
            if value is not None:
                return self._deserialize_value(value)

            # Then check main TTL cache
            value = self.ttl_cache.get(key)
            if value is not None:
                # Add frequently used values to LRU cache
                self.lru_cache[key] = value
                return self._deserialize_value(value)

        except Exception as e:
            logger.error(f"Error getting value from cache: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Save value to cache
        """
        try:
            async with self._lock:
                serialized_value = self._serialize_value(value)
                self.ttl_cache[key] = serialized_value
                # For frequently used values also update LRU cache
                if key in self.lru_cache:
                    self.lru_cache[key] = serialized_value
                return True
        except Exception as e:
            logger.error(f"Error setting value to cache: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete value from cache
        """
        try:
            async with self._lock:
                self.ttl_cache.pop(key, None)
                self.lru_cache.pop(key, None)
                return True
        except Exception as e:
            logger.error(f"Error deleting value from cache: {e}")
            return False

    async def clear(self) -> bool:
        """
        Clear the entire cache
        """
        try:
            async with self._lock:
                self.ttl_cache.clear()
                self.lru_cache.clear()
                return True
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False

    def _serialize_value(self, value: Any) -> str:
        """
        Serialize value for storage in cache
        """
        return json.dumps({"data": value, "timestamp": datetime.utcnow().isoformat()})

    def _deserialize_value(self, value: str) -> Any:
        """
        Deserialize value from cache
        """
        data = json.loads(value)
        return data["data"]


class CacheService:
    """
    Main caching service, providing a high-level interface
    for working with the cache and additional features
    """

    def __init__(self, backend: BaseCacheBackend, namespace: str = "default"):
        """
        Initialize caching service

        Args:
            backend: Backend for cache storage
            namespace: Namespace for isolating different cache types
        """
        self.backend = backend
        self.namespace = namespace

    def _generate_key(self, key: str | dict) -> str:
        """
        Generate cache key with support for complex structures and namespaces
        """
        if isinstance(key, dict):
            # For dictionaries, use sorted string of keys and values
            key = json.dumps(key, sort_keys=True)

        # Add namespace to key and hash
        namespaced_key = f"{self.namespace}:{key}"
        return hashlib.blake2b(namespaced_key.encode(), digest_size=16).hexdigest()

    async def get(self, key: str | dict) -> Any | None:
        """
        Get value from cache
        """
        cache_key = self._generate_key(key)
        return await self.backend.get(cache_key)

    async def set(self, key: str | dict, value: Any, ttl: int | None = None) -> bool:
        """
        Save value to cache
        """
        cache_key = self._generate_key(key)
        return await self.backend.set(cache_key, value, ttl)

    async def delete(self, key: str | dict) -> bool:
        """
        Delete value from cache
        """
        cache_key = self._generate_key(key)
        return await self.backend.delete(cache_key)

    async def clear(self) -> bool:
        """
        Clear the entire cache
        """
        return await self.backend.clear()

    async def get_or_set(
        self,
        key: str | dict,
        value_func: Callable[[], Awaitable[Any]],
        ttl: int | None = None,
    ) -> Any:
        """
        Get value from cache or compute if not present

        Args:
            key: Cache key
            value_func: Function to compute value
            ttl: Time to live for the record
        """
        value = await self.get(key)
        if value is None:
            value = await value_func()
            await self.set(key, value, ttl)
        return value
