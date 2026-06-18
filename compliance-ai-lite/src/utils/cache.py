"""
In-memory TTL cache for ComplianceAI Lite.

Stores the result of the circular pipeline between requests so that
page loads are fast and Gemini is not called on every visit.

The cache is process-local and does not survive restarts. For the MVP
this is sufficient; a persistent store (Redis, MongoDB) is a V2 concern.
"""

import threading
import time
from typing import Generic, TypeVar

from src.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class TTLCache(Generic[T]):
    """
    A thread-safe, single-entry cache with a time-to-live expiry.

    Designed specifically for the ComplianceAI Lite use case: one cached
    payload (the list of circular summaries) that expires after a
    configurable TTL. Multiple threads (e.g., concurrent web requests)
    can safely read from or invalidate the cache.

    Args:
        ttl_seconds: Number of seconds before the cached value expires.

    Example:
        cache: TTLCache[list[CircularSummary]] = TTLCache(ttl_seconds=1800)
        cache.set(summaries)
        cached = cache.get()   # Returns summaries or None if expired.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds: int = ttl_seconds
        self._value: T | None = None
        self._expires_at: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    def get(self) -> T | None:
        """
        Return the cached value if it exists and has not expired.

        Returns:
            The cached value, or None if the cache is empty or stale.
        """
        with self._lock:
            if self._value is not None and time.monotonic() < self._expires_at:
                logger.debug("Cache hit. Returning cached circulars.")
                return self._value
            logger.debug("Cache miss. Value is absent or expired.")
            return None

    def set(self, value: T) -> None:
        """
        Store a value in the cache and reset the expiry timer.

        Args:
            value: The value to cache.
        """
        with self._lock:
            self._value = value
            self._expires_at = time.monotonic() + self._ttl_seconds
            logger.info(
                "Cache populated. Expires in %d seconds (%d minutes).",
                self._ttl_seconds,
                self._ttl_seconds // 60,
            )

    def invalidate(self) -> None:
        """
        Clear the cached value immediately, forcing a fresh fetch on the next request.
        """
        with self._lock:
            self._value = None
            self._expires_at = 0.0
            logger.info("Cache invalidated manually.")

    @property
    def is_valid(self) -> bool:
        """Return True if the cache currently holds a non-expired value."""
        with self._lock:
            return self._value is not None and time.monotonic() < self._expires_at

    @property
    def seconds_until_expiry(self) -> float:
        """Return the number of seconds remaining before the cache expires. Zero if expired."""
        with self._lock:
            remaining = self._expires_at - time.monotonic()
            return max(remaining, 0.0)
