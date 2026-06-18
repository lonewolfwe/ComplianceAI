"""
RBI circular scraper for ComplianceAI Lite.

Responsible exclusively for fetching circular metadata from the RBI website.
Does not download PDFs, extract text, or call any AI service.

Public interface
----------------
    scraper = RBIScraper(settings)
    circulars: list[CircularMeta] = scraper.fetch_latest()

Internal pipeline
-----------------
    fetch_latest()
        └── _fetch_html()          HTTP GET + retry + timeout
                └── _parse_page()  BS4 HTML → list[RawCircular]
                        ├── _find_circular_table()   locate the <table>
                        ├── _parse_row()             one <tr> → RawCircular | None
                        └── _make_absolute_url()     resolve relative hrefs
        └── _deduplicate()         remove exact-URL duplicates
        └── _to_meta()             RawCircular → CircularMeta
"""

import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from config import Settings
from src.schemas.circular import CircularMeta
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── Module-level constants ────────────────────────────────────────────────────

# Path appended to the base URL to reach the circulars listing page.
_CIRCULARS_PATH: str = "/Scripts/BS_CircularIndexDisplay.aspx"

# CSS selectors tried in order when searching for the circulars table.
# The RBI website uses different table structures across page types.
_TABLE_SELECTORS: tuple[str, ...] = (
    "table.tablebg",
    "#divContent table",
    ".content-area table",
    "table",
)

# Maximum number of HTTP attempts (initial attempt + retries).
_MAX_ATTEMPTS: int = 3

# Base delay in seconds between retry attempts (doubles each retry).
_RETRY_BASE_DELAY_SECONDS: float = 1.0

# Minimum number of characters for a link text to be considered a circular title.
_MIN_TITLE_LENGTH: int = 10

# File extensions treated as direct PDF links.
_PDF_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".PDF"})


# ── Internal data model ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RawCircular:
    """
    Immutable value object representing one row scraped from the RBI listing page.

    This is the internal data model for the scraper layer. It is converted to
    the public-facing CircularMeta Pydantic model before leaving the scraper.

    Attributes:
        title:      The circular title extracted from the anchor text.
        date:       The publication date as a raw string from the page.
        url:        The href value (may be relative or absolute, PDF or HTML).
        source_url: The page URL from which this entry was scraped (for logging).
    """

    title: str
    date: str
    url: str
    source_url: str


# ── Scraper class ─────────────────────────────────────────────────────────────


