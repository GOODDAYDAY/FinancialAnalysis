"""
PII detection and redaction.

Regex-based, deliberately conservative — designed to catch obvious PII
leaks before they land in LLM prompts or audit logs. Not a replacement
for a proper DLP system; this is the first layer of defense.

Covered PII types (tuned for a global finance app with CN/EN users):
  - Email addresses
  - Phone numbers (international + Chinese mobile)
  - Chinese National ID (18-digit, with checksum-aware regex)
  - Credit card numbers (generic 13-19 digit)
  - IPv4 addresses
  - Generic API keys / secrets (sk-... style, long hex)
"""

import re
from dataclasses import dataclass


@dataclass
class PIIMatch:
    type: str
    value: str
    start: int
    end: int
    masked: str


# Compiled once at import — patterns are case-insensitive where safe.
_PATTERNS = {
    "email": re.compile(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    ),
    "phone_intl": re.compile(
        r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
    ),
    "phone_cn_mobile": re.compile(
        r"(?<!\d)1[3-9]\d{9}(?!\d)"
    ),
    "cn_id_card": re.compile(
        r"(?<!\d)[1-9]\d{5}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
    ),
    "credit_card": re.compile(
        r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)"
    ),
    "ipv4": re.compile(
        r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)"
    ),
    "api_key_sk": re.compile(
        r"sk-[a-zA-Z0-9]{20,}"
    ),
    "long_hex_secret": re.compile(
        r"(?<![a-fA-F0-9])[a-fA-F0-9]{32,}(?![a-fA-F0-9])"
    ),
}


def _mask(value: str) -> str:
    """Keep first 2 and last 2 chars, replace rest with *."""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def detect_pii(text: str) -> list[PIIMatch]:
    """
    Return non-overlapping PII matches.

    Multiple regexes can match the same span (e.g. 13812345678 matches
    both phone_intl and phone_cn_mobile). We keep the longest / most
    specific match per span and drop the rest — otherwise redaction
    double-counts and tests break.
    """
    if not text:
        return []
    raw: list[PIIMatch] = []
    for pii_type, pattern in _PATTERNS.items():
        for m in pattern.finditer(text):
            val = m.group(0)
            raw.append(PIIMatch(
                type=pii_type,
                value=val,
                start=m.start(),
                end=m.end(),
                masked=_mask(val),
            ))

    # Priority: more specific types win on ties (same span, same length)
    _priority = {
        "cn_id_card": 0,
        "credit_card": 1,
        "api_key_sk": 2,
        "email": 3,
        "phone_cn_mobile": 4,
        "phone_intl": 5,
        "long_hex_secret": 6,
        "ipv4": 7,
    }
    # Sort by (start asc, length desc, priority asc) then greedy pick
    raw.sort(key=lambda x: (x.start, -(x.end - x.start), _priority.get(x.type, 99)))
    picked: list[PIIMatch] = []
    last_end = -1
    for m in raw:
        if m.start >= last_end:
            picked.append(m)
            last_end = m.end
    return picked


def redact_pii(text: str) -> tuple[str, list[PIIMatch]]:
    """
    Replace every PII occurrence with a masked placeholder.

    Returns (redacted_text, matches). Matches are returned for audit
    logging even though the text itself no longer contains them.
    """
    if not text:
        return text, []

    matches = detect_pii(text)
    if not matches:
        return text, []

    # Sort by start desc so replacements don't shift subsequent indices
    matches_sorted = sorted(matches, key=lambda m: m.start, reverse=True)
    out = text
    for m in matches_sorted:
        placeholder = f"[REDACTED:{m.type}:{m.masked}]"
        out = out[:m.start] + placeholder + out[m.end:]
    return out, matches
