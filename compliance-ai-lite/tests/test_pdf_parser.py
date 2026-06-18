"""
Unit tests for the PDF parser module.

Tests rely entirely on mocking ``pdfplumber`` and ``PDFDownloader`` to avoid
hitting the network or requiring real binary PDF fixtures. This ensures tests
run instantly and deterministically.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

try:
    import pdfplumber.pdfminer.pdfparser
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not PDFPLUMBER_AVAILABLE,
    reason="pdfplumber is not installed on this architecture",
)

from src.parsers.pdf_downloader import DownloadResult, PDFDownloadError
from src.parsers.pdf_parser import PDFParser


# ── Fixtures & Mock helpers ───────────────────────────────────────────────────


def _make_settings(max_tokens: int = 50) -> MagicMock:
    """Return a mocked Settings object with a configurable token limit."""
    settings = MagicMock()
    settings.pdf_max_tokens = max_tokens
    return settings


def _make_downloader() -> MagicMock:
    """Return a mock PDFDownloader."""
    return MagicMock()


def _make_mock_page(text: str | None) -> MagicMock:
    """Return a mock pdfplumber Page that returns ``text`` on extract_text()."""
    page = MagicMock()
    page.extract_text.return_value = text
    return page


def _make_mock_pdf(pages: list[MagicMock]) -> MagicMock:
    """Return a mock pdfplumber.PDF object holding the given mock pages."""
    pdf = MagicMock()
    pdf.pages = pages
    # Support using the mock as a context manager (with ... as pdf:)
    pdf.__enter__.return_value = pdf
    pdf.__exit__.return_value = None
    return pdf


# ── _extract_pages ────────────────────────────────────────────────────────────


class TestExtractPages:
    """Tests for the PDFParser._extract_pages internal helper."""

    def test_extracts_text_from_single_page(self) -> None:
        """Must return text from a single page."""
        pdf = _make_mock_pdf([_make_mock_page("Hello World")])
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == "Hello World"

    def test_concatenates_multiple_pages_with_spaces(self) -> None:
        """Must join text from multiple pages with a single space."""
        pdf = _make_mock_pdf(
            [
                _make_mock_page("Page 1."),
                _make_mock_page("Page 2."),
                _make_mock_page("Page 3."),
            ]
        )
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == "Page 1. Page 2. Page 3."

    def test_skips_blank_pages(self) -> None:
        """Must silently ignore pages that return an empty string."""
        pdf = _make_mock_pdf(
            [
                _make_mock_page("Page 1."),
                _make_mock_page(""),
                _make_mock_page("Page 3."),
            ]
        )
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == "Page 1. Page 3."

    def test_skips_none_pages(self) -> None:
        """Must silently ignore pages that return None (e.g., image-only pages)."""
        pdf = _make_mock_pdf(
            [
                _make_mock_page("Page 1."),
                _make_mock_page(None),
                _make_mock_page("Page 3."),
            ]
        )
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == "Page 1. Page 3."

    def test_returns_empty_string_for_all_blank_pages(self) -> None:
        """Must return an empty string if no pages contain text."""
        pdf = _make_mock_pdf([_make_mock_page(""), _make_mock_page(None)])
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == ""

    def test_returns_empty_string_for_zero_pages(self) -> None:
        """Must handle a PDF with an empty pages list."""
        pdf = _make_mock_pdf([])
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._extract_pages(pdf) == ""


# ── _normalise_whitespace ─────────────────────────────────────────────────────


class TestNormaliseWhitespace:
    """Tests for the PDFParser._normalise_whitespace internal helper."""

    def test_collapses_multiple_spaces(self) -> None:
        """Must replace consecutive spaces with a single space."""
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._normalise_whitespace("Hello    World") == "Hello World"

    def test_replaces_newlines_and_tabs_with_spaces(self) -> None:
        """Must replace all whitespace characters (\\n, \\t, \\r) with spaces."""
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._normalise_whitespace("Hello\n\tWorld\r\n!") == "Hello World !"

    def test_strips_leading_and_trailing_whitespace(self) -> None:
        """Must remove whitespace from the beginning and end of the string."""
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._normalise_whitespace("  Hello World  \n") == "Hello World"

    def test_empty_string_remains_empty(self) -> None:
        """Must handle empty strings without crashing."""
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._normalise_whitespace("") == ""

    def test_whitespace_only_string_becomes_empty(self) -> None:
        """Must reduce strings composed entirely of whitespace to an empty string."""
        parser = PDFParser(_make_settings(), _make_downloader())
        assert parser._normalise_whitespace(" \n \t  \r ") == ""


# ── _truncate ─────────────────────────────────────────────────────────────────


class TestTruncate:
    """Tests for the PDFParser._truncate internal helper."""

    def test_returns_exact_text_when_under_limit(self) -> None:
        """Must not alter text that is shorter than the max_tokens limit."""
        parser = PDFParser(_make_settings(max_tokens=10), _make_downloader())
        assert parser._truncate("Short") == "Short"

    def test_returns_exact_text_when_exactly_at_limit(self) -> None:
        """Must not alter text that is exactly equal to the max_tokens limit."""
        parser = PDFParser(_make_settings(max_tokens=10), _make_downloader())
        assert parser._truncate("1234567890") == "1234567890"

    def test_truncates_when_over_limit(self) -> None:
        """Must slice text exactly at the max_tokens limit."""
        parser = PDFParser(_make_settings(max_tokens=5), _make_downloader())
        assert parser._truncate("1234567890") == "12345"

    def test_truncates_empty_string(self) -> None:
        """Must handle empty strings correctly."""
        parser = PDFParser(_make_settings(max_tokens=5), _make_downloader())
        assert parser._truncate("") == ""


# ── extract_from_path ─────────────────────────────────────────────────────────


class TestExtractFromPath:
    """Tests for PDFParser.extract_from_path() using a mocked pdfplumber."""

    @patch("src.parsers.pdf_parser.pdfplumber.open")
    def test_happy_path(self, mock_open: MagicMock) -> None:
        """Must orchestrate extraction, normalisation, and truncation correctly."""
        mock_open.return_value = _make_mock_pdf([_make_mock_page("  Hello \n  World  ")])
        parser = PDFParser(_make_settings(max_tokens=100), _make_downloader())
        
        result = parser.extract_from_path(Path("dummy.pdf"))
        
        assert result == "Hello World"
        mock_open.assert_called_once_with(Path("dummy.pdf"))

    @patch("src.parsers.pdf_parser.pdfplumber.open")
    def test_returns_empty_string_on_pdf_syntax_error(self, mock_open: MagicMock) -> None:
        """Must catch PDFSyntaxError and return an empty string (corrupted PDF)."""
        mock_open.side_effect = pdfplumber.pdfminer.pdfparser.PDFSyntaxError("Bad PDF")
        parser = PDFParser(_make_settings(), _make_downloader())
        
        result = parser.extract_from_path(Path("dummy.pdf"))
        
        assert result == ""

    @patch("src.parsers.pdf_parser.pdfplumber.open")
    def test_returns_empty_string_on_unexpected_error(self, mock_open: MagicMock) -> None:
        """Must catch generic Exceptions and return an empty string (failsafe)."""
        mock_open.side_effect = Exception("Out of memory or similar catastrophic failure")
        parser = PDFParser(_make_settings(), _make_downloader())
        
        result = parser.extract_from_path(Path("dummy.pdf"))
        
        assert result == ""

    @patch("src.parsers.pdf_parser.pdfplumber.open")
    def test_returns_empty_string_when_no_text_extracted(self, mock_open: MagicMock) -> None:
        """Must return empty string if the PDF is successfully opened but yields no text."""
        mock_open.return_value = _make_mock_pdf([_make_mock_page("")])
        parser = PDFParser(_make_settings(), _make_downloader())
        
        result = parser.extract_from_path(Path("dummy.pdf"))
        
        assert result == ""

    @patch("src.parsers.pdf_parser.pdfplumber.open")
    def test_returns_empty_string_when_only_whitespace_extracted(self, mock_open: MagicMock) -> None:
        """Must return empty string if normalisation reduces the content to nothing."""
        mock_open.return_value = _make_mock_pdf([_make_mock_page("   \n\t   ")])
        parser = PDFParser(_make_settings(), _make_downloader())
        
        result = parser.extract_from_path(Path("dummy.pdf"))
        
        assert result == ""


# ── download_and_extract ──────────────────────────────────────────────────────


class TestDownloadAndExtract:
    """Tests for PDFParser.download_and_extract() orchestrating downloader + parser."""

    def test_happy_path_downloads_extracts_and_deletes(self) -> None:
        """Must download the PDF, extract its text, and delete the temp file."""
        mock_downloader = _make_downloader()
        mock_result = DownloadResult(Path("temp.pdf"), "http://rbi.org/A.pdf", 1024, "application/pdf")
        mock_downloader.download.return_value = mock_result
        
        parser = PDFParser(_make_settings(), mock_downloader)
        
        with patch.object(parser, "extract_from_path", return_value="Extracted text") as mock_extract:
            result = parser.download_and_extract("http://rbi.org/A.pdf")
            
            assert result == "Extracted text"
            mock_downloader.download.assert_called_once_with("http://rbi.org/A.pdf")
            mock_extract.assert_called_once_with(mock_result.path)
            mock_downloader.delete.assert_called_once_with(mock_result)

    def test_returns_empty_string_on_download_error(self) -> None:
        """Must return empty string if the downloader raises PDFDownloadError."""
        mock_downloader = _make_downloader()
        mock_downloader.download.side_effect = PDFDownloadError("Network error")
        
        parser = PDFParser(_make_settings(), mock_downloader)
        
        with patch.object(parser, "extract_from_path") as mock_extract:
            result = parser.download_and_extract("http://rbi.org/A.pdf")
            
            assert result == ""
            mock_extract.assert_not_called()
            # If download fails, no DownloadResult is returned, so delete is not called.
            mock_downloader.delete.assert_not_called()

    def test_deletes_temp_file_even_if_extraction_raises(self) -> None:
        """Must delete the temp file even if an unexpected error occurs during extraction."""
        mock_downloader = _make_downloader()
        mock_result = DownloadResult(Path("temp.pdf"), "http://rbi.org/A.pdf", 1024, "application/pdf")
        mock_downloader.download.return_value = mock_result
        
        parser = PDFParser(_make_settings(), mock_downloader)
        
        with patch.object(parser, "extract_from_path", side_effect=ValueError("Boom")):
            with pytest.raises(ValueError, match="Boom"):
                parser.download_and_extract("http://rbi.org/A.pdf")
            
            # The finally block must still execute the cleanup.
            mock_downloader.delete.assert_called_once_with(mock_result)
