"""
In-memory caching utilities.
"""

import time
from typing import Generic, TypeVar

T = TypeVar("T")

class CacheManager(Generic[T]):
    """
    Generic in-memory TTL cache manager for lightweight data.
    Used for caching the scraped homepage metadata list.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._cache: T | None = None
        self._timestamp: float = 0.0

    def get(self) -> T | None:
        """Return the cached item if it exists and is not expired."""
        if self._cache is not None:
            if (time.time() - self._timestamp) < self._ttl:
                return self._cache
            self.invalidate()
        return None

    def set(self, item: T) -> None:
        """Store an item in the cache with the current timestamp."""
        self._cache = item
        self._timestamp = time.time()

    def invalidate(self) -> None:
        """Clear the cache."""
        self._cache = None
        self._timestamp = 0.0

class RedisCache:
    """Simple Redis-backed cache for JSON-serializable objects."""
    def __init__(self, redis_client, prefix: str = "cache:", ttl_seconds: int = 3600) -> None:
        self.redis = redis_client
        self.prefix = prefix
        self.ttl = ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def get(self, key: str):
        raw = self.redis.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value) -> None:
        self.redis.setex(self._key(key), self.ttl, json.dumps(value))

    def invalidate(self, key: str) -> None:
        self.redis.delete(self._key(key))
