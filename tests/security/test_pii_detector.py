"""
Tests for backend.security.pii_detector.

We care about three things:
  1. Known PII types are detected (no false negatives on the obvious stuff)
  2. Benign finance text does not trigger false positives
  3. redact_pii produces a clean output with no PII remaining
"""

import pytest

from backend.security import detect_pii, redact_pii


@pytest.mark.parametrize("text,expected_type", [
    ("Contact me at alice@example.com for details", "email"),
    ("Call me at +1-415-555-0199", "phone_intl"),
    ("My phone is 13812345678", "phone_cn_mobile"),
    ("身份证号: 110101199001011234", "cn_id_card"),
    ("Card: 4111-1111-1111-1111", "credit_card"),
    ("Server IP is 192.168.1.100", "ipv4"),
    ("Key: sk-abcdef1234567890abcdef1234567890", "api_key_sk"),
    ("Hash: " + "a" * 40, "long_hex_secret"),
])
def test_known_pii_detected(text, expected_type):
    matches = detect_pii(text)
    types = {m.type for m in matches}
    assert expected_type in types, f"Missed {expected_type} in: {text}"


@pytest.mark.parametrize("text", [
    "Analyze Tesla (TSLA) stock fundamentals",
    "What is the P/E ratio of 600519?",
    "RSI is 45.2 and MACD is bullish",
    "Price: $150.25, volume 1000000",
])
def test_benign_finance_text(text):
    matches = detect_pii(text)
    assert matches == [], f"False positive: {matches} on {text!r}"


def test_redact_pii_removes_all_matches():
    text = "Contact alice@example.com or 13812345678"
    redacted, matches = redact_pii(text)
    assert len(matches) == 2
    assert "alice@example.com" not in redacted
    assert "13812345678" not in redacted
    assert "[REDACTED:email" in redacted
    assert "[REDACTED:phone_cn_mobile" in redacted


def test_redact_empty_text():
    out, matches = redact_pii("")
    assert out == ""
    assert matches == []
