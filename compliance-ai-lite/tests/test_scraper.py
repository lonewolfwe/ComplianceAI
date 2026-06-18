"""
Unit tests for the RBI scraper module.

All HTTP calls are mocked. Tests pass without any internet connection
or live RBI website access.

Test strategy
-------------
- Pure functions (_parse_page, _deduplicate, etc.) are tested directly.
- RBIScraper.fetch_latest() is tested via unittest.mock.patch on requests.get.
- HTML fixtures simulate real RBI page structures.
"""

import pytest
import requests
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup

from src.scraper.rbi_scraper import (
    RawCircular,
    RBIScraper,
    _build_circulars_url,
    _deduplicate,
    _extract_date_from_cells,
    _find_circular_table,
    _looks_like_date,
    _make_absolute_url,
    _parse_page,
    _parse_row,
    _to_meta,
)
from src.schemas.circular import CircularMeta


# ── HTML Fixtures ─────────────────────────────────────────────────────────────

def _make_rbi_html(rows: list[tuple[str, str, str]]) -> str:
    """
    Build a minimal RBI-style HTML page with a circular table.

    Args:
        rows: List of (date, title, href) tuples for each circular row.

    Returns:
        An HTML string simulating the RBI circulars listing page.
    """
    row_html = ""
    for date, title, href in rows:
        row_html += f"""
        <tr>
            <td>{date}</td>
            <td><a href="{href}">{title}</a></td>
        </tr>
        """
    return f"""
    <html>
    <body>
    <div id="divContent">
        <table class="tablebg">
            <tr><th>Date</th><th>Description</th></tr>
            {row_html}
        </table>
    </div>
    </body>
    </html>
    """


_SAMPLE_ROWS: list[tuple[str, str, str]] = [
    ("Jun 18, 2026", "RBI Circular on Digital Lending Guidelines Amendment", "/rdocs/Pdf/Circular_A.pdf"),
    ("Jun 15, 2026", "Prudential Framework for Resolution of Stressed Assets", "/rdocs/Pdf/Circular_B.pdf"),
    ("Jun 10, 2026", "Master Direction on KYC Compliance Requirements", "/rdocs/Pdf/Circular_C.pdf"),
    ("Jun 05, 2026", "Guidelines on Interest Rate Risk in Banking Book", "/rdocs/Pdf/Circular_D.pdf"),
    ("Jun 01, 2026", "Directions on Payment Aggregators and Payment Gateways", "/rdocs/Pdf/Circular_E.pdf"),
    ("May 28, 2026", "Updated Framework for Large Exposure Norms NBFCs", "/rdocs/Pdf/Circular_F.pdf"),
]

_SAMPLE_HTML: str = _make_rbi_html(_SAMPLE_ROWS)
_BASE_URL: str = "https://www.rbi.org.in"


# ── _build_circulars_url ──────────────────────────────────────────────────────


class TestBuildCircularsUrl:
    """Tests for the _build_circulars_url pure function."""

    def test_appends_correct_path(self) -> None:
        """Must append the standard circulars path to the base URL."""
        result = _build_circulars_url("https://www.rbi.org.in")
        assert result == "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"

    def test_strips_trailing_slash_from_base(self) -> None:
        """Must handle a base URL with a trailing slash."""
        result = _build_circulars_url("https://www.rbi.org.in/")
        assert result == "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"

    def test_returns_string(self) -> None:
        """Return type must be a str."""
        assert isinstance(_build_circulars_url(_BASE_URL), str)


# ── _make_absolute_url ────────────────────────────────────────────────────────


class TestMakeAbsoluteUrl:
    """Tests for the _make_absolute_url pure function."""

    def test_relative_path_gets_base_prepended(self) -> None:
        """A root-relative path must be resolved against the base URL."""
        result = _make_absolute_url("/rdocs/Pdf/A.pdf", _BASE_URL)
        assert result == "https://www.rbi.org.in/rdocs/Pdf/A.pdf"

    def test_absolute_url_is_returned_unchanged(self) -> None:
        """An already-absolute URL must not be modified."""
        url = "https://www.rbi.org.in/rdocs/Pdf/A.pdf"
        assert _make_absolute_url(url, _BASE_URL) == url

    def test_absolute_url_on_different_domain_is_unchanged(self) -> None:
        """An absolute URL pointing to a different domain must be returned as-is."""
        url = "https://external-site.com/doc.pdf"
        assert _make_absolute_url(url, _BASE_URL) == url

    def test_relative_path_without_leading_slash(self) -> None:
        """A relative path without a leading slash must still resolve correctly."""
        result = _make_absolute_url("rdocs/Pdf/A.pdf", _BASE_URL)
        assert result.startswith("https://www.rbi.org.in")

    def test_empty_scheme_is_treated_as_relative(self) -> None:
        """A href with no scheme must be treated as a relative path."""
        result = _make_absolute_url("/Scripts/detail.aspx?id=123", _BASE_URL)
        assert result.startswith("https://www.rbi.org.in")


