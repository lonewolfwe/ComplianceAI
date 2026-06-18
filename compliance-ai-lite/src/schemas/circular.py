"""
Data schemas for RBI Circulars (Copilot Edition).
"""

import hashlib
from typing import Any, Dict, List
from pydantic import BaseModel, Field

class CircularMeta(BaseModel):
    """Metadata for a circular, fetched quickly from the homepage without AI."""
    title: str = Field(..., min_length=1)
    date: str
    pdf_url: str
    hash: str = Field(default="")

    def model_post_init(self, context: Any) -> None:
        if not self.hash:
            raw = f"{self.pdf_url}_{self.date}".encode("utf-8")
            self.hash = hashlib.sha256(raw).hexdigest()[:16]

class ExecutiveBrief(BaseModel):
    """Summarizes the key points and impact of the circular."""
    what_changed: str
    why_it_matters: str
    business_impact: str

class ApplicabilityDetail(BaseModel):
    """Details whether a circular applies to a specific company type."""
    status: str  # YES, PARTIALLY, NO
    reason: str

class ImpactScores(BaseModel):
    """Granular scores representing various risks and complexities."""
    overall: float
    business_risk: int
    legal_risk: int
    operational_complexity: int
    implementation_effort: int
    financial_exposure: int

class DepartmentImpact(BaseModel):
    """Impact analysis specific to a single organizational department."""
    department: str
    impact_level: str
    required_actions: List[str]
    estimated_time: str

class ChecklistItem(BaseModel):
    """An actionable compliance task."""
    task: str
    priority: str
    effort: str
    owner: str

class RoadmapMilestone(BaseModel):
    """A specific milestone in the implementation roadmap."""
    task: str
    owner: str
    risk: str

class AIRoadmap(BaseModel):
    """Timeline of required compliance actions."""
    today: List[RoadmapMilestone]
    day_3: List[RoadmapMilestone]
    day_7: List[RoadmapMilestone]
    day_30: List[RoadmapMilestone]

class BoardBrief(BaseModel):
    """High-level summary intended for the Board of Directors."""
    business_risk: str
    financial_impact: str
    urgency: str
    recommendation: str

class CircularSummary(BaseModel):
    """The fully detailed AI-generated compliance dashboard payload."""
    title: str
    date: str
    pdf_url: str
    hash: str
    generated_at: str
    ai_model: str
    confidence_score: int
    rbi_reference_number: str

    executive_brief: ExecutiveBrief
    applicability: Dict[str, ApplicabilityDetail]
    impact_scores: ImpactScores
    department_impacts: List[DepartmentImpact]
    checklist: List[ChecklistItem]
    roadmap: AIRoadmap
    key_questions: List[str]
    board_brief: BoardBrief

    # Graceful degradation fields
    summary_error: bool = False
    error_message: str | None = None

class ErrorResponse(BaseModel):
    """Standardized API error response format."""
    detail: str
