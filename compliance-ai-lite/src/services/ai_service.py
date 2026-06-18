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

try:
    from google.api_core import exceptions as google_exceptions  # type: ignore[import-not-found]
except ImportError:
    google_exceptions = None

from pydantic import ValidationError

from config import Settings
from src.schemas.circular import (
    CircularMeta, CircularSummary, ExecutiveBrief, ApplicabilityDetail,
    ImpactScores, DepartmentImpact, ChecklistItem, RoadmapMilestone, AIRoadmap, DecisionCenter, EvidenceItem
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

    def _parse_gemini_error(self, exc: Exception) -> tuple[int, str]:
        """Maps an exception to an HTTP status code and a developer recommendation."""
        code = 500
        msg = str(exc)
        
        if google_exceptions and isinstance(exc, google_exceptions.GoogleAPICallError):
            if exc.code is not None:
                code = exc.code
            msg = exc.message or str(exc)
        else:
            err_str = str(exc).lower()
            if "401" in err_str or "unauthenticated" in err_str or "api key" in err_str:
                code = 401
            elif "403" in err_str or "permission" in err_str:
                code = 403
            elif "429" in err_str or "quota" in err_str or "resource" in err_str or "exhausted" in err_str:
                code = 429
            elif "404" in err_str or "not found" in err_str or "model" in err_str:
                code = 404
            elif "408" in err_str or "timeout" in err_str or "deadline" in err_str:
                code = 408
            elif "503" in err_str or "unavailable" in err_str:
                code = 503
            elif "500" in err_str or "internal" in err_str:
                code = 500

        if code == 401:
            rec = "Invalid API key. Please check your GOOGLE_API_KEY environment variable."
        elif code == 403:
            rec = "Permission denied. Ensure the API key has correct permissions for the Gemini API."
        elif code == 404:
            rec = "Wrong model. The configured model was not found or is unavailable."
        elif code == 408:
            rec = "Request timeout. The connection to Gemini timed out. Please try again."
        elif code == 429:
            rec = "Quota exceeded. You have hit the Gemini API rate limit."
        elif code == 500:
            rec = "Gemini internal error. Google's servers encountered an error. Please try again later."
        elif code == 503:
            rec = "Model unavailable. The model is temporarily overloaded or down. Please try again later."
        else:
            rec = f"API communication failed: {msg}"
            
        return code, rec

    def generate_summary(self, meta: CircularMeta, text: str) -> CircularSummary:
        """
        Generates the detailed AI Copilot dashboard for the circular.
        If Gemini fails, returns a gracefully degraded CircularSummary with errors flagged.
        """
        logger.info("Copilot generation started for %r", meta.title)
        start_time = time.time()

        if not GENAI_AVAILABLE:
            return self._build_error(meta, "AI SDK not installed.")

        # Step 5: Validate extracted text length
        cleaned_text = text.strip()
        if len(cleaned_text) < 100:
            logger.warning("Extracted text has only %d characters (minimum 100 required). Skipping Gemini call.", len(cleaned_text))
            return self._build_error(meta, "No readable text extracted.")

        prompt = PromptBuilder.build_summarize_prompt(meta, cleaned_text)
        prompt_length = len(prompt)
        input_tokens = prompt_length // 4  # Estimate input tokens: ~4 chars per token

        fallback_models = [
            self._model_name,
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash-8b",
        ]
        # Keep unique models in order
        unique_models = []
        for m in fallback_models:
            if m and m not in unique_models:
                unique_models.append(m)

        last_error_code = 500
        last_recommendation = "API call failed."
        last_model_used = self._model_name

        from src.utils.diagnostics import diagnostics_tracker

        for model_name in unique_models:
            last_model_used = model_name
            logger.info("Attempting AI generation with model: %s", model_name)
            
            try:
                model = genai.GenerativeModel(
                    model_name=model_name,
                    system_instruction=PromptBuilder.get_system_instruction(),
                    generation_config=genai.types.GenerationConfig(
                        response_mime_type="application/json",
                    ),
                )
            except Exception as e:
                logger.error("Failed to initialize model %s: %s", model_name, e)
                continue

            # Exponential backoff loop: Wait 2, 4, 8, 16 seconds. Max 3 retries (total 4 attempts per model).
            backoff_seconds = [2, 4, 8, 16]
            max_retries = 3

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    wait_time = backoff_seconds[attempt - 1]
                    logger.info("Retrying model %s in %ds (attempt %d/%d) due to quota/temporary failures...", model_name, wait_time, attempt, max_retries)
                    time.sleep(wait_time)

                req_start = time.time()
                try:
                    logger.info("[%s] Gemini request started", datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"))
                    response = model.generate_content(prompt)
                    req_duration = time.time() - req_start

                    if not response.text:
                        raise ValueError("Gemini returned an empty response.")
                    
                    raw_response = response.text
                    response_size = len(raw_response)

                    # Step 6: Log Metrics
                    logger.info("[%s] Gemini returned HTTP 200", datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"))
                    logger.info(
                        "Gemini Metrics — Model: %s, Duration: %.2fs, Input tokens est: %d, Prompt length: %d, Response size: %d",
                        model_name, req_duration, input_tokens, prompt_length, response_size
                    )

                    # Parse and validate JSON
                    summary = self._parse_and_build(meta, raw_response, model_name)
                    
                    # Log successful request in diagnostics
                    diagnostics_tracker.record_request(req_duration, success=True)
                    logger.info("[%s] JSON validated", datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"))

                    duration = time.time() - start_time
                    logger.info("Copilot generation completed for %r in %.2fs using %s", meta.title, duration, model_name)
                    return summary

                except json.JSONDecodeError as exc:
                    req_duration = time.time() - req_start
                    logger.warning("Failures: JSON parsing failed on model %s: %s", model_name, exc)
                    last_error_code = 500
                    last_recommendation = f"Gemini returned invalid JSON: {exc}"
                    diagnostics_tracker.record_request(req_duration, success=False, error_msg=last_recommendation)
                except ValidationError as exc:
                    req_duration = time.time() - req_start
                    logger.warning("Failures: Schema validation failed on model %s: %s", model_name, exc)
                    last_error_code = 500
                    last_recommendation = f"Schema validation failed: {exc}"
                    diagnostics_tracker.record_request(req_duration, success=False, error_msg=last_recommendation)
                except Exception as exc:
                    req_duration = time.time() - req_start
                    code, rec = self._parse_gemini_error(exc)
                    logger.error("Failures: Gemini error on model %s (code %d): %s — Recommendation: %s", model_name, code, exc, rec)
                    last_error_code = code
                    last_recommendation = rec
                    diagnostics_tracker.record_request(req_duration, success=False, error_msg=rec)

                    # Parse Retry-After if 429
                    if code == 429:
                        retry_after = None
                        if hasattr(exc, "response") and exc.response:
                            headers = getattr(exc.response, "headers", {})
                            if "Retry-After" in headers:
                                try:
                                    retry_after = int(headers["Retry-After"])
                                except ValueError:
                                    pass
                        if retry_after is not None:
                            logger.info("Retry-After header found: waiting %d seconds.", retry_after)
                            time.sleep(retry_after)
                    else:
                        break

        # If we reached here, all attempts and models failed
        logger.error("Failures: All model fallbacks failed. Last model: %s, Last error code: %d, Recommendation: %s", last_model_used, last_error_code, last_recommendation)
        
        # If it is 429, we should return a specific message so the caller knows it is queued/exhausted
        if last_error_code == 429:
            return self._build_error(meta, "Analysis queued.")
        
        return self._build_error(meta, last_recommendation)

    def _call_gemini(self, prompt: str) -> str:
        """Calls Gemini and handles raw response."""
        response = self._model.generate_content(prompt)
        if not response.text:
            raise ValueError("Gemini returned an empty response.")
        return response.text

    def _parse_and_build(self, meta: CircularMeta, raw_response: str, model_name: str | None = None) -> CircularSummary:
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
            ai_model=model_name or self._model_name,
            confidence_score=data.get("confidence_score", 0),
            rbi_reference_number=data.get("rbi_reference_number", "N/A"),
            
            executive_brief=ExecutiveBrief(
                what_changed=exec_brief.get("what_changed", "N/A"),
                why_it_matters=exec_brief.get("why_it_matters", "N/A"),
                business_impact=exec_brief.get("business_impact", "N/A")
            ),
            
            ceo_brief=data.get("ceo_brief", "N/A"),
            compliance_impact=data.get("compliance_impact", "N/A"),
            
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
            
            questions_management_should_ask=safe_list("questions_management_should_ask", []),
            
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
            ),
            evidence=[
                EvidenceItem(
                    quote=ev.get("quote", ""),
                    section=ev.get("section", ""),
                    page_number=str(ev.get("page_number", "Page 1"))
                )
                for ev in safe_list("evidence", []) if isinstance(ev, dict)
            ]
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
            rbi_reference_number=meta.circular_number or "N/A",
            
            executive_brief=ExecutiveBrief(
                what_changed="Compliance review is underway.", 
                why_it_matters="The circular is queued for processing.", 
                business_impact="Review document details and metadata in the workspace."
            ),
            ceo_brief="AI analysis is currently being generated. You can continue reviewing the circular using the compliance workspace.",
            compliance_impact="Asynchronous analysis is processing. The compliance team can track, assign, and update compliance tasks manually in the action items panel.",
            applicability={},
            impact_scores=ImpactScores(
                overall=0.0, business_risk=0, legal_risk=0,
                operational_complexity=0, implementation_effort=0, financial_exposure=0
            ),
            department_impacts=[],
            checklist=[],
            roadmap=AIRoadmap(today=[], day_3=[], day_7=[], day_30=[]),
            questions_management_should_ask=[],
            decision_center=DecisionCenter(
                should_we_act="PENDING", urgency="PENDING", business_impact="PENDING",
                financial_exposure="PENDING", requires_policy_update=False,
                requires_legal_review=False, requires_customer_communication=False,
                estimated_internal_work="PENDING", recommended_owner="Compliance Head"
            ),
            evidence=[],
            
            summary_error=True,
            error_message=reason
        )
