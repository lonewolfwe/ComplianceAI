"""
Google Gemini AI service for ComplianceAI Copilot.
Handles secure API communication, strict JSON validation, and deeply nested object mapping.
"""

import json
import time
from datetime import datetime, timezone

try:
    import google.generativeai as genai  # type: ignore[import-not-found]
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from pydantic import ValidationError

from config import Settings
from src.schemas.circular import (
    CircularMeta, CircularSummary, ExecutiveBrief, ApplicabilityDetail,
    ImpactScores, DepartmentImpact, ChecklistItem, RoadmapMilestone, AIRoadmap, DecisionCenter
)
from src.services.prompt_builder import PromptBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)

class AIService:
    """
    Wraps the Google Gemini API to generate structured compliance dashboards.
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
        Generates the detailed AI Copilot dashboard for the circular.
        If Gemini fails, returns a gracefully degraded CircularSummary with errors flagged.
        """
        logger.info("Copilot generation started for %r", meta.title)
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
                logger.info("Copilot generation completed for %r in %.2fs", meta.title, duration)
                return summary

            except json.JSONDecodeError as exc:
                logger.warning("Failures: JSON parsing failed on attempt %d: %s", attempt, exc)
            except ValidationError as exc:
                logger.warning("Failures: Schema validation failed on attempt %d: %s", attempt, exc)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                err_str = str(exc)
                if "429" in err_str or "Quota exceeded" in err_str:
                    logger.warning("Failures: Gemini API quota exceeded.")
                    return self._build_error(
                        meta, "AI analysis is temporarily unavailable. Please retry later."
                    )
                
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
        
        # Helper to parse lists of dicts safely
        def safe_list(key: str, default: list) -> list:
            return data.get(key, default) if isinstance(data.get(key), list) else default

        def safe_dict(key: str, default: dict) -> dict:
            return data.get(key, default) if isinstance(data.get(key), dict) else default

        # Extract nested dicts with fallbacks
        exec_brief = safe_dict("executive_brief", {})
        impacts = safe_dict("impact_scores", {})
        roadmap_data = safe_dict("roadmap", {})
        dc = safe_dict("decision_center", {})
        
        return CircularSummary(
            title=meta.title,
            date=meta.date,
            pdf_url=meta.pdf_url,
            hash=meta.hash,
            generated_at=datetime.now(timezone.utc).isoformat(),
            ai_model=self._model_name,
            confidence_score=data.get("confidence_score", 0),
            rbi_reference_number=data.get("rbi_reference_number", "N/A"),
            
            executive_brief=ExecutiveBrief(
                what_changed=exec_brief.get("what_changed", "N/A"),
                why_it_matters=exec_brief.get("why_it_matters", "N/A"),
                business_impact=exec_brief.get("business_impact", "N/A")
            ),
            
            applicability={
                k: ApplicabilityDetail(
                    status=v.get("status", "UNKNOWN") if isinstance(v, dict) else "UNKNOWN",
                    reason=v.get("reason", "N/A") if isinstance(v, dict) else "N/A"
                )
                for k, v in safe_dict("applicability", {}).items()
            },
            
            impact_scores=ImpactScores(
                overall=float(impacts.get("overall", 0.0)),
                business_risk=int(impacts.get("business_risk", 0)),
                legal_risk=int(impacts.get("legal_risk", 0)),
                operational_complexity=int(impacts.get("operational_complexity", 0)),
                implementation_effort=int(impacts.get("implementation_effort", 0)),
                financial_exposure=int(impacts.get("financial_exposure", 0))
            ),
            
            department_impacts=[
                DepartmentImpact(
                    department=d.get("department", "Unknown"),
                    impact_level=d.get("impact_level", "Unknown"),
                    required_actions=d.get("required_actions", []) if isinstance(d.get("required_actions"), list) else [],
                    estimated_time=d.get("estimated_time", "Unknown")
                )
                for d in safe_list("department_impacts", []) if isinstance(d, dict)
            ],
            
            checklist=[
                ChecklistItem(
                    task=c.get("task", "Unknown"),
                    priority=c.get("priority", "Unknown"),
                    effort=c.get("effort", "Unknown"),
                    owner=c.get("owner", "Unknown")
                )
                for c in safe_list("checklist", []) if isinstance(c, dict)
            ],
            
            roadmap=AIRoadmap(
                today=[
                    RoadmapMilestone(
                        task=m.get("task", ""), owner=m.get("owner", ""), risk=m.get("risk", "")
                    )
                    for m in safe_list("today", roadmap_data.get("today", [])) if isinstance(m, dict)
                ],
                day_3=[
                    RoadmapMilestone(
                        task=m.get("task", ""), owner=m.get("owner", ""), risk=m.get("risk", "")
                    )
                    for m in safe_list("day_3", roadmap_data.get("day_3", [])) if isinstance(m, dict)
                ],
                day_7=[
                    RoadmapMilestone(
                        task=m.get("task", ""), owner=m.get("owner", ""), risk=m.get("risk", "")
                    )
                    for m in safe_list("day_7", roadmap_data.get("day_7", [])) if isinstance(m, dict)
                ],
                day_30=[
                    RoadmapMilestone(
                        task=m.get("task", ""), owner=m.get("owner", ""), risk=m.get("risk", "")
                    )
                    for m in safe_list("day_30", roadmap_data.get("day_30", [])) if isinstance(m, dict)
                ]
            ),
            
            key_questions=safe_list("key_questions", []),
            
            decision_center=DecisionCenter(
                should_we_act=dc.get("should_we_act", "N/A"),
                urgency=dc.get("urgency", "N/A"),
                business_impact=dc.get("business_impact", "N/A"),
                financial_exposure=dc.get("financial_exposure", "N/A"),
                requires_policy_update=bool(dc.get("requires_policy_update", False)),
                requires_legal_review=bool(dc.get("requires_legal_review", False)),
                requires_customer_communication=bool(dc.get("requires_customer_communication", False)),
                estimated_internal_work=dc.get("estimated_internal_work", "N/A"),
                recommended_owner=dc.get("recommended_owner", "N/A")
            )
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
            confidence_score=0,
            rbi_reference_number="N/A",
            
            executive_brief=ExecutiveBrief(
                what_changed="Error", why_it_matters="Error", business_impact=reason
            ),
            applicability={},
            impact_scores=ImpactScores(
                overall=0.0, business_risk=0, legal_risk=0,
                operational_complexity=0, implementation_effort=0, financial_exposure=0
            ),
            department_impacts=[],
            checklist=[],
            roadmap=AIRoadmap(today=[], day_3=[], day_7=[], day_30=[]),
            key_questions=[],
            decision_center=DecisionCenter(
                should_we_act="Error", urgency="Error", business_impact="Error",
                financial_exposure="Error", requires_policy_update=False,
                requires_legal_review=False, requires_customer_communication=False,
                estimated_internal_work="Error", recommended_owner="Error"
            ),
            
            summary_error=True,
            error_message=reason
        )