# ── _looks_like_date ──────────────────────────────────────────────────────────


class TestLooksLikeDate:
    """Tests for the _looks_like_date heuristic function."""

    @pytest.mark.parametrize("value", [
        "Jun 18, 2026",
        "18 Jun 2026",
        "June 18, 2026",
        "18/06/2026",
        "2026-06-18",
        "01 Jan 2025",
    ])
    def test_valid_date_strings_return_true(self, value: str) -> None:
        """Common RBI date formats must be recognised as dates."""
        assert _looks_like_date(value) is True

    @pytest.mark.parametrize("value", [
        "",
        "Circular on Digital Lending Guidelines",
        "RBI/2026/123",
        "12345",
        "  ",
    ])
    def test_non_date_strings_return_false(self, value: str) -> None:
        """Non-date strings must not be falsely identified as dates."""
        assert _looks_like_date(value) is False

    def test_very_long_string_returns_false(self) -> None:
        """Strings longer than 30 characters must return False."""
        assert _looks_like_date("a" * 31) is False

    def test_empty_string_returns_false(self) -> None:
        """Empty string must return False."""
        assert _looks_like_date("") is False


# ── _extract_date_from_cells ──────────────────────────────────────────────────


class TestExtractDateFromCells:
    """Tests for the _extract_date_from_cells pure function."""

    def test_extracts_date_from_first_matching_cell(self) -> None:
        """The date must be extracted from the first cell that looks like a date."""
        soup = BeautifulSoup(
            "<tr><td>Jun 18, 2026</td><td><a href='/a.pdf'>Some long circular title here</a></td></tr>",
            "lxml",
        )
        cells = soup.find_all("td")
        assert _extract_date_from_cells(cells) == "Jun 18, 2026"

    def test_returns_fallback_when_no_date_found(self) -> None:
        """Must return 'Date unavailable' when no cell contains a date."""
        soup = BeautifulSoup(
            "<tr><td>Reference</td><td><a href='/a.pdf'>Title</a></td></tr>",
            "lxml",
        )
        cells = soup.find_all("td")
        assert _extract_date_from_cells(cells) == "Date unavailable"

    def test_handles_empty_cell_list(self) -> None:
        """Must return 'Date unavailable' for an empty cell list."""
        assert _extract_date_from_cells([]) == "Date unavailable"


# ── _find_circular_table ──────────────────────────────────────────────────────


class TestFindCircularTable:
    """Tests for the _find_circular_table function."""

    def test_finds_tablebg_table(self) -> None:
        """Must find a table with class 'tablebg'."""
        soup = BeautifulSoup(_SAMPLE_HTML, "lxml")
        table = _find_circular_table(soup)
        assert table is not None

    def test_returns_none_for_empty_page(self) -> None:
        """Must return None when the page contains no tables."""
        soup = BeautifulSoup("<html><body><p>No tables here.</p></body></html>", "lxml")
        assert _find_circular_table(soup) is None

    def test_returns_none_for_table_without_anchors(self) -> None:
        """Must return None when no table contains anchor tags."""
        html = "<html><body><table><tr><td>No links here</td></tr></table></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _find_circular_table(soup) is None

    def test_falls_back_to_generic_table_selector(self) -> None:
        """Must locate a plain <table> when no class-specific selector matches."""
        html = "<html><body><table><tr><td><a href='/doc.pdf'>A sufficiently long title for a circular</a></td></tr></table></body></html>"
        soup = BeautifulSoup(html, "lxml")
        assert _find_circular_table(soup) is not None


# ── _parse_row ────────────────────────────────────────────────────────────────


