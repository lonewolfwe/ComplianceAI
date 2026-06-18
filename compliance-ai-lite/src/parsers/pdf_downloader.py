"""
PDF downloader for ComplianceAI Lite.

Single Responsibility: download PDF files from URLs to temporary disk storage.
Does not extract text, call Gemini, or perform any other processing.

Public interface
---------------
    downloader = PDFDownloader(settings, temp_dir=Path("/tmp/compliance_ai"))
    result: DownloadResult = downloader.download("https://www.rbi.org.in/rdocs/Pdf/A.pdf")
    # ... caller processes the file ...
    downloader.delete(result)   # explicit cleanup

Dependency injection
--------------------
    - settings: Settings  — timeout, user-agent (mandatory)
    - temp_dir: Path      — override the temp directory (optional, for testing)

Internal pipeline
-----------------
    download()
        └── _fetch_with_retry()          HTTP GET (stream=True) + exponential backoff
                └── _validate_response_headers()  content-length, content-type checks
        └── _stream_to_file()            chunk-write response body to disk
        └── _validate_pdf_file()         magic bytes + minimum size checks
        └── delete() / _delete_file()    cleanup on validation failure
"""

import hashlib
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from config import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Module-level constants ────────────────────────────────────────────────────

# Every valid PDF starts with these four bytes.
PDF_MAGIC_BYTES: bytes = b"%PDF"

# Minimum byte count for a file to be considered a valid PDF.
# A real PDF with even one page is orders of magnitude larger.
MIN_PDF_SIZE_BYTES: int = 1024  # 1 KB

# Maximum HTTP attempts (initial attempt + retries).
MAX_ATTEMPTS: int = 3

# Exponential back-off base delay in seconds (1 s → 2 s → 4 s).
RETRY_BASE_DELAY_SECONDS: float = 1.0

# Byte size of each streaming chunk written to disk.
STREAM_CHUNK_SIZE: int = 8192  # 8 KB

# Content-Type values that are accepted without a warning log.
# RBI serves PDFs as both application/pdf and application/octet-stream.
ACCEPTED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "application/octet-stream",
        "application/x-pdf",
        "binary/octet-stream",
    }
)

# Sub-directory name created inside the system temp dir.
TEMP_SUBDIR_NAME: str = "compliance_ai_pdfs"


# ── Exceptions ────────────────────────────────────────────────────────────────


class PDFDownloadError(Exception):
    """
    Raised when a PDF cannot be downloaded or fails file validation.

    Catching this specific exception lets callers distinguish download
    failures from unexpected errors in the rest of the pipeline.
    """


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DownloadResult:
    """
    Immutable record of a successfully completed PDF download.

    Attributes:
        path:         Path to the temporary file on disk. The caller is
                      responsible for calling downloader.delete(result)
                      once the file has been processed.
        url:          The source URL the PDF was fetched from.
        size_bytes:   Byte count of the downloaded file.
        content_type: The Content-Type header value from the HTTP response
                      (semicolon-stripped, e.g., ``"application/pdf"``).
    """

    path: Path
    url: str
    size_bytes: int
    content_type: str


# ── Downloader class ──────────────────────────────────────────────────────────


