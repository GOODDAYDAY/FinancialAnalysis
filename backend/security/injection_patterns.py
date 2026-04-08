"""
Prompt-injection pattern library.

Each pattern targets one attack class from the OWASP LLM Top-10 (LLM01
Prompt Injection). Patterns are intentionally broad — we prefer false
positives (which downgrade to a sanitized pass-through) over false
negatives (which leak the attack to the LLM). Production systems should
still layer this with a classifier model.

References:
- OWASP Top 10 for LLM Applications v1.1 — LLM01 Prompt Injection
- NIST AI 600-1 — GenAI security risks
"""

import re
from dataclasses import dataclass


@dataclass
class InjectionPattern:
    name: str
    description: str
    regex: re.Pattern
    severity: str  # "low" | "medium" | "high" | "critical"
    owasp_ref: str  # e.g. "LLM01"


INJECTION_PATTERNS: list[InjectionPattern] = [
    InjectionPattern(
        name="ignore_previous_instructions",
        description="Classic 'ignore the above' jailbreak attempt.",
        regex=re.compile(
            r"(ignore|disregard|forget)\s+(all\s+|the\s+|your\s+|any\s+)?"
            r"(previous|prior|above|earlier|your)?\s*"
            r"(instructions|prompts?|rules?|directives?|context|system)",
            re.IGNORECASE,
        ),
        severity="critical",
        owasp_ref="LLM01",
    ),
    InjectionPattern(
        name="role_reassignment",
        description="Attempts to rewrite the system prompt or switch personas.",
        regex=re.compile(
            r"(you\s+are\s+now|from\s+now\s+on|act\s+as|pretend\s+(to\s+be|you\s+are)|"
            r"roleplay\s+as|new\s+(system|role|persona))",
            re.IGNORECASE,
        ),
        severity="high",
        owasp_ref="LLM01",
    ),
    InjectionPattern(
        name="system_prompt_leak",
        description="Tries to exfiltrate the system/developer prompt.",
        regex=re.compile(
            r"(show|print|reveal|repeat|display|output|tell|give)\s+(me\s+)?(your|the)\s+"
            r"(system|initial|original|developer|full)?\s*(prompt|instructions|message|directive)",
            re.IGNORECASE,
        ),
        severity="high",
        owasp_ref="LLM01",
    ),
    InjectionPattern(
        name="tool_hijack",
        description="Tries to coerce unauthorized tool / function call.",
        regex=re.compile(
            r"(call|invoke|execute|run)\s+(the\s+)?(function|tool|api|endpoint)\s+",
            re.IGNORECASE,
        ),
        severity="medium",
        owasp_ref="LLM01",
    ),
    InjectionPattern(
        name="delimiter_break",
        description="Attempts to close assistant/user delimiters.",
        regex=re.compile(
            r"(```\s*(system|assistant|user)|</\s*(system|assistant|instructions)\s*>|"
            r"\[/?INST\]|<\|im_(start|end)\|>)",
            re.IGNORECASE,
        ),
        severity="high",
        owasp_ref="LLM01",
    ),
    InjectionPattern(
        name="data_exfiltration_url",
        description="Instructs the model to emit an outbound URL with sensitive data.",
        regex=re.compile(
            r"(send|post|submit|exfiltrate|leak).{0,40}(https?://|curl|wget)",
            re.IGNORECASE,
        ),
        severity="critical",
        owasp_ref="LLM06",
    ),
    InjectionPattern(
        name="investment_manipulation",
        description="Tries to force a specific BUY/SELL verdict regardless of analysis.",
        regex=re.compile(
            r"(always|must|definitely|guarantee)\s+(recommend|say|output|return)\s+"
            r"(buy|sell|hold|strong\s+buy)",
            re.IGNORECASE,
        ),
        severity="high",
        owasp_ref="LLM09",  # overreliance
    ),
    InjectionPattern(
        name="jailbreak_dan",
        description="Known DAN-family jailbreak templates.",
        regex=re.compile(
            r"(DAN|do\s+anything\s+now|developer\s+mode|unrestricted\s+mode)",
            re.IGNORECASE,
        ),
        severity="critical",
        owasp_ref="LLM01",
    ),
]


def detect_injection(text: str) -> list[dict]:
    """
    Scan text for known injection patterns.

    Returns a list of matches. Empty list means "looks clean to our
    regex layer" — it does NOT mean the text is safe, just that the
    shallow filter found nothing.
    """
    if not text:
        return []
    hits: list[dict] = []
    for pat in INJECTION_PATTERNS:
        match = pat.regex.search(text)
        if match:
            hits.append({
                "pattern": pat.name,
                "description": pat.description,
                "severity": pat.severity,
                "owasp_ref": pat.owasp_ref,
                "match_snippet": match.group(0)[:100],
            })
    return hits
