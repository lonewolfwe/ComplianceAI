"""
Circular pipeline orchestration service for ComplianceAI Lite.

This service owns the full circular processing workflow:
  scrape → download PDF → extract text → AI summarize → cache → return.

It is the only module that knows the order of operations. Routes call
this service and receive a list of CircularSummary objects. The service
does not know about HTTP, templates, or UI concerns.
"""

from config import Settings
from src.ai.gemini_client import GeminiClient
from src.parsers.pdf_downloader import PDFDownloader
from src.parsers.pdf_parser import PDFParser
from src.schemas.circular import CircularSummary
from src.scraper.rbi_scraper import RBIScraper
from src.utils.cache import TTLCache
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CircularService:
    """
    Orchestrates the full RBI circular processing pipeline.

    On a cache miss, the service runs the following steps for each circular:
      1. RBIScraper fetches the list of latest circular metadata.
      2. PDFDownloader downloads each circular's PDF to a temp file.
      3. PDFParser extracts text from the temp file.
      4. GeminiClient generates a structured AI summary.
      5. Results are stored in the TTL cache.

    Processing is sequential and per-circular errors are isolated: a
    failure on one circular does not prevent the others from processing.

    On a cache hit, results are returned immediately without any
    external network calls.

    Args:
        settings:     Application settings instance.
        scraper:      An RBIScraper instance.
        downloader:   A PDFDownloader instance.
        pdf_parser:   A PDFParser instance.
        gemini_client: A GeminiClient instance.
        cache:        A TTLCache[list[CircularSummary]] instance.
    """

    def __init__(
        self,
        settings: Settings,
        scraper: RBIScraper,
        downloader: PDFDownloader,
        pdf_parser: PDFParser,
        gemini_client: GeminiClient,
        cache: TTLCache[list[CircularSummary]],
    ) -> None:
        self._settings: Settings = settings
        self._scraper: RBIScraper = scraper
        self._downloader: PDFDownloader = downloader
        self._pdf_parser: PDFParser = pdf_parser
        self._gemini_client: GeminiClient = gemini_client
        self._cache: TTLCache[list[CircularSummary]] = cache

    def get_circulars(self) -> list[CircularSummary]:
        """
        Return the latest RBI circular summaries.

        Serves from cache when valid. Runs the full pipeline on a cache miss.

        Returns:
            A list of CircularSummary objects, ordered most-recent first.
            Returns an empty list if the pipeline fails entirely.
        """
        raise NotImplementedError(
            "CircularService.get_circulars() will be implemented in Milestone 5."
        )

    def refresh(self) -> list[CircularSummary]:
        """
        Invalidate the cache and run the full pipeline immediately.

        Intended to be called by the manual refresh endpoint (POST /api/refresh).

        Returns:
            A freshly-fetched list of CircularSummary objects.
        """
        raise NotImplementedError(
            "CircularService.refresh() will be implemented in Milestone 5."
        )

    def _run_pipeline(self) -> list[CircularSummary]:
        """
        Execute the full scrape → parse → summarize pipeline.

        Processes each circular sequentially. A failure on any single
        circular is caught, logged, and replaced with an error summary
        so the remaining circulars continue processing.

        Returns:
            A list of CircularSummary objects (may include error summaries).
        """
        raise NotImplementedError(
            "CircularService._run_pipeline() will be implemented in Milestone 5."
        )

    def _process_single_circular(self, index: int, total: int, meta_title: str) -> None:
        """
        Process one circular through the download → extract → summarize chain.

        This is a template for the implementation. The actual method signature
        will accept a CircularMeta object.

        Args:
            index: 1-based position of this circular in the batch.
            total: Total number of circulars being processed.
            meta_title: Title of the circular being processed (for logging).
        """
        logger.info(
            "Processing circular %d/%d: %r",
            index,
            total,
            meta_title,
        )