class TestParseRow:
    """Tests for the _parse_row function."""

    def _make_row(self, date: str, title: str, href: str) -> "Tag":
        """Helper to build a BeautifulSoup Tag for a single table row."""
        html = f"<table><tr><td>{date}</td><td><a href='{href}'>{title}</a></td></tr></table>"
        return BeautifulSoup(html, "lxml").find("tr")

    def test_parses_valid_row(self) -> None:
        """Must return a RawCircular for a well-formed row."""
        row = self._make_row(
            "Jun 18, 2026",
            "RBI Circular on Digital Lending Guidelines",
            "/rdocs/Pdf/A.pdf",
        )
        result = _parse_row(row, source_url="https://www.rbi.org.in/page", base_url=_BASE_URL)
        assert result is not None
        assert "Digital Lending" in result.title

    def test_skips_header_row_with_th_elements(self) -> None:
        """Must return None for rows that contain <th> elements."""
        html = "<table><tr><th>Date</th><th>Description</th></tr></table>"
        row = BeautifulSoup(html, "lxml").find("tr")
        assert _parse_row(row, source_url="", base_url=_BASE_URL) is None

    def test_skips_row_with_no_td_elements(self) -> None:
        """Must return None for rows with no <td> cells."""
        html = "<table><tr></tr></table>"
        row = BeautifulSoup(html, "lxml").find("tr")
        assert _parse_row(row, source_url="", base_url=_BASE_URL) is None

    def test_skips_anchor_with_fragment_only_href(self) -> None:
        """Must return None for rows whose anchor href is a bare fragment (#)."""
        row = self._make_row("Jun 18, 2026", "Some long enough title here to pass check", "#")
        assert _parse_row(row, source_url="", base_url=_BASE_URL) is None

    def test_skips_anchor_with_title_too_short(self) -> None:
        """Must skip anchors whose text is shorter than the minimum title length."""
        row = self._make_row("Jun 18, 2026", "Short", "/rdocs/Pdf/A.pdf")
        assert _parse_row(row, source_url="", base_url=_BASE_URL) is None

    def test_url_is_resolved_to_absolute(self) -> None:
        """The parsed URL must always be absolute."""
        row = self._make_row(
            "Jun 18, 2026",
            "RBI Circular on Digital Lending Guidelines",
            "/rdocs/Pdf/A.pdf",
        )
        result = _parse_row(row, source_url="", base_url=_BASE_URL)
        assert result is not None
        assert result.url.startswith("https://")

    def test_date_extracted_from_first_cell(self) -> None:
        """The date must be extracted from the row's cells."""
        row = self._make_row(
            "Jun 18, 2026",
            "RBI Circular on Digital Lending Guidelines",
            "/rdocs/Pdf/A.pdf",
        )
        result = _parse_row(row, source_url="", base_url=_BASE_URL)
        assert result is not None
        assert result.date == "Jun 18, 2026"

    def test_title_whitespace_is_normalised(self) -> None:
        """Extra whitespace in the title must be collapsed to single spaces."""
        row = self._make_row(
            "Jun 18, 2026",
            "  RBI   Circular   on  Digital  Lending  ",
            "/rdocs/Pdf/A.pdf",
        )
        result = _parse_row(row, source_url="", base_url=_BASE_URL)
        assert result is not None
        assert "  " not in result.title


# ── _parse_page ───────────────────────────────────────────────────────────────


class TestParsePage:
    """Tests for the _parse_page pure function."""

    def test_returns_all_valid_rows(self) -> None:
        """Must return one RawCircular per valid data row (header row excluded)."""
        result = _parse_page(_SAMPLE_HTML, source_url="https://www.rbi.org.in/page", base_url=_BASE_URL)
        assert len(result) == len(_SAMPLE_ROWS)

    def test_returns_empty_list_for_empty_html(self) -> None:
        """Must return [] when the HTML contains no tables."""
        result = _parse_page("<html><body></body></html>", source_url="", base_url=_BASE_URL)
        assert result == []

    def test_returns_empty_list_for_blank_string(self) -> None:
        """Must return [] when the HTML is an empty string."""
        result = _parse_page("", source_url="", base_url=_BASE_URL)
        assert result == []

    def test_all_urls_are_absolute(self) -> None:
        """Every RawCircular URL must be absolute."""
        result = _parse_page(_SAMPLE_HTML, source_url="", base_url=_BASE_URL)
        for circular in result:
            assert circular.url.startswith("https://"), f"Non-absolute URL: {circular.url}"

    def test_titles_are_non_empty(self) -> None:
        """Every parsed circular must have a non-empty title."""
        result = _parse_page(_SAMPLE_HTML, source_url="", base_url=_BASE_URL)
        for circular in result:
            assert circular.title.strip() != ""

    def test_source_url_is_preserved(self) -> None:
        """Every RawCircular must carry the source_url it was scraped from."""
        source = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"
        result = _parse_page(_SAMPLE_HTML, source_url=source, base_url=_BASE_URL)
        for circular in result:
            assert circular.source_url == source


