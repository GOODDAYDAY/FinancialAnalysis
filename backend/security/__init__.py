"""
AI security module — input sanitization, PII detection, output filtering,
prompt-injection pattern library. Used by agents at LLM boundaries.

Design goal: a single place for all defensive controls so the MLSecOps
audit and the risk register can point at concrete, testable code.
"""

from backend.security.sanitizer import (
    sanitize_user_input,
    SanitizationResult,
)
from backend.security.pii_detector import (
    detect_pii,
    redact_pii,
    PIIMatch,
)
from backend.security.output_filter import (
    filter_llm_output,
    OutputFilterResult,
)
from backend.security.injection_patterns import (
    INJECTION_PATTERNS,
    detect_injection,
)

__all__ = [
    "sanitize_user_input",
    "SanitizationResult",
    "detect_pii",
    "redact_pii",
    "PIIMatch",
    "filter_llm_output",
    "OutputFilterResult",
    "INJECTION_PATTERNS",
    "detect_injection",
]
