"""
Unit tests for the CompliancePipeline orchestration module.
"""

from unittest.mock import MagicMock

import pytest

from src.schemas.circular import CircularMeta, CircularSummary
from src.services.pipeline import CompliancePipeline


# ── Fixtures & Helpers ────────────────────────────────────────────────────────


@pytest.fixture
def mock_settings() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_scraper() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_downloader() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_pdf_parser() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_summarizer() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_cache() -> MagicMock:
    return MagicMock()


@pytest.fixture
def pipeline(
    mock_settings: MagicMock,
    mock_scraper: MagicMock,
    mock_downloader: MagicMock,
    mock_pdf_parser: MagicMock,
    mock_summarizer: MagicMock,
    mock_cache: MagicMock,
) -> CompliancePipeline:
    """Return a CompliancePipeline with all dependencies mocked."""
    return CompliancePipeline(
        settings=mock_settings,
        scraper=mock_scraper,
        downloader=mock_downloader,
        pdf_parser=mock_pdf_parser,
        summarizer=mock_summarizer,
        cache=mock_cache,
    )


def _make_meta(title: str) -> CircularMeta:
    return CircularMeta(
        title=title,
        date="June 18, 2026",
        pdf_url="https://rbi.org.in/test.pdf",
    )


def _make_summary(title: str, is_error: bool = False) -> CircularSummary:
    return CircularSummary(
        title=title,
        date="June 18, 2026",
        pdf_url="https://rbi.org.in/test.pdf",
        summary_error=is_error,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestCompliancePipeline:
    def test_get_circulars_returns_cached_if_available(
        self, pipeline: CompliancePipeline, mock_cache: MagicMock
    ) -> None:
        """Must return cached summaries without invoking the scraper."""
        cached_list = [_make_summary("Cached")]
        mock_cache.get.return_value = cached_list

        result = pipeline.get_circulars()

        assert result == cached_list
        mock_cache.get.assert_called_once_with("latest_circulars")
        pipeline._scraper.fetch_latest.assert_not_called()

    def test_get_circulars_runs_pipeline_on_cache_miss(
        self, pipeline: CompliancePipeline, mock_cache: MagicMock
    ) -> None:
        """Must invoke the scraper and run the pipeline if cache is empty."""
        mock_cache.get.return_value = None
        pipeline._scraper.fetch_latest.return_value = []

        result = pipeline.get_circulars()

        assert result == []
        pipeline._scraper.fetch_latest.assert_called_once()

    def test_refresh_invalidates_cache_and_runs_pipeline(
        self, pipeline: CompliancePipeline, mock_cache: MagicMock
    ) -> None:
        """Must invalidate cache and re-run pipeline regardless of cache state."""
        pipeline._scraper.fetch_latest.return_value = []

        result = pipeline.refresh()

        assert result == []
        mock_cache.invalidate.assert_called_once_with("latest_circulars")
        pipeline._scraper.fetch_latest.assert_called_once()

    def test_run_pipeline_returns_empty_list_on_scraper_failure(
        self, pipeline: CompliancePipeline
    ) -> None:
        """Must log and return an empty list if the scraper raises an exception."""
        pipeline._scraper.fetch_latest.side_effect = Exception("Scrape failed")

        result = pipeline._run_pipeline()

        assert result == []

    def test_run_pipeline_returns_empty_list_on_no_circulars(
        self, pipeline: CompliancePipeline
    ) -> None:
        """Must log and return an empty list if scraper finds no circulars."""
        pipeline._scraper.fetch_latest.return_value = []

        result = pipeline._run_pipeline()

        assert result == []

    def test_run_pipeline_processes_each_circular_sequentially(
        self, pipeline: CompliancePipeline
    ) -> None:
        """Must iterate over metas, calling download/extract/summarize for each."""
        meta1 = _make_meta("Circ 1")
        meta2 = _make_meta("Circ 2")
        pipeline._scraper.fetch_latest.return_value = [meta1, meta2]

        pipeline._pdf_parser.download_and_extract.side_effect = ["Text 1", "Text 2"]
        summary1 = _make_summary("Circ 1")
        summary2 = _make_summary("Circ 2")
        pipeline._summarizer.summarize.side_effect = [summary1, summary2]

        result = pipeline._run_pipeline()

        assert result == [summary1, summary2]
        
        # Verify it passed the right args to dependencies
        assert pipeline._pdf_parser.download_and_extract.call_count == 2
        assert pipeline._summarizer.summarize.call_count == 2
        
        # Verify cache was updated
        pipeline._cache.set.assert_called_once_with("latest_circulars", [summary1, summary2])

    def test_run_pipeline_isolates_failures(
        self, pipeline: CompliancePipeline
    ) -> None:
        """
        A catastrophic failure processing one circular must not halt the pipeline.
        The failed circular should be replaced with an error summary.
        """
        meta1 = _make_meta("Circ 1")
        meta2 = _make_meta("Circ 2")
        pipeline._scraper.fetch_latest.return_value = [meta1, meta2]

        # First circular crashes unhandled during download_and_extract
        pipeline._pdf_parser.download_and_extract.side_effect = [
            Exception("Catastrophic disk failure"),
            "Text 2"
        ]
        
        error_summary = _make_summary("Circ 1", is_error=True)
        success_summary = _make_summary("Circ 2")
        
        pipeline._summarizer._build_error_summary.return_value = error_summary
        pipeline._summarizer.summarize.return_value = success_summary

        result = pipeline._run_pipeline()

        # Both items process. First is an error summary, second is successful.
        assert len(result) == 2
        assert result[0] == error_summary
        assert result[1] == success_summary
