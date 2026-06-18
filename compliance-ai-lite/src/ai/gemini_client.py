"""
Google Gemini AI client for ComplianceAI Lite.

Responsible exclusively for:
  1. Sending circular text to the Gemini API.
  2. Validating the JSON response against the CircularSummary schema.
  3. Retrying once on JSON parse failure.
  4. Returning a graceful fallback CircularSummary on total failure.

Does not scrape websites, download PDFs, or orchestrate the pipeline.
"""

import json
import logging

import google.generativeai as genai

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


class GeminiClient:
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
        genai.configure(api_key=settings.google_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        self._model_name: str = settings.gemini_model

    def summarize(self, meta: CircularMeta, text: str) -> CircularSummary:
        """
        Generate a structured compliance summary for a single RBI circular.

        Attempts to call Gemini and parse the response. On JSON parse
        failure, retries once. Returns a graceful error summary if both
        attempts fail.

        Args:
            meta: The circular's scraped metadata (title, date, pdf_url).
            text: The extracted plain text from the circular's PDF.

        Returns:
            A CircularSummary populated with AI-generated fields, or
            a CircularSummary with summary_error=True on failure.
        """
        raise NotImplementedError(
            "GeminiClient.summarize() will be implemented in Milestone 4."
        )

    def _call_gemini(self, prompt: str) -> str:
        """
        Send a prompt to the Gemini API and return the raw text response.

        Args:
            prompt: The fully-rendered prompt string to send.

        Returns:
            The raw text content of the Gemini response.

        Raises:
            Exception: Re-raises any exception from the Gemini SDK after logging.
        """
        raise NotImplementedError(
            "GeminiClient._call_gemini() will be implemented in Milestone 4."
        )

    def _parse_response(self, meta: CircularMeta, raw_response: str) -> CircularSummary:
        """
        Parse and validate a raw Gemini JSON response into a CircularSummary.

        Args:
            meta: The source circular metadata to embed in the summary.
            raw_response: The raw text returned by the Gemini API.

        Returns:
            A fully-populated CircularSummary Pydantic model.

        Raises:
            json.JSONDecodeError: If the response is not valid JSON.
            pydantic.ValidationError: If the JSON fields do not match the schema.
        """
        raise NotImplementedError(
            "GeminiClient._parse_response() will be implemented in Milestone 4."
        )

    def _build_error_summary(self, meta: CircularMeta, reason: str) -> CircularSummary:
        """
        Construct a graceful fallback CircularSummary when AI summarization fails.

        The returned summary has summary_error=True so the frontend can
        render an informative partial card rather than crashing.

        Args:
            meta: The source circular metadata.
            reason: A human-readable description of why summarization failed.

        Returns:
            A CircularSummary with summary_error=True and the failure reason.
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
