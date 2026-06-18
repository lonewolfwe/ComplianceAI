"""
Orchestrates the new Lazy-Loading AI Pipeline.
Separates fetching metadata from generating heavy AI summaries.
"""

from typing import List

from config import Settings
from src.schemas.circular import CircularMeta, CircularSummary
from src.scraper.rbi_scraper import RBIScraper
from src.parsers.pdf_parser import PDFParser
from src.services.ai_service import AIService
from src.repositories.summary_repository import SummaryRepository
from src.utils.cache_manager import CacheManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class CircularService:
    """Orchestrates metadata fetching, PDF extraction, and AI summarization pipelines."""

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        settings: Settings,
        scraper: RBIScraper,
        pdf_parser: PDFParser,
        ai_service: AIService,
        summary_repo: SummaryRepository,
        meta_cache: CacheManager[List[CircularMeta]],
    ):
        self._settings = settings
        self._scraper = scraper
        self._pdf_parser = pdf_parser
        self._ai_service = ai_service
        self._summary_repo = summary_repo
        self._meta_cache = meta_cache

    def get_latest_metadata(self, force_refresh: bool = False) -> List[CircularMeta]:
        """
        Fetches the latest circular titles and links.
        Does NOT trigger any PDF downloads or AI summarizations.
        Used for the homepage load (< 1 second).
        """
        if not force_refresh:
            cached = self._meta_cache.get()
            if cached is not None:
                logger.info("Serving metadata from memory cache.")
                return cached

        logger.info("Fetching fresh metadata from RBI scraper.")
        try:
            metas = self._scraper.fetch_latest()
            if metas:
                self._meta_cache.set(metas)
            return metas
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Scraper failed: %s", exc, exc_info=True)
            return []

    def get_or_generate_summary(
        self, meta: CircularMeta, force_regenerate: bool = False
    ) -> CircularSummary:
        """
        The core Lazy AI pipeline.
        Checks disk cache first. If cache miss, downloads PDF, extracts text, calls Gemini, and saves.
        """
        # 1. Check persistent cache
        if not force_regenerate:
            cached_summary = self._summary_repo.get_summary(meta.hash)
            if cached_summary:
                logger.info("Cache hit: Found existing summary for %s", meta.hash)
                return cached_summary

        logger.info("Cache miss: Generating new summary for %s", meta.hash)

        # 2. Download & Extract
        text = self._pdf_parser.download_and_extract(meta.pdf_url)

        # 3. Generate AI Summary
        summary = self._ai_service.generate_summary(meta, text)

        # 4. Save to persistent storage if successful
        if not summary.summary_error:
            self._summary_repo.save_summary(summary)

        return summary