# ── _deduplicate ──────────────────────────────────────────────────────────────


class TestDeduplicate:
    """Tests for the _deduplicate pure function."""

    def _make_raw(self, title: str, url: str) -> RawCircular:
        """Helper to create a minimal RawCircular for deduplication tests."""
        return RawCircular(title=title, date="Jun 18, 2026", url=url, source_url="")

    def test_removes_exact_duplicate_urls(self) -> None:
        """Entries sharing the same URL must be deduplicated to one."""
        url = "https://www.rbi.org.in/rdocs/Pdf/A.pdf"
        circulars = [self._make_raw("Title A", url), self._make_raw("Title A", url)]
        result = _deduplicate(circulars)
        assert len(result) == 1

    def test_preserves_unique_entries(self) -> None:
        """Entries with different URLs must all be preserved."""
        circulars = [
            self._make_raw("Title A", "https://www.rbi.org.in/A.pdf"),
            self._make_raw("Title B", "https://www.rbi.org.in/B.pdf"),
        ]
        assert len(_deduplicate(circulars)) == 2

    def test_preserves_order_of_first_occurrence(self) -> None:
        """The first occurrence of a URL must be kept, not the last."""
        url = "https://www.rbi.org.in/rdocs/Pdf/A.pdf"
        first = self._make_raw("First Title", url)
        duplicate = self._make_raw("Duplicate Title", url)
        result = _deduplicate([first, duplicate])
        assert result[0].title == "First Title"

    def test_empty_list_returns_empty(self) -> None:
        """An empty input must produce an empty output."""
        assert _deduplicate([]) == []

    def test_no_duplicates_returns_same_length(self) -> None:
        """A list with no duplicates must be returned at full length."""
        circulars = [self._make_raw(f"Title {i}", f"https://rbi.org.in/{i}.pdf") for i in range(5)]
        assert len(_deduplicate(circulars)) == 5

    def test_multiple_duplicates_of_same_url(self) -> None:
        """Three entries with the same URL must collapse to one."""
        url = "https://www.rbi.org.in/A.pdf"
        circulars = [self._make_raw("T", url) for _ in range(3)]
        assert len(_deduplicate(circulars)) == 1


# ── _to_meta ──────────────────────────────────────────────────────────────────


class TestToMeta:
    """Tests for the _to_meta conversion function."""

    def test_returns_circular_meta_instance(self) -> None:
        """Must return a CircularMeta Pydantic model."""
        raw = RawCircular(
            title="RBI Circular on Digital Lending Guidelines",
            date="Jun 18, 2026",
            url="https://www.rbi.org.in/rdocs/Pdf/A.pdf",
            source_url="https://www.rbi.org.in/page",
        )
        result = _to_meta(raw)
        assert isinstance(result, CircularMeta)

    def test_fields_are_correctly_mapped(self) -> None:
        """Title, date, and pdf_url must match the source RawCircular."""
        raw = RawCircular(
            title="RBI Circular on Payment Aggregators",
            date="Jun 15, 2026",
            url="https://www.rbi.org.in/rdocs/Pdf/B.pdf",
            source_url="",
        )
        meta = _to_meta(raw)
        assert meta.title == raw.title
        assert meta.date == raw.date
        assert meta.pdf_url == raw.url


# ── RBIScraper.fetch_latest (integration-style with mocked HTTP) ──────────────