class PDFDownloader:
    """
    Downloads PDF files from URLs and stores them in a temporary directory.

    Every public method either returns a result or raises ``PDFDownloadError``.
    No method ever returns silently incorrect data or swallows exceptions
    without re-raising — the caller must handle failures explicitly.

    Temp files are named using a stable URL hash so that repeated calls
    for the same URL overwrite the previous file rather than accumulating
    stale copies.

    Args:
        settings: Application settings providing download timeout and
                  the HTTP User-Agent header.
        temp_dir: Directory for temporary PDF files. Defaults to a
                  ``compliance_ai_pdfs/`` sub-directory inside the
                  system temp dir. Pass a custom ``Path`` in tests to
                  avoid touching the real filesystem.

    Example:
        downloader = PDFDownloader(settings=get_settings())
        try:
            result = downloader.download("https://rbi.org.in/rdocs/A.pdf")
            text = extract_text(result.path)   # hand off to PDFParser
        except PDFDownloadError as exc:
            logger.error("Download failed: %s", exc)
        finally:
            downloader.delete(result)
    """

    def __init__(
        self,
        settings: Settings,
        temp_dir: Path | None = None,
    ) -> None:
        self._timeout: int = settings.pdf_download_timeout_seconds
        self._headers: dict[str, str] = {
            "User-Agent": settings.scraper_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        }
        self._temp_dir: Path = temp_dir or (
            Path(tempfile.gettempdir()) / TEMP_SUBDIR_NAME
        )
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("PDFDownloader initialised. Temp dir: %s", self._temp_dir)

    # ── Public interface ──────────────────────────────────────────────────────

    def download(self, url: str) -> DownloadResult:
        """
        Download a PDF from the given URL and store it in the temp directory.

        Streams the HTTP response body to disk in ``STREAM_CHUNK_SIZE`` chunks
        to handle large PDFs without loading them fully into memory.

        Validates both the HTTP response headers and the downloaded file
        content (magic bytes + minimum size). Deletes the temp file
        immediately if any validation step fails.

        Args:
            url: Absolute URL of the PDF to download.

        Returns:
            A ``DownloadResult`` containing the local file path and metadata.

        Raises:
            PDFDownloadError: If the download fails after ``MAX_ATTEMPTS``
                              retries, or if the file fails validation.
        """
        logger.info("Starting PDF download: %s", url)
        response = self._fetch_with_retry(url)
        temp_path = self._stream_to_file(response, url)

        try:
            _validate_pdf_file(temp_path, url)
        except PDFDownloadError:
            self._delete_file(temp_path)
            raise

        size_bytes = temp_path.stat().st_size
        content_type = (
            response.headers.get("Content-Type", "unknown")
            .split(";")[0]
            .strip()
            .lower()
        )

        logger.info(
            "PDF downloaded: %s → %s (%d bytes, type=%s).",
            url,
            temp_path.name,
            size_bytes,
            content_type,
        )
        return DownloadResult(
            path=temp_path,
            url=url,
            size_bytes=size_bytes,
            content_type=content_type,
        )

    def delete(self, result: DownloadResult) -> None:
        """
        Delete the temporary PDF file associated with a ``DownloadResult``.

        Must be called by the caller after the file has been processed to
        prevent temp files from accumulating on disk.

        Args:
            result: The ``DownloadResult`` whose temp file should be removed.
        """
        self._delete_file(result.path)

    # ── Private HTTP layer ────────────────────────────────────────────────────

    def _fetch_with_retry(self, url: str) -> requests.Response:
        """
        Perform a streaming HTTP GET with automatic exponential-backoff retries.

        Args:
            url: The PDF URL to fetch.

        Returns:
            An open ``requests.Response`` with ``stream=True``.

        Raises:
            PDFDownloadError: After ``MAX_ATTEMPTS`` failed attempts.
        """
        last_exc: Exception | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                logger.debug(
                    "HTTP GET (stream) %s — attempt %d/%d.",
                    url,
                    attempt,
                    MAX_ATTEMPTS,
                )
                response = requests.get(
                    url,
                    headers=self._headers,
                    timeout=self._timeout,
                    stream=True,
                    allow_redirects=True,
                )
                response.raise_for_status()
                _validate_response_headers(response, url)
                logger.debug(
                    "HTTP %d received for %s (%s).",
                    response.status_code,
                    url,
                    response.headers.get("Content-Type", "?"),
                )
                return response

            except (requests.RequestException, PDFDownloadError) as exc:
                last_exc = exc
                if attempt < MAX_ATTEMPTS:
                    delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Attempt %d/%d failed for %s: %s. Retrying in %.1fs.",
                        attempt,
                        MAX_ATTEMPTS,
                        url,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All %d attempts exhausted for %s. Last error: %s",
                        MAX_ATTEMPTS,
                        url,
                        exc,
                    )

        raise PDFDownloadError(
            f"PDF download failed after {MAX_ATTEMPTS} attempts: {url}"
        ) from last_exc

    def _stream_to_file(self, response: requests.Response, url: str) -> Path:
        """
        Write a streaming HTTP response body to a temp file on disk.

        The temp filename is derived from a short MD5 hash of the URL so
        repeated downloads of the same circular overwrite the same file.

        Args:
            response: An open streaming ``requests.Response``.
            url:      Source URL (used to derive the filename and for logging).

        Returns:
            Path to the written temp file.

        Raises:
            PDFDownloadError: If a filesystem error occurs or the written
                              file is empty after streaming completes.
        """
        url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]
        temp_path = self._temp_dir / f"rbi_{url_hash}.pdf"

        logger.debug("Streaming response body to %s.", temp_path)

        try:
            with open(temp_path, "wb") as file_handle:
                for chunk in response.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                    if chunk:
                        file_handle.write(chunk)
        except OSError as exc:
            self._delete_file(temp_path)
            raise PDFDownloadError(
                f"Filesystem error while writing temp file for {url}: {exc}"
            ) from exc

        written_bytes = temp_path.stat().st_size
        if written_bytes == 0:
            self._delete_file(temp_path)
            raise PDFDownloadError(
                f"Streamed response body is empty for {url}."
            )

        logger.debug("Streamed %d bytes to %s.", written_bytes, temp_path.name)
        return temp_path

    def _delete_file(self, path: Path) -> None:
        """
        Delete a file from disk, suppressing all errors.

        Used for cleanup of corrupted or invalid temp files. Errors are
        logged at WARNING level so they are visible but do not mask the
        original failure that triggered cleanup.

        Args:
            path: The path of the file to delete.
        """
        try:
            if path.exists():
                path.unlink()
                logger.debug("Deleted temp file: %s", path.name)
        except OSError as exc:
            logger.warning(
                "Could not delete temp file %s: %s", path, exc
            )


