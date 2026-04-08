"""
User-input sanitizer — first-line defense before user queries reach the
orchestrator or any LLM prompt.

The sanitizer is a pure function: it takes a raw user string and returns
a `SanitizationResult` with:
  - `cleaned`: the text safe to forward to downstream agents
  - `blocked`: True if the entire request must be rejected
  - `reasons`: human-readable reasons (for logs + audit trail)
  - `pii_matches`: redactions applied
  - `injection_matches`: prompt-injection hits

Policy decisions live here — change this file to tighten or relax the
security posture. Downstream agents trust the output.
"""

import logging
from dataclasses import dataclass, field

from backend.security.injection_patterns import detect_injection
from backend.security.pii_detector import redact_pii, PIIMatch

logger = logging.getLogger(__name__)

# Upper limit on input length. Longer inputs are a cheap DoS vector
# against token budgets and often signal an attack payload.
MAX_INPUT_LENGTH = 2000


@dataclass
class SanitizationResult:
    cleaned: str
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)
    pii_matches: list[PIIMatch] = field(default_factory=list)
    injection_matches: list[dict] = field(default_factory=list)


def sanitize_user_input(raw: str) -> SanitizationResult:
    """
    Sanitize a raw user query. Blocks critical-severity attacks and
    redacts PII. Caller should check `.blocked` before proceeding.
    """
    if raw is None:
        return SanitizationResult(cleaned="", blocked=True, reasons=["null input"])

    text = raw.strip()
    if not text:
        return SanitizationResult(cleaned="", blocked=True, reasons=["empty input"])

    reasons: list[str] = []

    # 1. Length cap — initial pass (may be re-applied after redaction
    # if PII placeholders push length back above the cap)
    if len(text) > MAX_INPUT_LENGTH:
        reasons.append(f"input truncated from {len(text)} to {MAX_INPUT_LENGTH} chars")
        text = text[:MAX_INPUT_LENGTH]

    # 2. Strip control characters except newline/tab
    cleaned_chars = []
    for ch in text:
        if ch == "\n" or ch == "\t" or ord(ch) >= 32:
            cleaned_chars.append(ch)
    text = "".join(cleaned_chars)

    # 3. Prompt injection detection
    injection_hits = detect_injection(text)
    if injection_hits:
        severities = {h["severity"] for h in injection_hits}
        if "critical" in severities:
            logger.warning("Blocking critical injection attempt: %s", injection_hits)
            return SanitizationResult(
                cleaned="",
                blocked=True,
                reasons=[f"critical prompt injection: {injection_hits[0]['pattern']}"],
                injection_matches=injection_hits,
            )
        # High / medium / low — log and continue with neutralized text
        reasons.append(
            f"injection patterns detected ({len(injection_hits)}): "
            + ", ".join(h["pattern"] for h in injection_hits)
        )

    # 4. PII redaction
    redacted, pii_matches = redact_pii(text)
    if pii_matches:
        reasons.append(f"{len(pii_matches)} PII token(s) redacted")
        text = redacted

    # 5. Final length cap — PII placeholders can grow the string past
    # the limit, and we must still honor MAX_INPUT_LENGTH downstream.
    if len(text) > MAX_INPUT_LENGTH:
        reasons.append(f"post-redaction re-truncation to {MAX_INPUT_LENGTH} chars")
        text = text[:MAX_INPUT_LENGTH]

    return SanitizationResult(
        cleaned=text,
        blocked=False,
        reasons=reasons,
        pii_matches=pii_matches,
        injection_matches=injection_hits,
    )
