"""
Data schemas for RBI Circulars.
"""

from typing import Any
from pydantic import BaseModel, Field

class CircularMeta(BaseModel):
    """Metadata for a circular, fetched quickly from the homepage without AI."""
    title: str = Field(..., min_length=1)
    date: str
    pdf_url: str
    hash: str = Field(default="")

    def model_post_init(self, __context: Any) -> None:
        if not self.hash:
            import hashlib
            raw = f"{self.pdf_url}_{self.date}".encode("utf-8")
            self.hash = hashlib.sha256(raw).hexdigest()[:16]

class CircularSummary(BaseModel):
    """The fully detailed AI-generated summary, loaded lazily and cached."""
    title: str
    date: str
    pdf_url: str
    hash: str
    generated_at: str
    ai_model: str
    
    summary: str
    impact_score: str
    departments: list[str]
    questions: list[str]
    roadmap: list[str]
    executive_brief: str
    checklist: list[str]

    # Graceful degradation fields
    summary_error: bool = False
    error_message: str | None = None

class ErrorResponse(BaseModel):
    """Standardized API error response format."""
    detail: str
