"""
Test suite for the RBI scraper module.

All network calls are mocked. Tests must pass without internet access.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.schemas.circular import CircularMeta


class TestRBIScraper:
    """Test cases for RBIScraper.fetch_latest()."""

    def test_fetch_latest_returns_list(self) -> None:
        """fetch_latest() must return a list."""
        # Will be implemented in Milestone 2.
        pass

    def test_fetch_latest_respects_limit(self) -> None:
        """fetch_latest() must not return more circulars than configured."""
        pass

    def test_fetch_latest_returns_empty_on_network_error(self) -> None:
        """fetch_latest() must return [] when the RBI website is unreachable."""
        pass

    def test_fetch_latest_returns_empty_on_parse_error(self) -> None:
        """fetch_latest() must return [] when the page structure is unrecognised."""
        pass

    def test_circular_meta_has_required_fields(self) -> None:
        """Each CircularMeta must have a non-empty title, date, and pdf_url."""
        pass
