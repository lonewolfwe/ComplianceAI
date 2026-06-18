"""
Compliance pipeline orchestration for ComplianceAI Lite.

This service owns the full circular processing workflow:
  scrape → download PDF → extract text → AI summarize → cache → return.

It is the only module that knows the exact order of operations. Routes call
this service and receive a list of CircularSummary objects.
"""

from config import Settings
from src.ai.summarizer import GeminiSummarizer
from src.parsers.pdf_downloader import PDFDownloader
from src.parsers.pdf_parser import PDFParser
from src.schemas.circular import CircularMeta, CircularSummary
from src.scraper.rbi_scraper import RBIScraper
from src.utils.cache import TTLCache
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache key used to store the list of summaries.
_CACHE_KEY: str = "latest_circulars"


class CompliancePipeline:
    """
    Orchestrates the full RBI circular processing pipeline.

    On a cache miss, the pipeline runs the following steps for each circular:
      1. RBIScraper fetches the list of latest circular metadata.
      2. PDFParser orchestrates the download and extraction of the PDF text.
      3. GeminiSummarizer generates a structured AI summary from the text.
      4. Results are stored in the TTL cache.

    Processing is sequential and per-circular errors are isolated: a
    failure on one circular does not prevent the others from processing.

    On a cache hit, results are returned immediately without any
    external network calls.

    Args:
        settings:     Application settings instance.
        scraper:      An RBIScraper instance.
        downloader:   A PDFDownloader instance.
        pdf_parser:   A PDFParser instance.
        summarizer:   A GeminiSummarizer instance.
        cache:        A TTLCache[list[CircularSummary]] instance.
    """

    def __init__(
        self,
        settings: Settings,
        scraper: RBIScraper,
        downloader: PDFDownloader,
        pdf_parser: PDFParser,
        summarizer: GeminiSummarizer,
        cache: TTLCache[list[CircularSummary]],
    ) -> None:
        self._settings = settings
        self._scraper = scraper
        self._downloader = downloader
        self._pdf_parser = pdf_parser
        self._summarizer = summarizer
        self._cache = cache

    def get_circulars(self) -> list[CircularSummary]:
        """
        Return the latest RBI circular summaries.

        Serves from cache when valid. Runs the full pipeline on a cache miss.

        Returns:
            A list of CircularSummary objects, ordered most-recent first.
            Returns an empty list if the pipeline fails entirely (e.g., scraper down).
        """
        cached = self._cache.get()
        if cached is not None:
            logger.info("Serving %d circular summaries from cache.", len(cached))
            return cached

        logger.info("Cache miss for circulars. Running pipeline.")
        return self._run_pipeline()

    def refresh(self) -> list[CircularSummary]:
        """
        Invalidate the cache and run the full pipeline immediately.

        Intended to be called by the manual refresh endpoint (POST /api/refresh).

        Returns:
            A freshly-fetched list of CircularSummary objects.
        """
        logger.info("Manual refresh requested. Invalidating cache and running pipeline.")
        self._cache.invalidate()
        return self._run_pipeline()

    def _run_pipeline(self) -> list[CircularSummary]:
        """
        Execute the full scrape → parse → summarize pipeline.

        Processes each circular sequentially. A failure on any single
        circular is caught, logged, and replaced with an error summary
        so the remaining circulars continue processing.

        Returns:
            A list of CircularSummary objects (may include error summaries).
        """
        logger.info("Starting RBI circular pipeline.")
        try:
            # 1. Fetch metadata list
            metas = self._scraper.fetch_latest_circulars()
        except Exception as exc:
            logger.error("Pipeline failed to fetch circular metadata: %s", exc)
            return []

        if not metas:
            logger.warning("Scraper returned an empty list. Pipeline halting.")
            return []

        # Process sequentially so errors don't stop the pipeline
        total = len(metas)
        summaries: list[CircularSummary] = []

        for index, meta in enumerate(metas, start=1):
            logger.info("Processing circular %d/%d: %r", index, total, meta.title)
            summary = self._process_single_circular(meta)
            summaries.append(summary)

        # Store the completed list in cache
        logger.info(
            "Pipeline completed successfully. Caching %d summaries.", len(summaries)
        )
        self._cache.set(summaries)
        return summaries

    def _process_single_circular(self, meta: CircularMeta) -> CircularSummary:
        """
        Process one circular through the download → extract → summarize chain.

        Args:
            meta: The circular's scraped metadata.

        Returns:
            A populated CircularSummary, or an error CircularSummary if
            a step failed.
        """
        try:
            # 2 & 3. Download PDF and Extract Text
            # Note: PDFParser catches its own download/parse errors and returns ""
            text = self._pdf_parser.download_and_extract(meta.pdf_url)
            
            # 4. Generate AI Summary
            # Note: GeminiSummarizer handles empty text internally by returning an error summary
            return self._summarizer.summarize(meta, text)

        except Exception as exc:
            # Absolute worst-case fallback if the orchestration itself throws an unhandled exception
            logger.error(
                "Unhandled exception processing circular %r: %s", meta.title, exc
            )
            # The summarizer knows how to build a clean error summary shape
            return self._summarizer._build_error_summary(
                meta, f"Internal pipeline error: {exc}"
            )
