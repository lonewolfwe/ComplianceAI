"""
Thread-safe persistent diagnostics tracker for ComplianceAI Lite.
Tracks Gemini API request counts, latency, errors, and cache hit/miss stats.
"""

import os
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict

class DiagnosticsTracker:
    """Tracks and persists AI pipeline metrics."""

    def __init__(self, filepath: str = "data/diagnostics_stats.json") -> None:
        self.filepath = filepath
        self.lock = threading.Lock()
        
        # Explicit typed attributes
        self.requests_today: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.total_response_time: float = 0.0
        self.last_error: str | None = None
        self.last_success_time: str | None = None
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.last_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        self.load()

    def load(self) -> None:
        """Load stats from JSON file if it exists."""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.requests_today = int(loaded.get("requests_today", 0))
                    self.successful_requests = int(loaded.get("successful_requests", 0))
                    self.failed_requests = int(loaded.get("failed_requests", 0))
                    self.total_response_time = float(loaded.get("total_response_time", 0.0))
                    self.last_error = loaded.get("last_error")
                    self.last_success_time = loaded.get("last_success_time")
                    self.cache_hits = int(loaded.get("cache_hits", 0))
                    self.cache_misses = int(loaded.get("cache_misses", 0))
                    self.last_date = str(loaded.get("last_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def save(self) -> None:
        """Persist stats to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.get_stats_dict(), f, indent=2)
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _check_date_reset(self) -> None:
        """Reset daily stats if the date has changed in UTC."""
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if current_date != self.last_date:
            self.requests_today = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.last_date = current_date

    def record_request(self, duration: float, success: bool, error_msg: str | None = None) -> None:
        """Record a Gemini request with latency and status."""
        with self.lock:
            self._check_date_reset()
            self.requests_today += 1
            if success:
                self.successful_requests += 1
                self.total_response_time += duration
                self.last_success_time = datetime.now(timezone.utc).isoformat()
            else:
                self.failed_requests += 1
                self.last_error = error_msg
            self.save()

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self.lock:
            self.cache_hits += 1
            self.save()

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self.lock:
            self.cache_misses += 1
            self.save()

    def get_stats_dict(self) -> Dict[str, Any]:
        """Returns the internal stats as a dictionary for saving."""
        return {
            "requests_today": self.requests_today,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_response_time": self.total_response_time,
            "last_error": self.last_error,
            "last_success_time": self.last_success_time,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "last_date": self.last_date
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return a formatted dictionary of diagnostic metrics for APIs."""
        with self.lock:
            self._check_date_reset()
            avg = 0.0
            if self.successful_requests > 0:
                avg = self.total_response_time / self.successful_requests
            
            return {
                "requests_today": self.requests_today,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "average_response_time": round(avg, 2),
                "last_error": self.last_error,
                "last_success_time": self.last_success_time,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses
            }

diagnostics_tracker = DiagnosticsTracker()