# ── Module-level pure functions (unit-testable without instantiating the class) ──


def _validate_response_headers(response: requests.Response, url: str) -> None:
    """
    Inspect HTTP response headers before streaming the body.

    Rejects responses with a known-zero Content-Length. Logs a warning for
    unexpected Content-Type values but does not reject them, because some
    RBI servers serve PDFs as ``application/octet-stream``.

    Args:
        response: The HTTP response whose headers will be inspected.
        url:      Source URL used for error messages and log context.

    Raises:
        PDFDownloadError: If ``Content-Length`` is explicitly ``0``.
    """
    content_length_header = response.headers.get("Content-Length")
    if content_length_header is not None:
        try:
            if int(content_length_header) == 0:
                raise PDFDownloadError(
                    f"Server returned Content-Length: 0 for {url}. "
                    "The resource may have been removed."
                )
        except ValueError:
            logger.debug(
                "Non-integer Content-Length %r for %s — ignoring.",
                content_length_header,
                url,
            )

    raw_content_type = response.headers.get("Content-Type", "")
    content_type = raw_content_type.split(";")[0].strip().lower()
    if content_type and content_type not in {ct.lower() for ct in ACCEPTED_CONTENT_TYPES}:
        logger.warning(
            "Unexpected Content-Type %r for %s. "
            "Proceeding — file validation will catch non-PDF content.",
            content_type,
            url,
        )


def _validate_pdf_file(path: Path, url: str) -> None:
    """
    Confirm that a downloaded file is a genuine PDF document.

    Performs two checks in order:

    1. **Minimum size** — a valid PDF is always larger than ``MIN_PDF_SIZE_BYTES``.
       A file smaller than this is almost certainly an HTML error page or an
       empty response that slipped past the header check.

    2. **Magic bytes** — every PDF starts with the four-byte signature ``%PDF``.
       An incorrect signature means the file is corrupted, is an HTML error
       page, or is a completely different file type.

    Args:
        path: Path to the file to validate.
        url:  Source URL used in error messages.

    Raises:
        PDFDownloadError: If the file is too small or has wrong magic bytes.
    """
    size_bytes = path.stat().st_size

    if size_bytes < MIN_PDF_SIZE_BYTES:
        raise PDFDownloadError(
            f"Downloaded file is too small ({size_bytes} bytes < "
            f"{MIN_PDF_SIZE_BYTES} bytes minimum) for {url}. "
            "The server may have returned an HTML error page."
        )

    with open(path, "rb") as file_handle:
        header = file_handle.read(len(PDF_MAGIC_BYTES))

    if header != PDF_MAGIC_BYTES:
        raise PDFDownloadError(
            f"File from {url} is not a valid PDF. "
            f"Expected magic bytes {PDF_MAGIC_BYTES!r}, got {header!r}. "
            "The server may have returned an HTML error page or a redirect."
        )

    logger.debug(
        "PDF validation passed: %s (%d bytes).", path.name, size_bytes
    )


def _build_temp_filename(url: str) -> str:
    """
    Derive a deterministic temp filename from a URL.

    Uses the first 12 hex characters of the MD5 hash of the URL to keep
    filenames short while avoiding collisions in practice.

    Args:
        url: The source URL string.

    Returns:
        A filename string, e.g., ``"rbi_3f2a8c91b4e0.pdf"``.

    Example:
        >>> _build_temp_filename("https://rbi.org.in/rdocs/A.pdf")
        'rbi_<12-char-hash>.pdf'
    """
    url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]
    return f"rbi_{url_hash}.pdf"