class TestRBIScraperFetchLatest:
    """
    Integration-style tests for RBIScraper.fetch_latest().

    requests.get is mocked; no real network calls are made.
    """

    def _make_settings(self, limit: int = 5) -> MagicMock:
        """Build a minimal mock Settings object for the scraper."""
        settings = MagicMock()
        settings.rbi_base_url = _BASE_URL
        settings.rbi_circular_limit = limit
        settings.scraper_timeout_seconds = 10
        settings.scraper_user_agent = "TestAgent/1.0"
        return settings

    def _make_ok_response(self, html: str) -> MagicMock:
        """Build a mock requests.Response with status 200 and the given HTML."""
        response = MagicMock()
        response.status_code = 200
        response.text = html
        response.content = html.encode()
        response.raise_for_status.return_value = None
        return response

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_returns_circular_meta_list(self, mock_get: MagicMock) -> None:
        """fetch_latest() must return a list of CircularMeta objects."""
        mock_get.return_value = self._make_ok_response(_SAMPLE_HTML)
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert isinstance(result, list)
        assert all(isinstance(c, CircularMeta) for c in result)

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_respects_configured_limit(self, mock_get: MagicMock) -> None:
        """fetch_latest() must not return more items than the configured limit."""
        mock_get.return_value = self._make_ok_response(_SAMPLE_HTML)
        scraper = RBIScraper(settings=self._make_settings(limit=3))
        result = scraper.fetch_latest()
        assert len(result) <= 3

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_returns_empty_list_on_connection_error(self, mock_get: MagicMock) -> None:
        """Must return [] when the RBI website is unreachable."""
        mock_get.side_effect = requests.ConnectionError("Network unreachable")
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert result == []

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_returns_empty_list_on_timeout(self, mock_get: MagicMock) -> None:
        """Must return [] when every request times out."""
        mock_get.side_effect = requests.Timeout("Request timed out")
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert result == []

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_returns_empty_list_on_http_error(self, mock_get: MagicMock) -> None:
        """Must return [] when the server returns a 5xx status."""
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("503 Service Unavailable")
        mock_get.return_value = response
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert result == []

    @patch("src.scraper.rbi_scraper.time.sleep")
    @patch("src.scraper.rbi_scraper.requests.get")
    def test_retries_on_failure_before_giving_up(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Must attempt the request _MAX_ATTEMPTS times before returning []."""
        mock_get.side_effect = requests.ConnectionError("Unavailable")
        scraper = RBIScraper(settings=self._make_settings())
        scraper.fetch_latest()
        assert mock_get.call_count == 3  # _MAX_ATTEMPTS = 3

    @patch("src.scraper.rbi_scraper.time.sleep")
    @patch("src.scraper.rbi_scraper.requests.get")
    def test_succeeds_on_second_attempt_after_initial_failure(
        self,
        mock_get: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        """Must succeed on the second attempt if the first fails."""
        ok_response = self._make_ok_response(_SAMPLE_HTML)
        mock_get.side_effect = [requests.ConnectionError("Transient error"), ok_response]
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert len(result) > 0
        assert mock_get.call_count == 2

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_deduplicates_duplicate_entries(self, mock_get: MagicMock) -> None:
        """Must not return duplicate entries when the page contains repeated URLs."""
        duplicate_rows = _SAMPLE_ROWS[:2] + _SAMPLE_ROWS[:2]  # 4 rows, 2 unique
        html_with_dupes = _make_rbi_html(duplicate_rows)
        mock_get.return_value = self._make_ok_response(html_with_dupes)
        scraper = RBIScraper(settings=self._make_settings(limit=10))
        result = scraper.fetch_latest()
        urls = [c.pdf_url for c in result]
        assert len(urls) == len(set(urls)), "Duplicate URLs found in result"

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_returns_empty_list_for_empty_page(self, mock_get: MagicMock) -> None:
        """Must return [] when the page contains no recognisable circulars."""
        mock_get.return_value = self._make_ok_response("<html><body><p>No content.</p></body></html>")
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        assert result == []

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_all_results_have_non_empty_titles(self, mock_get: MagicMock) -> None:
        """Every returned CircularMeta must have a non-empty title."""
        mock_get.return_value = self._make_ok_response(_SAMPLE_HTML)
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        for meta in result:
            assert meta.title.strip() != "", f"Empty title found: {meta!r}"

    @patch("src.scraper.rbi_scraper.requests.get")
    def test_all_results_have_non_empty_pdf_urls(self, mock_get: MagicMock) -> None:
        """Every returned CircularMeta must have a non-empty pdf_url."""
        mock_get.return_value = self._make_ok_response(_SAMPLE_HTML)
        scraper = RBIScraper(settings=self._make_settings())
        result = scraper.fetch_latest()
        for meta in result:
            assert meta.pdf_url.strip() != "", f"Empty pdf_url found: {meta!r}"
