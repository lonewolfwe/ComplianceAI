"""
Unit tests for the Gemini summarizer module.

All Gemini API calls are mocked to ensure tests run offline,
deterministically, and without incurring API costs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.ai.summarizer import GeminiSummarizer
from src.schemas.circular import CircularMeta, CircularSummary


# ── Fixtures & Helpers ────────────────────────────────────────────────────────


def _make_settings() -> MagicMock:
    """Return a mocked Settings object with a fake API key."""
    settings = MagicMock()
    settings.google_api_key = "fake_api_key"
    settings.gemini_model = "gemini-test-model"
    return settings


@pytest.fixture
def mock_meta() -> CircularMeta:
    """Return a standard CircularMeta instance for testing."""
    return CircularMeta(
        title="Test Circular",
        date="June 18, 2026",
        pdf_url="https://rbi.org.in/test.pdf",
    )


# Valid JSON that Gemini might return, strictly matching GeminiResponseSchema.
VALID_JSON_RESPONSE: str = """
{
  "summary": "This is a valid summary.",
  "affected": "Banks and NBFCs",
  "severity": "High",
  "action_items": ["Action 1", "Action 2"],
  "deadline": "2026-12-31"
}
"""

# JSON with markdown code fences (common Gemini hallucination).
FENCED_JSON_RESPONSE: str = f"```json\n{VALID_JSON_RESPONSE}\n```"

# JSON missing required fields to trigger ValidationError.
INVALID_SCHEMA_RESPONSE: str = """
{
  "summary": "Missing other fields."
}
"""


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestGeminiSummarizer:
    """Test suite for GeminiSummarizer."""

    @patch("src.ai.summarizer.genai.configure")
    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_initialisation_configures_genai(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock
    ) -> None:
        """Must configure genai with the API key during initialisation."""
        settings = _make_settings()
        GeminiSummarizer(settings)
        
        mock_configure.assert_called_once_with(api_key="fake_api_key")
        mock_model_cls.assert_called_once()
        # Verify JSON mode is requested
        kwargs = mock_model_cls.call_args[1]
        assert kwargs["model_name"] == "gemini-test-model"
        assert kwargs["generation_config"].response_mime_type == "application/json"

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_returns_error_summary_for_empty_text(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must not call Gemini and must return an error if text is empty."""
        summarizer = GeminiSummarizer(_make_settings())
        
        result = summarizer.summarize(mock_meta, "   \n  ")
        
        assert result.summary_error is True
        assert "No readable text" in result.error_message
        mock_model_cls.return_value.generate_content.assert_not_called()

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_happy_path_parses_valid_json(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must successfully parse a valid JSON response from Gemini."""
        mock_response = MagicMock()
        mock_response.text = VALID_JSON_RESPONSE
        mock_model_cls.return_value.generate_content.return_value = mock_response
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        assert result.summary_error is False
        assert result.title == "Test Circular"
        assert result.summary == "This is a valid summary."
        assert result.severity == "High"
        assert len(result.action_items) == 2

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_strips_markdown_fences_before_parsing(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must cleanly strip ```json fences if Gemini includes them."""
        mock_response = MagicMock()
        mock_response.text = FENCED_JSON_RESPONSE
        mock_model_cls.return_value.generate_content.return_value = mock_response
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        assert result.summary_error is False
        assert result.summary == "This is a valid summary."

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_retries_once_on_json_decode_error(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must retry if the first response is not valid JSON."""
        bad_response = MagicMock(text="Not JSON at all")
        good_response = MagicMock(text=VALID_JSON_RESPONSE)
        
        # First call returns garbage, second returns valid JSON
        mock_model_cls.return_value.generate_content.side_effect = [
            bad_response,
            good_response,
        ]
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        # Verify it succeeded after the retry
        assert result.summary_error is False
        assert result.summary == "This is a valid summary."
        assert mock_model_cls.return_value.generate_content.call_count == 2

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_retries_once_on_validation_error(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must retry if the JSON is valid but does not match the schema."""
        bad_schema_response = MagicMock(text=INVALID_SCHEMA_RESPONSE)
        good_response = MagicMock(text=VALID_JSON_RESPONSE)
        
        mock_model_cls.return_value.generate_content.side_effect = [
            bad_schema_response,
            good_response,
        ]
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        assert result.summary_error is False
        assert result.summary == "This is a valid summary."
        assert mock_model_cls.return_value.generate_content.call_count == 2

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_returns_error_summary_after_max_retries(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must return a graceful error summary if all retries fail."""
        bad_response = MagicMock(text="Not JSON at all")
        
        # All calls return garbage
        mock_model_cls.return_value.generate_content.return_value = bad_response
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        assert result.summary_error is True
        assert "Gemini failed to return valid JSON" in result.error_message
        assert mock_model_cls.return_value.generate_content.call_count == 2

    @patch("src.ai.summarizer.genai.GenerativeModel")
    def test_returns_error_summary_immediately_on_api_exception(
        self, mock_model_cls: MagicMock, mock_meta: CircularMeta
    ) -> None:
        """Must NOT retry on generic exceptions (like connection errors)."""
        mock_model_cls.return_value.generate_content.side_effect = Exception("API down")
        
        summarizer = GeminiSummarizer(_make_settings())
        result = summarizer.summarize(mock_meta, "Valid extracted text.")
        
        assert result.summary_error is True
        assert "API communication failed" in result.error_message
        # Must only be called once, no retries for generic errors
        assert mock_model_cls.return_value.generate_content.call_count == 1
