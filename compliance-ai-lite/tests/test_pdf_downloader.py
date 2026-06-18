"""
Unit tests for the PDF downloader module.

All HTTP calls and filesystem operations are controlled via mocks and
pytest's ``tmp_path`` fixture. Tests pass without any internet access.

Test strategy
-------------
- Pure functions (_validate_response_headers, _validate_pdf_file,
  _build_temp_filename) are tested directly.
- PDFDownloader methods are tested with mocked requests.get and
  a real tmp_path directory (pytest fixture) so we exercise actual
  file I/O without touching production temp dirs.
- time.sleep is mocked in retry tests to keep the suite fast.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import requests

from src.parsers.pdf_downloader import (
    ACCEPTED_CONTENT_TYPES,
    MAX_ATTEMPTS,
    MIN_PDF_SIZE_BYTES,
    PDF_MAGIC_BYTES,
    RETRY_BASE_DELAY_SECONDS,
    DownloadResult,
    PDFDownloadError,
    PDFDownloader,
    _build_temp_filename,
    _validate_pdf_file,
    _validate_response_headers,
)


# ── Fixtures & helpers ────────────────────────────────────────────────────────

SAMPLE_URL: str = "https://www.rbi.org.in/rdocs/Pdf/SampleCircular.pdf"

# Minimal valid PDF content: starts with %PDF magic bytes and is large enough.
VALID_PDF_CONTENT: bytes = PDF_MAGIC_BYTES + b"-1.4\n" + b"x" * (MIN_PDF_SIZE_BYTES + 512)

# Content that looks like an HTML error page (no magic bytes).
HTML_ERROR_CONTENT: bytes = b"<html><body>404 Not Found</body></html>" + b"x" * 2048


def _make_settings(timeout: int = 10) -> MagicMock:
    """Build a minimal mock Settings object for the downloader."""
    settings = MagicMock()
    settings.pdf_download_timeout_seconds = timeout
    settings.scraper_user_agent = "TestAgent/1.0"
    return settings


def _make_streaming_response(
    content: bytes,
    status_code: int = 200,
    content_type: str = "application/pdf",
    content_length: str | None = None,
) -> MagicMock:
    """
    Build a mock requests.Response that supports streaming iteration.

    Splits ``content`` into chunks of 8 KB to simulate iter_content behaviour.
    """
    chunk_size = 8192
    chunks = [
        content[i : i + chunk_size] for i in range(0, len(content), chunk_size)
    ]

    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status = MagicMock()
    response.iter_content = MagicMock(return_value=iter(chunks))

    headers: dict[str, str] = {"Content-Type": content_type}
    if content_length is not None:
        headers["Content-Length"] = content_length
    response.headers = headers

    return response


# ── _build_temp_filename ──────────────────────────────────────────────────────


class TestBuildTempFilename:
    """Tests for the _build_temp_filename pure function."""

    def test_returns_string(self) -> None:
        """Must return a str."""
        assert isinstance(_build_temp_filename(SAMPLE_URL), str)

    def test_has_pdf_extension(self) -> None:
        """Filename must end with .pdf."""
        assert _build_temp_filename(SAMPLE_URL).endswith(".pdf")

    def test_starts_with_rbi_prefix(self) -> None:
        """Filename must start with the 'rbi_' prefix."""
        assert _build_temp_filename(SAMPLE_URL).startswith("rbi_")

    def test_is_deterministic(self) -> None:
        """Same URL must always produce the same filename."""
        assert _build_temp_filename(SAMPLE_URL) == _build_temp_filename(SAMPLE_URL)

    def test_different_urls_produce_different_filenames(self) -> None:
        """Different URLs must not produce the same filename."""
        url_a = "https://rbi.org.in/A.pdf"
        url_b = "https://rbi.org.in/B.pdf"
        assert _build_temp_filename(url_a) != _build_temp_filename(url_b)

    def test_filename_has_expected_length(self) -> None:
        """Filename should be 'rbi_' + 12 hex chars + '.pdf' = 20 chars."""
        assert len(_build_temp_filename(SAMPLE_URL)) == 20


# ── _validate_response_headers ────────────────────────────────────────────────


class TestValidateResponseHeaders:
    """Tests for the _validate_response_headers pure function."""

    def _make_response(
        self,
        content_type: str = "application/pdf",
        content_length: str | None = None,
    ) -> MagicMock:
        """Helper to build a minimal mock response for header validation."""
        response = MagicMock()
        headers: dict[str, str] = {"Content-Type": content_type}
        if content_length is not None:
            headers["Content-Length"] = content_length
        response.headers = headers
        return response

    def test_accepts_application_pdf(self) -> None:
        """Must not raise for Content-Type: application/pdf."""
        _validate_response_headers(self._make_response("application/pdf"), SAMPLE_URL)

    def test_accepts_octet_stream(self) -> None:
        """Must not raise for Content-Type: application/octet-stream."""
        _validate_response_headers(
            self._make_response("application/octet-stream"), SAMPLE_URL
        )

    def test_accepts_pdf_with_charset_parameter(self) -> None:
        """Must strip charset parameters and still accept the content type."""
        _validate_response_headers(
            self._make_response("application/pdf; charset=utf-8"), SAMPLE_URL
        )

    def test_raises_on_content_length_zero(self) -> None:
        """Must raise PDFDownloadError when Content-Length is explicitly 0."""
        with pytest.raises(PDFDownloadError, match="Content-Length: 0"):
            _validate_response_headers(
                self._make_response(content_length="0"), SAMPLE_URL
            )

    def test_does_not_raise_on_positive_content_length(self) -> None:
        """Must not raise when Content-Length is a positive integer."""
        _validate_response_headers(
            self._make_response(content_length="102400"), SAMPLE_URL
        )

    def test_does_not_raise_on_missing_content_length(self) -> None:
        """Must not raise when Content-Length header is absent."""
        _validate_response_headers(self._make_response(), SAMPLE_URL)

    def test_does_not_raise_for_unexpected_content_type(self) -> None:
        """
        Must NOT raise for unexpected content types — only logs a warning.
        File validation (magic bytes) is the final safety check.
        """
        _validate_response_headers(self._make_response("text/html"), SAMPLE_URL)

    def test_handles_invalid_content_length_gracefully(self) -> None:
        """Must not raise for a non-integer Content-Length value."""
        _validate_response_headers(
            self._make_response(content_length="not-a-number"), SAMPLE_URL
        )


# ── _validate_pdf_file ────────────────────────────────────────────────────────


class TestValidatePdfFile:
    """Tests for the _validate_pdf_file pure function."""

    def test_passes_for_valid_pdf(self, tmp_path: Path) -> None:
        """Must not raise for a file with correct magic bytes and sufficient size."""
        pdf_file = tmp_path / "valid.pdf"
        pdf_file.write_bytes(VALID_PDF_CONTENT)
        _validate_pdf_file(pdf_file, SAMPLE_URL)

    def test_raises_for_file_below_minimum_size(self, tmp_path: Path) -> None:
        """Must raise PDFDownloadError when the file is too small."""
        small_file = tmp_path / "small.pdf"
        small_file.write_bytes(PDF_MAGIC_BYTES + b"tiny")
        with pytest.raises(PDFDownloadError, match="too small"):
            _validate_pdf_file(small_file, SAMPLE_URL)

    def test_raises_for_wrong_magic_bytes(self, tmp_path: Path) -> None:
        """Must raise PDFDownloadError when the file does not start with %PDF."""
        html_file = tmp_path / "error.pdf"
        html_file.write_bytes(HTML_ERROR_CONTENT)
        with pytest.raises(PDFDownloadError, match="magic bytes"):
            _validate_pdf_file(html_file, SAMPLE_URL)

    def test_raises_for_empty_file(self, tmp_path: Path) -> None:
        """Must raise PDFDownloadError for a completely empty file."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")
        with pytest.raises(PDFDownloadError):
            _validate_pdf_file(empty_file, SAMPLE_URL)

    def test_error_message_contains_url(self, tmp_path: Path) -> None:
        """The error message must include the source URL for traceability."""
        bad_file = tmp_path / "bad.pdf"
        bad_file.write_bytes(HTML_ERROR_CONTENT)
        with pytest.raises(PDFDownloadError, match=SAMPLE_URL):
            _validate_pdf_file(bad_file, SAMPLE_URL)

    def test_exactly_at_minimum_size_boundary(self, tmp_path: Path) -> None:
        """A file exactly at MIN_PDF_SIZE_BYTES with valid magic must pass."""
        boundary_content = PDF_MAGIC_BYTES + b"x" * (MIN_PDF_SIZE_BYTES - len(PDF_MAGIC_BYTES))
        boundary_file = tmp_path / "boundary.pdf"
        boundary_file.write_bytes(boundary_content)
        _validate_pdf_file(boundary_file, SAMPLE_URL)

    def test_one_byte_below_minimum_size_fails(self, tmp_path: Path) -> None:
        """A file one byte smaller than the minimum must be rejected."""
        short_content = PDF_MAGIC_BYTES + b"x" * (MIN_PDF_SIZE_BYTES - len(PDF_MAGIC_BYTES) - 1)
        short_file = tmp_path / "short.pdf"
        short_file.write_bytes(short_content)
        with pytest.raises(PDFDownloadError, match="too small"):
            _validate_pdf_file(short_file, SAMPLE_URL)


