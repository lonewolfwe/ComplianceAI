"""
PDF downloader and text extractor for ComplianceAI Lite.

Responsible exclusively for:
  1. Downloading a PDF from a given URL into memory (no disk writes).
  2. Extracting plain text from that PDF using pdfplumber.

Does not scrape, summarize, or call any AI service.
"""

import io

import pdfplumber
import requests

from config import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFParser:
    """
    Downloads RBI PDF circulars and extracts readable text content.

    PDFs are never written to disk. They are downloaded into an in-memory
    BytesIO buffer and processed entirely in memory to avoid filesystem
    side-effects and simplify cleanup.

    Args:
        settings: Application settings providing timeout and token limits.
    """

    def __init__(self, settings: Settings) -> None:
        self._timeout: int = settings.pdf_download_timeout_seconds
        self._max_tokens: int = settings.pdf_max_tokens
        self._headers: dict[str, str] = {
            "User-Agent": settings.scraper_user_agent,
        }

    def download_and_extract(self, pdf_url: str) -> str:
        """
        Download a PDF from the given URL and return its extracted text.

        The extracted text is truncated to `settings.pdf_max_tokens`
        characters before being returned, to control Gemini token usage.

        Args:
            pdf_url: The absolute URL of the PDF to download.

        Returns:
            Extracted plain text from the PDF. Returns an empty string
            if the download fails or the PDF contains no readable text
            (e.g., scanned image-only documents).

        Raises:
            This method does not raise. All exceptions are caught,
            logged, and an empty string is returned.
        """
        raise NotImplementedError(
            "PDFParser.download_and_extract() will be implemented in Milestone 3."
        )

    def _download_to_buffer(self, pdf_url: str) -> io.BytesIO:
        """
        Stream a PDF from the given URL into an in-memory BytesIO buffer.

        Args:
            pdf_url: The absolute URL of the PDF to download.

        Returns:
            A BytesIO buffer positioned at the start of the PDF bytes.

        Raises:
            requests.RequestException: If the download fails after retries.
        """
        raise NotImplementedError(
            "PDFParser._download_to_buffer() will be implemented in Milestone 3."
        )

    def _extract_text_from_buffer(self, buffer: io.BytesIO) -> str:
        """
        Extract all readable text from an in-memory PDF buffer.

        Image-only pages yield no text and are silently skipped.
        Excessive whitespace is normalized before returning.

        Args:
            buffer: A BytesIO buffer containing the raw PDF bytes.

        Returns:
            The concatenated plain-text content of all pages.
        """
        raise NotImplementedError(
            "PDFParser._extract_text_from_buffer() will be implemented in Milestone 3."
        )

    def _truncate_text(self, text: str) -> str:
        """
        Truncate extracted text to the configured maximum character count.

        Args:
            text: The full extracted text string.

        Returns:
            Text truncated to `self._max_tokens` characters.
        """
        if len(text) <= self._max_tokens:
            return text
        logger.debug(
            "Truncating PDF text from %d to %d characters.",
            len(text),
            self._max_tokens,
        )
        return text[: self._max_tokens]
