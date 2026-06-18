"""
Centralized prompt engineering for the ComplianceAI generation pipeline.
Ensures strict JSON output formatting and detailed compliance analysis.
"""

from src.schemas.circular import CircularMeta

class PromptBuilder:
    """Constructs instructions and prompts for the Gemini API."""

    @staticmethod
    def get_system_instruction() -> str:
        """
        The core persona and strict output constraints.
        Enforces absolutely strict JSON format (no markdown fences, no text).
        """
        return (
            "You are a Principal Compliance Analyst for the Reserve Bank of India (RBI). "
            "Your job is to read complex regulatory circulars and output highly structured, actionable intelligence. "
            "CRITICAL INSTRUCTION: Your output MUST ALWAYS be a valid, raw JSON object. "
            "NEVER include markdown formatting. NEVER include '```json' fences. NEVER include plain text outside the JSON. "
            "If you violate this rule, the system will crash."
        )

    @staticmethod
    def build_summarize_prompt(meta: CircularMeta, text: str) -> str:
        """
        Build the prompt for extracting the detailed schema from the circular text.
        """
        return f"""
Analyze the following RBI circular. Extract the required compliance intelligence and return it strictly matching the JSON schema below.

Required JSON Structure:
{{
  "summary": "<A plain-language summary of the circular's core directive in 3-5 sentences>",
  "impact_score": "<Must be exactly one of: Low, Medium, High, Critical>",
  "departments": ["<Department 1>", "<Department 2>"],
  "questions": ["<Question 1 compliance teams should ask>", "<Question 2>"],
  "roadmap": ["<Step 1 for compliance>", "<Step 2>"],
  "executive_brief": "<A 1-sentence TL;DR for C-level executives>",
  "checklist": ["<Actionable checklist item 1>", "<Actionable checklist item 2>"]
}}

Circular Details:
Title: {meta.title}
Date: {meta.date}

Text Content:
{text}
"""