class RBIScraper:
    """
    Scrapes the RBI circulars listing page and returns structured metadata.

    All public methods return gracefully on failure — they never raise.
    Failures are logged and an empty list is returned so the pipeline
    can continue with whatever data is available.

    Args:
        settings: Application settings providing base URL, timeout,
                  user agent, and maximum result count.

    Example:
        scraper = RBIScraper(settings=get_settings())
        circulars = scraper.fetch_latest()
        for c in circulars:
            print(c.title, c.date, c.pdf_url)
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url: str = settings.rbi_base_url.rstrip("/")
        self._limit: int = settings.rbi_circular_limit
        self._timeout: int = settings.scraper_timeout_seconds
        self._headers: dict[str, str] = {
            "User-Agent": settings.scraper_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    # ── Public interface ──────────────────────────────────────────────────

    def fetch_latest(self) -> list[CircularMeta]:
        """
        Fetch the latest RBI circulars from the public website.

        Runs the full scrape → deduplicate → convert pipeline. Returns up to
        ``settings.rbi_circular_limit`` circulars ordered most-recent first.

        Returns:
            A list of CircularMeta objects. Empty if the website is
            unreachable or the page structure cannot be parsed.
        """
        circulars_url = _build_circulars_url(self._base_url)
        logger.info("Fetching RBI circulars from %s (limit=%d).", circulars_url, self._limit)

        try:
            html = self._fetch_html(circulars_url)
        except requests.RequestException as exc:
            logger.error("Failed to fetch RBI page after %d attempts: %s", _MAX_ATTEMPTS, exc)
            return []

        raw_circulars = _parse_page(html, source_url=circulars_url, base_url=self._base_url)

        if not raw_circulars:
            logger.warning(
                "No circulars found on %s. The page structure may have changed.",
                circulars_url,
            )
            return []

        unique_circulars = _deduplicate(raw_circulars)
        limited_circulars = unique_circulars[: self._limit]

        logger.info(
            "Scraped %d raw entries → %d unique → returning %d.",
            len(raw_circulars),
            len(unique_circulars),
            len(limited_circulars),
        )

        final_metas = []
        for raw in limited_circulars:
            # The URL we have is the detail page. Fetch it to find the actual PDF.
            pdf_url = self._fetch_pdf_link(raw.url)
            final_metas.append(CircularMeta(
                title=raw.title,
                date=raw.date,
                pdf_url=pdf_url or raw.url,  # Fallback to detail page if no PDF found
            ))

        return final_metas

    # ── Private HTTP layer ────────────────────────────────────────────────

    def _fetch_html(self, url: str) -> str:
        """
        Perform an HTTP GET request with automatic retries and timeout.

        Attempts the request up to ``_MAX_ATTEMPTS`` times. Each failed
        attempt waits an exponentially increasing delay before retrying.

        Args:
            url: The absolute URL to fetch.

        Returns:
            The decoded HTML response body as a string.

        Raises:
            requests.RequestException: Re-raised from the final failed attempt.
        """
        last_exception: requests.RequestException | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                logger.debug("HTTP GET %s (attempt %d/%d).", url, attempt, _MAX_ATTEMPTS)
                response = requests.get(
                    url,
                    headers=self._headers,
                    timeout=self._timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                logger.debug(
                    "HTTP GET %s → %d (%d bytes).",
                    url,
                    response.status_code,
                    len(response.content),
                )
                return response.text

            except requests.RequestException as exc:
                last_exception = exc
                if attempt < _MAX_ATTEMPTS:
                    delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Request failed (attempt %d/%d): %s. Retrying in %.1fs.",
                        attempt,
                        _MAX_ATTEMPTS,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All %d attempts exhausted for %s. Last error: %s",
                        _MAX_ATTEMPTS,
                        url,
                        exc,
                    )

        raise last_exception  # type: ignore[misc]

    def _fetch_pdf_link(self, detail_url: str) -> str | None:
        """
        Fetch the detail page and extract the first direct .pdf link.
        """
        # RBI detail pages are typically under NotificationUser.aspx
        # The index page links to BS_CircularIndexDisplay.aspx which sometimes fails or redirects.
        target_url = detail_url.replace("BS_CircularIndexDisplay.aspx", "NotificationUser.aspx")
        
        try:
            html = self._fetch_html(target_url)
            soup = BeautifulSoup(html, "lxml")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if ".pdf" in href.lower():
                    # Return absolute URL of the PDF
                    return _make_absolute_url(href, base_url=self._base_url, source_url=target_url)
            logger.debug("No PDF links found on detail page: %s", target_url)
        except Exception as exc:
            logger.warning("Failed to fetch detail page %s: %s", target_url, exc)
            
        return None


# ── Module-level pure functions (unit-testable without class instantiation) ───


def _build_circulars_url(base_url: str) -> str:
    """
    Construct the absolute URL for the RBI circulars listing page.

    Kept as a module-level function so it can be tested independently.

    Args:
        base_url: The RBI base URL (e.g., "https://www.rbi.org.in").

    Returns:
        The full URL to the circulars index page.

    Example:
        >>> _build_circulars_url("https://www.rbi.org.in")
        'https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx'
    """
    return base_url.rstrip("/") + _CIRCULARS_PATH


def _parse_page(html: str, source_url: str, base_url: str) -> list[RawCircular]:
    """
    Parse an RBI circulars HTML page and return a list of raw circular entries.

    Tries multiple CSS selectors to locate the circulars table, making the
    parser resilient to minor layout changes on the RBI website.

    Args:
        html:       The raw HTML string returned by the HTTP request.
        source_url: The URL the HTML was fetched from (used for logging).
        base_url:   The RBI base URL used to resolve relative hrefs.

    Returns:
        A list of RawCircular dataclass instances, ordered as they appear
        on the page (most recent first for the RBI website).
    """
    soup = BeautifulSoup(html, "lxml")
    table = _find_circular_table(soup)

    if table is None:
        logger.warning("Could not locate a circulars table in the HTML from %s.", source_url)
        return []

    rows = table.find_all("tr")
    logger.debug("Found %d table rows to parse.", len(rows))

    circulars: list[RawCircular] = []
    for row in rows:
        raw = _parse_row(row, source_url=source_url, base_url=base_url)
        if raw is not None:
            circulars.append(raw)

    return circulars


def _find_circular_table(soup: BeautifulSoup) -> Tag | None:
    """
    Locate the HTML table containing RBI circulars using multiple CSS selectors.

    Iterates through ``_TABLE_SELECTORS`` in priority order and returns the
    first table that contains at least one anchor tag.

    Args:
        soup: A BeautifulSoup-parsed HTML document.

    Returns:
        The matching Tag element, or None if no suitable table is found.
    """
    for selector in _TABLE_SELECTORS:
        tables = soup.select(selector)
        for table in tables:
            if table.find("a"):
                logger.debug("Located circulars table using selector %r.", selector)
                return table

    return None


def _parse_row(row: Tag, source_url: str, base_url: str) -> RawCircular | None:
    """
    Extract a RawCircular from a single HTML table row.

    A valid circular row must contain:
      - At least one anchor tag with a meaningful href.
      - Link text long enough to be a genuine circular title.

    Rows that are header rows (contain <th> elements) or that contain no
    qualifying link are silently skipped by returning None.

    Args:
        row:        A BeautifulSoup Tag representing a <tr> element.
        source_url: The page URL (for logging context).
        base_url:   The RBI base URL used to resolve relative hrefs.

    Returns:
        A RawCircular instance, or None if the row should be skipped.
    """
    # Skip header rows.
    if row.find("th"):
        return None

    cells = row.find_all("td")
    if not cells:
        return None

    # Find the first anchor with a usable href and title text.
    anchor: Tag | None = None
    for cell in cells:
        candidate = cell.find("a", href=True)
        if candidate and len(candidate.get_text(strip=True)) >= _MIN_TITLE_LENGTH:
            anchor = candidate
            break

    if anchor is None:
        return None

    href: str = anchor["href"].strip()  # type: ignore[index]
    
    # The RBI website structure changed: the link text is now the circular number, 
    # and the actual title is in the 4th column (index 3).
    if len(cells) >= 4 and len(cells[3].get_text(strip=True)) >= _MIN_TITLE_LENGTH:
        title = " ".join(cells[3].get_text().split())
    else:
        title = " ".join(anchor.get_text().split())

    if not href or href.startswith("#"):
        logger.debug("Skipping anchor with non-navigable href %r.", href)
        return None

    absolute_url = _make_absolute_url(href, base_url=base_url, source_url=source_url)
    date = _extract_date_from_cells(cells)

    logger.debug("Parsed circular: title=%r date=%r url=%r", title, date, absolute_url)

    return RawCircular(
        title=title,
        date=date,
        url=absolute_url,
        source_url=source_url,
    )


def _extract_date_from_cells(cells: list[Tag]) -> str:
    """
    Extract a publication date string from the table cells of a circular row.

    Scans all cells for text that looks like a date. Falls back to "Date
    unavailable" if no date-like text is found.

    The RBI website uses several date formats; this function returns the raw
    text rather than normalising it, preserving the original formatting.

    Args:
        cells: All <td> elements in a single table row.

    Returns:
        A date string, or "Date unavailable" if none can be found.
    """
    for cell in cells:
        text = cell.get_text(strip=True)
        if _looks_like_date(text):
            return text

    return "Date unavailable"


def _looks_like_date(text: str) -> bool:
    """
    Return True if the given string looks like a publication date.

    Heuristic checks for common RBI date formats:
      - "18 Jun 2026"
      - "Jun 18, 2026"
      - "18/06/2026"
      - "2026-06-18"

    Requires both a recognisable month name or date separator AND a 4-digit
    year in the range 1900–2099. This prevents circular reference strings
    (e.g., "RBI/2026/123") from being incorrectly classified as dates.

    Args:
        text: A stripped string from a table cell.

    Returns:
        True if the text is likely a date, False otherwise.
    """
    if not text or len(text) > 30:
        return False

    # Must contain a plausible 4-digit year (1900–2099).
    if not re.search(r"\b(19|20)\d{2}\b", text):
        return False

    month_abbreviations = (
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec",
    )
    lower = text.lower()

    has_month_name = any(month in lower for month in month_abbreviations)
    # Match day/month separator only when bounded by non-digits on both sides,
    # e.g. "18/06" matches but "2026/123" does not (digit before the slash).
    has_date_separator = bool(re.search(r"(?<!\d)\d{1,2}[/\-\.]\d{1,2}(?!\d)", text))

    return has_month_name or has_date_separator


def _make_absolute_url(href: str, base_url: str, source_url: str = "") -> str:
    """
    Resolve a potentially relative href into an absolute URL.

    If the href is already absolute (starts with http/https), it is returned
    unchanged. Otherwise, it is joined against the source URL or base URL.

    Args:
        href:       The raw href attribute value from an anchor tag.
        base_url:   The base URL to fallback to.
        source_url: The page URL where the href was found.

    Returns:
        An absolute URL string.
    """
    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        return href
        
    base = source_url if source_url else base_url + "/"
    return urljoin(base, href.lstrip("/"))


def _deduplicate(circulars: list[RawCircular]) -> list[RawCircular]:
    """
    Remove duplicate circular entries that share the same URL.

    Preserves the order of first occurrence. The URL (after absolute
    resolution) is used as the deduplication key.

    Args:
        circulars: A list of RawCircular objects, possibly containing duplicates.

    Returns:
        A new list containing only the first occurrence of each unique URL.

    Example:
        >>> c1 = RawCircular("Title A", "Jun 18, 2026", "https://rbi.org.in/a.pdf", "")
        >>> c2 = RawCircular("Title A", "Jun 18, 2026", "https://rbi.org.in/a.pdf", "")
        >>> _deduplicate([c1, c2])
        [RawCircular(title='Title A', ...)]
    """
    seen_urls: set[str] = set()
    unique: list[RawCircular] = []

    for circular in circulars:
        if circular.url not in seen_urls:
            seen_urls.add(circular.url)
            unique.append(circular)
        else:
            logger.debug("Dropping duplicate circular URL: %s", circular.url)

    duplicates_removed = len(circulars) - len(unique)
    if duplicates_removed:
        logger.info("Removed %d duplicate circular(s).", duplicates_removed)

    return unique



