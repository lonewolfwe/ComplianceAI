"""
Google Gemini AI service for ComplianceAI Lite.
Handles secure API communication, strict JSON validation, and gracefully mapped failures.
"""

import json
import time
from datetime import datetime, timezone
from typing import Optional

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from pydantic import ValidationError

from config import Settings
from src.schemas.circular import CircularMeta, CircularSummary
from src.services.prompt_builder import PromptBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AIService:
    """
    Wraps the Google Gemini API to generate structured compliance summaries.
    Enforces the PromptBuilder's strict schema and handles 429 rate limit backoff.
    """

    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.gemini_model
        if GENAI_AVAILABLE:
            genai.configure(api_key=settings.google_api_key)
            self._model = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=PromptBuilder.get_system_instruction(),
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
        else:
            self._model = None
            logger.error("google-generativeai is not installed.")

    def generate_summary(self, meta: CircularMeta, text: str) -> CircularSummary:
        """
        Generates the detailed AI summary for the circular.
        If Gemini fails, returns a gracefully degraded CircularSummary with errors flagged.
        """
        logger.info("Generation started for %r", meta.title)
        start_time = time.time()

        if not GENAI_AVAILABLE:
            return self._build_error(meta, "AI SDK not installed.")

        if not text.strip():
            return self._build_error(meta, "No readable text extracted from PDF.")

        prompt = PromptBuilder.build_summarize_prompt(meta, text)

        for attempt in range(1, 3):
            try:
                raw_response = self._call_gemini(prompt)
                summary = self._parse_and_build(meta, raw_response)
                
                duration = time.time() - start_time
                logger.info("Generation completed for %r in %.2fs", meta.title, duration)
                return summary

            except json.JSONDecodeError as exc:
                logger.warning("Failures: JSON parsing failed on attempt %d: %s", attempt, exc)
            except ValidationError as exc:
                logger.warning("Failures: Schema validation failed on attempt %d: %s", attempt, exc)
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "Quota exceeded" in err_str:
                    logger.warning("Failures: Gemini API quota exceeded.")
                    return self._build_error(meta, "AI analysis is temporarily unavailable. Please retry later.")
                
                logger.error("Failures: Unexpected AI error on attempt %d: %s", attempt, exc, exc_info=True)
                return self._build_error(meta, f"API communication failed: {exc}")

        return self._build_error(meta, "AI failed to return valid JSON after retries.")

    def _call_gemini(self, prompt: str) -> str:
        """Calls Gemini and handles raw response."""
        response = self._model.generate_content(prompt)
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        return response.text

    def _parse_and_build(self, meta: CircularMeta, raw_response: str) -> CircularSummary:
        """Parses the raw JSON into the final CircularSummary Pydantic model."""
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        
        return CircularSummary(
            title=meta.title,
            date=meta.date,
            pdf_url=meta.pdf_url,
            hash=meta.hash,
            generated_at=datetime.now(timezone.utc).isoformat(),
            ai_model=self._model_name,
            summary=data.get("summary", ""),
            impact_score=data.get("impact_score", "Medium"),
            departments=data.get("departments", []),
            questions=data.get("questions", []),
            roadmap=data.get("roadmap", []),
            executive_brief=data.get("executive_brief", ""),
            checklist=data.get("checklist", [])
        )

    def _build_error(self, meta: CircularMeta, reason: str) -> CircularSummary:
        """Graceful fallback."""
        return CircularSummary(
            title=meta.title,
            date=meta.date,
            pdf_url=meta.pdf_url,
            hash=meta.hash,
            generated_at=datetime.now(timezone.utc).isoformat(),
            ai_model=self._model_name,
            summary="AI Generation Failed",
            impact_score="Unknown",
            departments=[],
            questions=[],
            roadmap=[],
            executive_brief=reason,
            checklist=[],
            summary_error=True,
            error_message=reason
        )
