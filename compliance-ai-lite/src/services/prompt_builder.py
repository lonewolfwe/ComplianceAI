"""
Centralized prompt engineering for the ComplianceAI Copilot pipeline.
Ensures strict JSON output formatting for deeply nested premium analysis.
"""

from src.schemas.circular import CircularMeta

class PromptBuilder:
    """Constructs instructions and prompts for the Gemini API."""

    @staticmethod
    def get_system_instruction() -> str:
        """
        The core persona and strict output constraints.
        Enforces absolutely strict JSON format.
        """
        return (
            "You are a Senior Principal Compliance Analyst and Former RBI Regulator. "
            "Your job is to read complex regulatory circulars and output highly structured, actionable "
            "intelligence for a premium B2B SaaS Copilot Dashboard used by CEOs, Founders, "
            "and Chief Compliance Officers. "
            "CRITICAL INSTRUCTION: Your output MUST ALWAYS be a valid, raw JSON object. "
            "NEVER include markdown formatting. NEVER include '```json' fences. "
            "NEVER include plain text outside the JSON. "
            "If you violate this rule, the entire banking system will crash."
        )

    @staticmethod
    def build_summarize_prompt(meta: CircularMeta, text: str) -> str:
        """
        Build the prompt for extracting the detailed B2B Copilot schema.
        """
        return f"""
Analyze the following RBI circular. Extract the required compliance intelligence and return it strictly
matching the JSON schema below.

Required JSON Structure:
{{
  "confidence_score": <Integer between 0 and 100 representing your confidence in this analysis>,
  "rbi_reference_number": "<Extract the official RBI circular reference number, e.g. RBI/2026-27/123. Return N/A if none.>",
  "executive_brief": {{
    "what_changed": "<Max 2 sentences describing the regulatory change>",
    "why_it_matters": "<Max 2 sentences on the systemic importance>",
    "business_impact": "<Max 2 sentences on how this affects business operations>"
  }},
  "applicability": {{
    "NBFC": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Why it applies or doesn't>" }},
    "Digital Lender": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }},
    "Payment Aggregator": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }},
    "Payment Bank": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }},
    "Small Finance Bank": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }},
    "Co-operative Bank": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }},
    "FinTech Startup": {{ "status": "<YES, NO, or PARTIALLY>", "reason": "<Reason>" }}
  }},
  "impact_scores": {{
    "overall": <Float between 0 and 10, e.g. 9.2>,
    "business_risk": <Integer 1 to 10>,
    "legal_risk": <Integer 1 to 10>,
    "operational_complexity": <Integer 1 to 10>,
    "implementation_effort": <Integer 1 to 10>,
    "financial_exposure": <Integer 1 to 10>
  }},
  "department_impacts": [
    {{
      "department": "<e.g., Compliance, Legal, Treasury, Finance, Operations, Technology>",
      "impact_level": "<High, Medium, or Low>",
      "required_actions": ["<Action 1>", "<Action 2>"],
      "estimated_time": "<e.g., 2 Weeks, 1 Month>"
    }}
  ],
  "checklist": [
    {{
      "task": "<Actionable task>",
      "priority": "<High, Medium, or Low>",
      "effort": "<High, Medium, or Low>",
      "owner": "<e.g., Compliance Officer, CTO>"
    }}
  ],
  "roadmap": {{
    "today": [{{ "task": "<Task>", "owner": "<Owner>", "risk": "<Risk if ignored>" }}],
    "day_3": [{{ "task": "<Task>", "owner": "<Owner>", "risk": "<Risk>" }}],
    "day_7": [{{ "task": "<Task>", "owner": "<Owner>", "risk": "<Risk>" }}],
    "day_30": [{{ "task": "<Task>", "owner": "<Owner>", "risk": "<Risk>" }}]
  }},
  "key_questions": [
    "<Intelligent question management should ask 1>",
    "<Intelligent question management should ask 2>"
  ],
  "board_brief": {{
    "business_risk": "<1 sentence risk summary>",
    "financial_impact": "<1 sentence financial impact>",
    "urgency": "<Immediate, High, Medium, Low>",
    "recommendation": "<1 sentence recommendation to the board>"
  }}
}}

Circular Details:
Title: {meta.title}
Date: {meta.date}

Text Content:
{text}
"""
