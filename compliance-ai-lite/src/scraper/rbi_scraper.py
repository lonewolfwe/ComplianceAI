"""
RBI circular scraper for ComplianceAI Lite.

Responsible exclusively for fetching circular metadata from the
RBI website. Does not download PDFs or call any AI service.
"""

import requests
from bs4 import BeautifulSoup

from config import Settings
from src.schemas.circular import CircularMeta
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RBIScraper:
    """
    Scrapes the RBI circulars listing page and returns structured metadata.

    Responsibilities:
      - Connect to the RBI circulars page.
      - Parse circular titles, publish dates, and PDF links.
      - Return a list of CircularMeta objects.

    This class performs no PDF downloading, text extraction, or AI calls.

    Args:
        settings: Application settings instance providing base URL,
                  timeout, user agent, and result limit.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url: str = settings.rbi_base_url
        self._limit: int = settings.rbi_circular_limit
        self._timeout: int = settings.scraper_timeout_seconds
        self._headers: dict[str, str] = {
            "User-Agent": settings.scraper_user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_latest(self) -> list[CircularMeta]:
        """
        Fetch the latest RBI circulars from the public website.

        Returns a list of up to `settings.rbi_circular_limit` circulars,
        ordered from most recent to oldest. Returns an empty list if the
        website is unreachable or the page structure has changed.

        Returns:
            A list of CircularMeta objects. May be shorter than the
            configured limit if fewer circulars are available.

        Raises:
            This method does not raise. All exceptions are caught,
            logged, and an empty list is returned so the pipeline
            can continue gracefully.
        """
        raise NotImplementedError(
            "RBIScraper.fetch_latest() will be implemented in Milestone 2."
        )

    def _build_circulars_url(self) -> str:
        """
        Construct the full URL for the RBI circulars listing page.

        Returns:
            The absolute URL string.
        """
        raise NotImplementedError(
            "RBIScraper._build_circulars_url() will be implemented in Milestone 2."
        )

    def _parse_circular_rows(
        self,
        soup: BeautifulSoup,
    ) -> list[CircularMeta]:
        """
        Extract CircularMeta entries from a parsed BeautifulSoup document.

        Args:
            soup: A parsed BeautifulSoup object representing the RBI circulars page.

        Returns:
            A list of CircularMeta objects extracted from the page.
        """
        raise NotImplementedError(
            "RBIScraper._parse_circular_rows() will be implemented in Milestone 2."
        )
