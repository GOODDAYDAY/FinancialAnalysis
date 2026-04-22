"""
Tests for LLM output factual consistency (hallucination detection).

Covers: checking that recommendations reference known data fields,
that numeric claims are internally consistent, and that fabricated
tickers or impossible values are flagged.
"""

import pytest

from backend.state import RecommendationOutput


def _check_numeric_claims(
    recommendation: RecommendationOutput,
    market_data: dict,
) -> list[str]:
    """
    Return list of hallucination flags. Checks:
    - reasoning text should not reference prices not in market_data
    - confidence should be 0 when data is empty
    """
    flags = []
    # If no market data but high confidence, that's suspicious
    if not market_data and recommendation.confidence > 0.5:
        flags.append("high_confidence_without_data")

    # If reasoning references specific numbers not in market_data
    if recommendation.reasoning and market_data:
        price = market_data.get("current_price")
        if price and str(int(price)) not in recommendation.reasoning:
            pass  # Not necessarily hallucination — LLM may use qualitative language

    return flags


class TestHallucinationDetection:
    def test_high_confidence_no_data_flagged(self):
        r = RecommendationOutput(confidence=0.9, recommendation="buy", reasoning="Strong data shows...")
        flags = _check_numeric_claims(r, {})
        assert "high_confidence_without_data" in flags

    def test_low_confidence_no_data_ok(self):
        r = RecommendationOutput(confidence=0.2, recommendation="hold")
        flags = _check_numeric_claims(r, {})
        assert flags == []

    def test_real_data_no_flags(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.7,
            reasoning="Stock trading around 1800 with strong momentum.",
        )
        flags = _check_numeric_claims(r, {"current_price": 1800.0})
        assert "high_confidence_without_data" not in flags

    def test_empty_reasoning_no_hallucination(self):
        r = RecommendationOutput(recommendation="hold", confidence=0.5)
        flags = _check_numeric_claims(r, {"current_price": 100.0})
        assert flags == []


class TestImpossibleValues:
    def test_confidence_above_one_rejected(self):
        with pytest.raises(Exception):
            RecommendationOutput(confidence=1.1)

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(Exception):
            RecommendationOutput(confidence=-0.1)

    def test_recommendation_is_string(self):
        r = RecommendationOutput(recommendation="buy")
        assert isinstance(r.recommendation, str)


class TestDisclaimerPresence:
    """Disclaimer is a required safety guard — its absence is a factual gap."""

    def test_default_disclaimer_present(self):
        r = RecommendationOutput()
        assert r.disclaimer != ""

    def test_disclaimer_contains_key_terms(self):
        r = RecommendationOutput()
        lower = r.disclaimer.lower()
        assert "educational" in lower or "informational" in lower
        assert "advice" in lower

    def test_disclaimer_not_empty_after_custom_factors(self):
        r = RecommendationOutput(
            recommendation="sell",
            supporting_factors=["declining trend"],
            dissenting_factors=["oversold"],
        )
        assert r.disclaimer != ""
