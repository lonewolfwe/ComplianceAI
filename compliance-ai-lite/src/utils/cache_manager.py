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
