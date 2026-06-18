"""
Google Gemini AI summarizer for ComplianceAI Lite.

Responsible exclusively for:
  1. Sending circular text to the Gemini API.
  2. Validating the JSON response against the schema.
  3. Retrying once on JSON parse failure.
  4. Returning a graceful fallback CircularSummary on total failure.

Does not scrape websites, download PDFs, or orchestrate the pipeline.
"""

import json
import time
from typing import Literal

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from pydantic import BaseModel, ValidationError

from config import Settings
from src.schemas.circular import CircularMeta, CircularSummary
from src.utils.logger import get_logger

logger = get_logger(__name__)

# The system instruction sent to Gemini before every summarization request.
_SYSTEM_INSTRUCTION: str = (
    "You are a senior Indian fintech compliance analyst with deep expertise in RBI regulations. "
    "Your task is to analyze RBI circular text and produce a structured JSON compliance brief "
    "for compliance officers at NBFCs, payment companies, and digital lenders. "
    "Be precise, factual, and actionable. Never fabricate deadlines or requirements."
)

# The user prompt template. {title} and {text} are substituted at runtime.
_SUMMARIZE_PROMPT: str = """
Analyze the following RBI circular and return a JSON object with exactly these fields:

{{
  "summary": "<plain-language summary in 3–5 sentences, max 200 words>",
  "affected": "<which organizations or entity types are affected>",
  "severity": "<one of: Low | Medium | High | Critical>",
  "action_items": ["<action 1>", "<action 2>", "..."],
  "deadline": "<compliance deadline as a date string, or null if not specified>"
}}

Circular Title: {title}

Circular Text:
{text}

Respond ONLY with the JSON object. No markdown, no explanation, no preamble.
""".strip()


class GeminiResponseSchema(BaseModel):
    """Temporary schema to strictly validate Gemini's JSON output."""

    summary: str
    affected: str
    severity: Literal["Low", "Medium", "High", "Critical"]
    action_items: list[str]
    deadline: str | None


class GeminiSummarizer:
    """
    Wraps the Google Gemini API to generate structured compliance summaries.

    Each call to summarize() sends the extracted circular text to Gemini
    and returns a validated CircularSummary Pydantic model. If Gemini
    returns invalid JSON, the call is retried once. If the retry also
    fails, a CircularSummary with summary_error=True is returned so the
    UI can display a graceful degraded card.

    Args:
        settings: Application settings providing the API key and model name.
    """

    def __init__(self, settings: Settings) -> None:
        if GENAI_AVAILABLE:
            # Initialize Google SDK
            genai.configure(api_key=settings.google_api_key)
            self._model = genai.GenerativeModel(
                model_name=settings.gemini_model,
                system_instruction=_SYSTEM_INSTRUCTION,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )
        else:
            self._model = None
            logger.error("google-generativeai is not installed. AI summarization is disabled.")

    def summarize(self, meta: CircularMeta, text: str) -> CircularSummary:
        """
        Generate a structured compliance summary for a single RBI circular.

        Attempts to call Gemini and parse the response. On JSON parse
        failure, retries once. Returns a graceful error summary if both
        attempts fail or if the input text is empty.

        Args:
            meta: The circular's scraped metadata (title, date, pdf_url).
            text: The extracted plain text from the circular's PDF.

        Returns:
            A CircularSummary populated with AI-generated fields, or
            a CircularSummary with summary_error=True on failure.
        """
        if not GENAI_AVAILABLE:
            return self._build_error_summary(
                meta, "Google Generative AI SDK is not installed on this system."
            )

        if not text.strip():
            return self._build_error_summary(
                meta, "No readable text extracted from PDF."
            )

        prompt = _SUMMARIZE_PROMPT.format(title=meta.title, text=text)

        for attempt in range(1, 3):  # 1 initial attempt + 1 retry = 2 attempts total
            try:
                logger.debug(
                    "Calling Gemini API for circular %r (attempt %d/2).",
                    meta.title,
                    attempt,
                )
                raw_response = self._call_gemini(prompt)
                return self._parse_response(meta, raw_response)

            except json.JSONDecodeError as exc:
                logger.warning(
                    "Failed to parse Gemini JSON on attempt %d: %s", attempt, exc
                )
            except ValidationError as exc:
                logger.warning(
                    "Gemini output failed schema validation on attempt %d: %s",
                    attempt,
                    exc,
                )
            except Exception as exc:
                logger.error(
                    "Unexpected error calling Gemini API on attempt %d: %s",
                    attempt,
                    exc,
                    exc_info=True
                )
                # Fail immediately on generic exceptions (e.g., auth, networking)
                # to avoid pointless retries when the API is down.
                return self._build_error_summary(
                    meta, f"API communication failed: {exc}"
                )

        return self._build_error_summary(
            meta, "Gemini failed to return valid JSON after retries."
        )

    def _call_gemini(self, prompt: str) -> str:
        """
        Send a prompt to the Gemini API and return the raw text response.
        Automatically handles 429 Rate Limit Exceeded by sleeping for 32s.
        """
        try:
            response = self._model.generate_content(prompt)
        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "Quota exceeded" in err_str:
                logger.warning("Gemini API rate limit exceeded (429). Sleeping for 32 seconds before retrying...")
                time.sleep(32)
                response = self._model.generate_content(prompt)
            else:
                raise exc

        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        return response.text

    def _parse_response(self, meta: CircularMeta, raw_response: str) -> CircularSummary:
        """
        Parse and validate a raw Gemini JSON response into a CircularSummary.
        """
        # Defensive cleanup: strip potential markdown fences if the model
        # ignores the response_mime_type instruction
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        validated = GeminiResponseSchema(**data)

        return CircularSummary(
            title=meta.title,
            date=meta.date,
            pdf_url=meta.pdf_url,
            summary=validated.summary,
            affected=validated.affected,
            severity=validated.severity,
            action_items=validated.action_items,
            deadline=validated.deadline,
        )

    def _build_error_summary(self, meta: CircularMeta, reason: str) -> CircularSummary:
        """
        Construct a graceful fallback CircularSummary when AI summarization fails.
        """
        logger.warning(
            "Returning error summary for circular %r. Reason: %s",
            meta.title,
            reason,
        )
        return CircularSummary(
            title=meta.title,
            date=meta.date,
            pdf_url=meta.pdf_url,
            summary_error=True,
            error_message=reason,
        )
