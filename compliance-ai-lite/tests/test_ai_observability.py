import os
import json
import pytest
from unittest.mock import MagicMock, patch
from config import Settings
from src.utils.diagnostics import DiagnosticsTracker
from src.services.ai_service import AIService
from src.schemas.circular import CircularMeta

def test_api_key_sanitization() -> None:
    """Settings validator must strip whitespace and quotes from GOOGLE_API_KEY."""
    settings = Settings(
        google_api_key="  'my-api-key-with-spaces-and-quotes'  ",
        gemini_model="gemini-1.5-flash"
    )
    assert settings.google_api_key == "my-api-key-with-spaces-and-quotes"

def test_diagnostics_tracker_recording(tmp_path) -> None:
    """DiagnosticsTracker must correctly record and persist requests and cache stats."""
    filepath = tmp_path / "diagnostics_test.json"
    tracker = DiagnosticsTracker(filepath=str(filepath))
    
    # Check initial values
    stats = tracker.get_stats()
    assert stats["requests_today"] == 0
    assert stats["cache_hits"] == 0
    
    # Record requests
    tracker.record_request(duration=1.5, success=True)
    tracker.record_request(duration=2.5, success=True)
    tracker.record_request(duration=0.5, success=False, error_msg="Quota Exceeded")
    tracker.record_cache_hit()
    tracker.record_cache_miss()
    
    # Check updated values
    stats = tracker.get_stats()
    assert stats["requests_today"] == 3
    assert stats["successful_requests"] == 2
    assert stats["failed_requests"] == 1
    assert stats["average_response_time"] == 2.0  # (1.5 + 2.5) / 2
    assert stats["last_error"] == "Quota Exceeded"
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1

@patch("src.services.ai_service.GENAI_AVAILABLE", True)
@patch("src.services.ai_service.genai", create=True)
def test_ai_service_character_validation(mock_genai: MagicMock) -> None:
    """AIService must reject texts shorter than 100 characters and bypass Gemini call."""
    settings = Settings(
        google_api_key="valid-key-length-should-be-fine-here",
        gemini_model="gemini-1.5-flash"
    )
    ai_service = AIService(settings=settings)
    
    meta = CircularMeta(
        title="RBI/2026-27/01 KYC Master Direction Update",
        date="June 18, 2026",
        pdf_url="https://rbi.org.in/rdocs/Pdf/KYC.pdf"
    )
    
    short_text = "This is a very short text snippet."
    summary = ai_service.generate_summary(meta, short_text)
    
    assert summary.summary_error is True
    assert "No readable text extracted" in summary.error_message

def test_ai_service_error_mapping() -> None:
    """AIService must map exceptions to correct status codes and developer recommendations."""
    settings = Settings(
        google_api_key="valid-key-length-should-be-fine-here",
        gemini_model="gemini-1.5-flash"
    )
    ai_service = AIService(settings=settings)
    
    # 401
    code, rec = ai_service._parse_gemini_error(Exception("API_KEY_INVALID: unauthenticated"))
    assert code == 401
    assert "Invalid API key" in rec
    
    # 429
    code, rec = ai_service._parse_gemini_error(Exception("429 Quota exceeded for model"))
    assert code == 429
    assert "Quota exceeded" in rec
