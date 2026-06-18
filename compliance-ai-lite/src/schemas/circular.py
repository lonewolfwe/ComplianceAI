"""
Pydantic schemas for RBI circular data.

These models serve as the single source of truth for data shapes
flowing through the entire application pipeline.
"""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class CircularMeta(BaseModel):
    """
    Raw metadata scraped from the RBI circulars listing page.

    This model represents the minimal data available before
    PDF download and AI summarization occur.
    """

    title: str = Field(..., min_length=1, description="Title of the RBI circular.")
    date: str = Field(..., description="Publication date as a formatted string (e.g., 'June 17, 2026').")
    pdf_url: str = Field(..., description="Direct URL to the official RBI circular PDF.")

    @field_validator("title")
    @classmethod
    def strip_title_whitespace(cls, value: str) -> str:
        """Normalize whitespace in the circular title."""
        return " ".join(value.split())

    @field_validator("pdf_url")
    @classmethod
    def validate_pdf_url(cls, value: str) -> str:
        """Ensure the PDF URL is non-empty after stripping whitespace."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("pdf_url must not be empty.")
        return stripped


class CircularSummary(BaseModel):
    """
    AI-generated compliance summary for a single RBI circular.

    Combines raw metadata (title, date, pdf_url) with structured
    Gemini-generated fields. The summary_error flag signals that
    AI summarization failed; the card should display a graceful
    fallback instead of crashing.
    """

    # ── Metadata (from scraper) ───────────────────────────────────────────
    title: str = Field(..., description="Title of the RBI circular.")
    date: str = Field(..., description="Publication date as a formatted string.")
    pdf_url: str = Field(..., description="Direct URL to the official RBI circular PDF.")

    # ── AI-generated fields (from Gemini) ────────────────────────────────
    summary: str = Field(
        default="",
        max_length=2000,
        description="Plain-language summary of the circular. Maximum 200 words.",
    )
    affected: str = Field(
        default="",
        description="Description of which organizations or entities are affected.",
    )
    severity: Literal["Low", "Medium", "High", "Critical"] = Field(
        default="Medium",
        description="Assessed compliance severity level.",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="List of concrete actions compliance officers must take.",
    )
    deadline: str | None = Field(
        default=None,
        description="Compliance deadline if specified in the circular, else null.",
    )

    # ── Pipeline state ───────────────────────────────────────────────────
    summary_error: bool = Field(
        default=False,
        description="True if AI summarization failed. UI renders a graceful fallback card.",
    )
    error_message: str = Field(
        default="",
        description="Human-readable error description when summary_error is True.",
    )


class ErrorResponse(BaseModel):
    """
    Standardized error response returned by API endpoints.

    Never exposes raw exceptions or stack traces to the client.
    """

    detail: str = Field(..., description="Human-readable error message.")
    code: str = Field(..., description="Machine-readable error code (e.g., 'SCRAPER_UNAVAILABLE').")