# ── PDFDownloader.download ────────────────────────────────────────────────────


class TestPDFDownloaderDownload:
    """
    Integration-style tests for PDFDownloader.download().

    requests.get is mocked. All file I/O uses the real filesystem via
    pytest's tmp_path fixture so we exercise actual disk writes.
    """

    def _make_downloader(self, tmp_path: Path) -> PDFDownloader:
        """Instantiate a PDFDownloader with an injected temp directory."""
        return PDFDownloader(settings=_make_settings(), temp_dir=tmp_path)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_happy_path_returns_download_result(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """download() must return a DownloadResult on success."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        downloader = self._make_downloader(tmp_path)
        result = downloader.download(SAMPLE_URL)
        assert isinstance(result, DownloadResult)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_result_url_matches_input(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """DownloadResult.url must equal the URL passed to download()."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert result.url == SAMPLE_URL

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_result_path_exists_on_disk(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """DownloadResult.path must point to a real file on disk."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert result.path.exists()
        assert result.path.is_file()

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_result_size_bytes_matches_file(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """DownloadResult.size_bytes must match the actual file size."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert result.size_bytes == result.path.stat().st_size

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_file_starts_with_pdf_magic_bytes(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """The downloaded file must begin with %PDF."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        with open(result.path, "rb") as fp:
            assert fp.read(4) == PDF_MAGIC_BYTES

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_raises_pdf_download_error_on_http_404(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Must raise PDFDownloadError when the server returns 4xx."""
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = response
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_raises_pdf_download_error_on_connection_error(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Must raise PDFDownloadError when the network is unreachable."""
        mock_get.side_effect = requests.ConnectionError("No route to host")
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_raises_pdf_download_error_on_timeout(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Must raise PDFDownloadError when the request times out."""
        mock_get.side_effect = requests.Timeout("Read timed out")
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_raises_on_html_error_page_content(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Must raise PDFDownloadError when the server returns an HTML error page."""
        mock_get.return_value = _make_streaming_response(
            HTML_ERROR_CONTENT, content_type="text/html"
        )
        with pytest.raises(PDFDownloadError, match="magic bytes"):
            self._make_downloader(tmp_path).download(SAMPLE_URL)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_deletes_file_after_validation_failure(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Corrupted files must be deleted before the exception propagates."""
        mock_get.return_value = _make_streaming_response(
            HTML_ERROR_CONTENT, content_type="text/html"
        )
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)
        # The temp directory must be empty — the invalid file was deleted.
        pdf_files = list(tmp_path.glob("*.pdf"))
        assert pdf_files == [], f"Stale files found: {pdf_files}"

    @patch("src.parsers.pdf_downloader.time.sleep")
    @patch("src.parsers.pdf_downloader.requests.get")
    def test_raises_on_content_length_zero(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """
        Must raise PDFDownloadError when Content-Length is 0.

        The Content-Length check fires inside _validate_response_headers(),
        which is called from _fetch_with_retry(). After MAX_ATTEMPTS retries
        the outer method raises PDFDownloadError chained from the inner one.
        We verify the chain so both the raise and the original cause are tested.
        """
        mock_get.return_value = _make_streaming_response(
            VALID_PDF_CONTENT, content_length="0"
        )
        with pytest.raises(PDFDownloadError) as exc_info:
            self._make_downloader(tmp_path).download(SAMPLE_URL)
        # The __cause__ chain must contain the Content-Length message.
        assert exc_info.value.__cause__ is not None
        assert "Content-Length: 0" in str(exc_info.value.__cause__)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_same_url_overwrites_previous_file(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """Repeated downloads of the same URL must overwrite the temp file."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        downloader = self._make_downloader(tmp_path)
        result_a = downloader.download(SAMPLE_URL)
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        result_b = downloader.download(SAMPLE_URL)
        assert result_a.path == result_b.path

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_content_type_stripped_of_parameters(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """DownloadResult.content_type must not contain charset parameters."""
        mock_get.return_value = _make_streaming_response(
            VALID_PDF_CONTENT, content_type="application/pdf; charset=utf-8"
        )
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert ";" not in result.content_type


# ── PDFDownloader retry behaviour ─────────────────────────────────────────────


class TestPDFDownloaderRetry:
    """Tests for retry and back-off behaviour in PDFDownloader."""

    def _make_downloader(self, tmp_path: Path) -> PDFDownloader:
        return PDFDownloader(settings=_make_settings(), temp_dir=tmp_path)

    @patch("src.parsers.pdf_downloader.time.sleep")
    @patch("src.parsers.pdf_downloader.requests.get")
    def test_retries_max_attempts_times_on_persistent_failure(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Must attempt the request exactly MAX_ATTEMPTS times before giving up."""
        mock_get.side_effect = requests.ConnectionError("Unavailable")
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert mock_get.call_count == MAX_ATTEMPTS

    @patch("src.parsers.pdf_downloader.time.sleep")
    @patch("src.parsers.pdf_downloader.requests.get")
    def test_succeeds_on_second_attempt_after_transient_error(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Must succeed when the first attempt fails but the second succeeds."""
        ok_response = _make_streaming_response(VALID_PDF_CONTENT)
        mock_get.side_effect = [
            requests.ConnectionError("Transient"),
            ok_response,
        ]
        result = self._make_downloader(tmp_path).download(SAMPLE_URL)
        assert isinstance(result, DownloadResult)
        assert mock_get.call_count == 2

    @patch("src.parsers.pdf_downloader.time.sleep")
    @patch("src.parsers.pdf_downloader.requests.get")
    def test_exponential_backoff_delays_are_correct(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Back-off delays must follow the 1s → 2s pattern (base × 2^(attempt-1))."""
        mock_get.side_effect = requests.ConnectionError("Always fails")
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)
        # Expect two sleep calls (between attempt 1→2 and 2→3, not after the last).
        expected_delays = [
            call(RETRY_BASE_DELAY_SECONDS * (2 ** 0)),  # 1.0 s
            call(RETRY_BASE_DELAY_SECONDS * (2 ** 1)),  # 2.0 s
        ]
        assert mock_sleep.call_args_list == expected_delays

    @patch("src.parsers.pdf_downloader.time.sleep")
    @patch("src.parsers.pdf_downloader.requests.get")
    def test_no_sleep_after_final_failed_attempt(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Must not sleep after the last failed attempt (avoids wasted wait time)."""
        mock_get.side_effect = requests.ConnectionError("Always fails")
        with pytest.raises(PDFDownloadError):
            self._make_downloader(tmp_path).download(SAMPLE_URL)
        # For MAX_ATTEMPTS=3 we expect exactly MAX_ATTEMPTS - 1 = 2 sleep calls.
        assert mock_sleep.call_count == MAX_ATTEMPTS - 1


# ── PDFDownloader.delete ──────────────────────────────────────────────────────


class TestPDFDownloaderDelete:
    """Tests for PDFDownloader.delete()."""

    def _make_downloader(self, tmp_path: Path) -> PDFDownloader:
        return PDFDownloader(settings=_make_settings(), temp_dir=tmp_path)

    @patch("src.parsers.pdf_downloader.requests.get")
    def test_delete_removes_temp_file(
        self, mock_get: MagicMock, tmp_path: Path
    ) -> None:
        """delete() must remove the file from disk."""
        mock_get.return_value = _make_streaming_response(VALID_PDF_CONTENT)
        downloader = self._make_downloader(tmp_path)
        result = downloader.download(SAMPLE_URL)
        assert result.path.exists()
        downloader.delete(result)
        assert not result.path.exists()

    def test_delete_does_not_raise_for_nonexistent_file(
        self, tmp_path: Path
    ) -> None:
        """delete() must not raise if the file no longer exists."""
        downloader = self._make_downloader(tmp_path)
        phantom_result = DownloadResult(
            path=tmp_path / "ghost.pdf",
            url=SAMPLE_URL,
            size_bytes=0,
            content_type="application/pdf",
        )
        downloader.delete(phantom_result)  # Must not raise.


# ── Temp directory injection ──────────────────────────────────────────────────


class TestTempDirectoryInjection:
    """Tests for the temp_dir dependency injection parameter."""

    def test_custom_temp_dir_is_used(self, tmp_path: Path) -> None:
        """PDFDownloader must write files into the injected temp_dir."""
        custom_dir = tmp_path / "custom_temp"
        custom_dir.mkdir()
        downloader = PDFDownloader(settings=_make_settings(), temp_dir=custom_dir)
        assert downloader._temp_dir == custom_dir

    def test_temp_dir_is_created_if_it_does_not_exist(self, tmp_path: Path) -> None:
        """PDFDownloader must create the temp_dir if it is absent."""
        new_dir = tmp_path / "new_subdir" / "nested"
        assert not new_dir.exists()
        PDFDownloader(settings=_make_settings(), temp_dir=new_dir)
        assert new_dir.is_dir()
