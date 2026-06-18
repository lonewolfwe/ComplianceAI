"""
Test suite for the CircularService orchestration layer.

All dependencies (scraper, PDF parser, Gemini client, cache) are mocked.
Tests must pass without internet access or a valid API key.
"""

import pytest
from unittest.mock import MagicMock, create_autospec

from src.schemas.circular import CircularMeta, CircularSummary
from src.services.circular_service import CircularService
from src.utils.cache import TTLCache


class TestCircularService:
    """Test cases for CircularService."""

    def test_get_circulars_returns_cached_data_on_cache_hit(self) -> None:
        """get_circulars() must return cached data without calling the pipeline."""
        pass

    def test_get_circulars_runs_pipeline_on_cache_miss(self) -> None:
        """get_circulars() must run the full pipeline when the cache is empty."""
        pass

    def test_get_circulars_returns_empty_list_when_scraper_fails(self) -> None:
        """get_circulars() must return [] when the scraper returns no metadata."""
        pass

    def test_single_circular_failure_does_not_abort_pipeline(self) -> None:
        """A failure processing one circular must not stop the remaining circulars."""
        pass

    def test_refresh_invalidates_cache(self) -> None:
        """refresh() must call cache.invalidate() before running the pipeline."""
        pass

    def test_results_are_cached_after_pipeline_run(self) -> None:
        """After a pipeline run, results must be stored in the cache."""
        pass
