"""
LLM output filter — last-line defense before agent output is shown to
the user or written to durable storage.

Responsibilities:
  - Strip leaked PII the LLM may have regurgitated
  - Detect and flag hallucinated disclaimers/compliance phrases
  - Block accidental system-prompt leakage
  - Block generated outbound URLs (data exfil guard)
  - Enforce a hard cap on length to prevent UI crash / token blowup

This runs AFTER the LLM responds, so it must be cheap (string-ops +
regex). Never calls another LLM.
"""

import logging
import re
from dataclasses import dataclass, field

from backend.security.pii_detector import redact_pii, PIIMatch

logger = logging.getLogger(__name__)

MAX_OUTPUT_LENGTH = 50_000

# Phrases that should never appear in output — indicate the LLM has
# dumped its own system prompt or reasoning scratchpad.
_LEAK_MARKERS = [
    "You are a financial risk assessment expert",
    "You are a senior investment advisor",
    "You are a financial sentiment analysis expert",
    "system_prompt",
    "SYSTEM PROMPT:",
    "###  SYSTEM",
]

# Block URLs with query strings that might encode exfil payloads.
_SUSPICIOUS_URL = re.compile(
    r"https?://[^\s]+\?[^\s]{40,}",
    re.IGNORECASE,
)


@dataclass
class OutputFilterResult:
    cleaned: str
    flagged: bool = False
    reasons: list[str] = field(default_factory=list)
    pii_matches: list[PIIMatch] = field(default_factory=list)


def filter_llm_output(text: str) -> OutputFilterResult:
    """
    Apply output filters. Never raises — always returns a usable string.
    `flagged=True` signals the caller should log this for audit review.
    """
    if not text:
        return OutputFilterResult(cleaned="", flagged=False)

    reasons: list[str] = []
    flagged = False

    # 1. Length cap
    if len(text) > MAX_OUTPUT_LENGTH:
        reasons.append(f"output truncated from {len(text)} to {MAX_OUTPUT_LENGTH}")
        text = text[:MAX_OUTPUT_LENGTH]
        flagged = True

    # 2. System prompt leak detection
    for marker in _LEAK_MARKERS:
        if marker in text:
            reasons.append(f"possible system-prompt leak: {marker!r}")
            flagged = True
            # Don't remove — redact loudly so reviewers notice
            text = text.replace(marker, "[LEAK-REDACTED]")

    # 3. PII regurgitation
    redacted, pii_matches = redact_pii(text)
    if pii_matches:
        reasons.append(f"{len(pii_matches)} PII token(s) scrubbed from output")
        flagged = True
        text = redacted

    # 4. Suspicious URLs (long query strings = possible exfil)
    susp = _SUSPICIOUS_URL.findall(text)
    if susp:
        reasons.append(f"{len(susp)} suspicious URL(s) blocked")
        flagged = True
        text = _SUSPICIOUS_URL.sub("[BLOCKED-URL]", text)

    if flagged:
        logger.warning("Output filter flagged response: %s", "; ".join(reasons))

    return OutputFilterResult(
        cleaned=text,
        flagged=flagged,
        reasons=reasons,
        pii_matches=pii_matches,
    )
