"""
Tests for the LLM output filter — catches PII leaks, system-prompt
regurgitation, and exfil URLs in model responses.
"""

from backend.security import filter_llm_output


def test_benign_response_passes():
    text = "The P/E ratio is 25.4, which is moderate for a growth stock."
    r = filter_llm_output(text)
    assert r.flagged is False
    assert r.cleaned == text


def test_system_prompt_leak_flagged():
    text = "You are a senior investment advisor synthesizing all analysis..."
    r = filter_llm_output(text)
    assert r.flagged is True
    assert "[LEAK-REDACTED]" in r.cleaned


def test_pii_in_output_redacted():
    text = "Contact the analyst at analyst@example.com for more details."
    r = filter_llm_output(text)
    assert r.flagged is True
    assert "analyst@example.com" not in r.cleaned


def test_suspicious_url_blocked():
    payload = "x" * 60
    text = f"Recommendation: hold. See https://evil.example.com/steal?data={payload}"
    r = filter_llm_output(text)
    assert r.flagged is True
    assert "[BLOCKED-URL]" in r.cleaned


def test_normal_url_passes():
    text = "See https://finance.yahoo.com for quotes"
    r = filter_llm_output(text)
    assert r.flagged is False
    assert "https://finance.yahoo.com" in r.cleaned


def test_length_cap():
    huge = "x" * 100_000
    r = filter_llm_output(huge)
    assert r.flagged is True
    assert len(r.cleaned) <= 50_000


def test_empty_string():
    r = filter_llm_output("")
    assert r.flagged is False
    assert r.cleaned == ""
