"""
PDF text extractor for ComplianceAI Lite.

Single Responsibility: extract plain text from a local PDF file path.
Does not download PDFs, scrape websites, or call any AI service.

Dependency injection
--------------------
    - settings:    Settings     — token limit (mandatory)
    - downloader:  PDFDownloader — injected so the caller controls download
                                   lifecycle and cleanup (mandatory)

Public interface
----------------
    parser = PDFParser(settings=settings, downloader=downloader)
    text: str = parser.download_and_extract("https://rbi.org.in/rdocs/A.pdf")
    # or, if you already have a local path:
    text: str = parser.extract_from_path(path)
"""

import re
import typing
from pathlib import Path

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from config import Settings
from src.parsers.pdf_downloader import PDFDownloadError, PDFDownloader
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PDFParser:
    """
    Extracts plain text from RBI PDF circular documents.

    Accepts a ``PDFDownloader`` via constructor injection. This means the
    caller (``CircularService``) controls the downloader's lifecycle and
    temp-file cleanup, keeping each class focused on a single concern:

      - ``PDFDownloader`` owns: HTTP download, temp storage, file validation.
      - ``PDFParser``     owns: text extraction, whitespace normalisation,
                                token truncation.

    Args:
        settings:   Application settings providing the ``pdf_max_tokens`` limit.
        downloader: An injected ``PDFDownloader`` instance.
    """

    def __init__(self, settings: Settings, downloader: PDFDownloader) -> None:
        self._max_tokens: int = settings.pdf_max_tokens
        self._downloader: PDFDownloader = downloader

    # ── Public interface ──────────────────────────────────────────────────────

    def download_and_extract(self, pdf_url: str) -> str:
        """
        Download a PDF from the given URL and return its extracted text.

        Orchestrates the full download → extract → cleanup sequence. The
        temp file is always deleted after extraction, even on failure.

        Returns an empty string rather than raising if the download fails or
        the PDF contains no readable text (e.g., scanned image-only documents).
        The caller must check for an empty result and handle it appropriately.

        Args:
            pdf_url: The absolute URL of the PDF to download and extract.

        Returns:
            Extracted plain text, truncated to ``settings.pdf_max_tokens``
            characters. Empty string on download or extraction failure.
        """
        logger.debug("Downloading and extracting PDF: %s", pdf_url)
        try:
            result = self._downloader.download(pdf_url)
        except PDFDownloadError as exc:
            logger.error("Failed to download PDF from %s: %s", pdf_url, exc)
            return ""

        try:
            return self.extract_from_path(result.path)
        finally:
            self._downloader.delete(result)

    def download_and_extract_metadata(self, pdf_url: str) -> dict[str, typing.Any]:
        """
        Download a PDF, extract its text, and return text along with metadata (page_count, file_size_bytes).
        """
        logger.debug("Downloading and extracting PDF metadata: %s", pdf_url)
        if not PYPDF_AVAILABLE:
            logger.error("pypdf is not installed. PDF extraction skipped.")
            return {"text": "", "page_count": 0, "file_size_bytes": 0}

        try:
            result = self._downloader.download(pdf_url)
        except PDFDownloadError as exc:
            logger.error("Failed to download PDF from %s: %s", pdf_url, exc)
            return {"text": "", "page_count": 0, "file_size_bytes": 0}

        try:
            reader = PdfReader(result.path)
            page_count = len(reader.pages)
            raw_text = self._extract_pages(reader)
            
            cleaned_text = ""
            if raw_text:
                cleaned_text = self._normalise_whitespace(raw_text)
                if cleaned_text:
                    cleaned_text = self._truncate(cleaned_text)

            return {
                "text": cleaned_text,
                "page_count": page_count,
                "file_size_bytes": result.size_bytes
            }
        except Exception as exc:
            logger.error("Error extracting PDF metadata: %s", exc)
            return {"text": "", "page_count": 0, "file_size_bytes": result.size_bytes}
        finally:
            self._downloader.delete(result)

    def extract_from_path(self, path: Path) -> str:
        """
        Extract plain text from a local PDF file.

        Reads all pages using pypdf. Image-only pages yield no text
        and are silently skipped. Excessive whitespace is normalised before
        the text is returned.

        Args:
            path: Absolute path to a PDF file on disk.

        Returns:
            Extracted plain text, truncated to ``settings.pdf_max_tokens``
            characters. Returns an empty string if no text can be extracted.

        Raises:
            This method does not raise. All pdfplumber exceptions are caught,
            logged, and an empty string is returned.
        """
        logger.debug("Extracting text from local PDF: %s", path)
        if not PYPDF_AVAILABLE:
            logger.error("pypdf is not installed. PDF extraction skipped.")
            return ""

        try:
            reader = PdfReader(path)
            raw_text = self._extract_pages(reader)
        except PdfReadError as exc:
            logger.error("PDF syntax error while parsing %s: %s", path, exc)
            return ""
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error parsing PDF %s: %s", path, exc)
            return ""

        if not raw_text:
            logger.warning("No readable text could be extracted from %s.", path)
            return ""

        cleaned_text = self._normalise_whitespace(raw_text)
        if not cleaned_text:
            logger.warning("PDF %s contained only whitespace.", path)
            return ""

        return self._truncate(cleaned_text)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_pages(self, reader: typing.Any) -> str:
        """
        Concatenate text from all pages of a pypdf.PdfReader object.

        Pages that contain no extractable text (e.g., scanned images) are
        silently skipped without raising.

        Args:
            reader: A ``pypdf.PdfReader`` instance.

        Returns:
            Raw concatenated text from all readable pages.
        """
        if not PYPDF_AVAILABLE:
            return ""
        pages_text: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return " ".join(pages_text)

    def _normalise_whitespace(self, text: str) -> str:
        """
        Collapse runs of whitespace characters to a single space and strip ends.

        Args:
            text: Raw extracted text from pypdf.

        Returns:
            Cleaned text with normalised whitespace.
        """
        return re.sub(r"\s+", " ", text).strip()

    def _truncate(self, text: str) -> str:
        """
        Truncate text to ``self._max_tokens`` characters.

        Truncation prevents excessively large inputs from being sent to the
        Gemini API, controlling both latency and token cost.

        Args:
            text: The full extracted and normalised text string.

        Returns:
            Text capped at ``self._max_tokens`` characters.
        """
        if len(text) <= self._max_tokens:
            return text
        logger.debug(
            "Truncating PDF text: %d → %d characters.",
            len(text),
            self._max_tokens,
        )
        return text[: self._max_tokens]
