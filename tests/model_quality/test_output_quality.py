"""
Tests for recommendation output format, required fields, and disclaimer.

Covers: output completeness, factor list quality, horizon validity,
and overall structural integrity of RecommendationOutput.
"""

import pytest

from backend.state import RecommendationOutput


class TestRequiredFields:
    def test_all_defaults_present(self):
        r = RecommendationOutput()
        assert r.recommendation is not None
        assert r.confidence is not None
        assert r.investment_horizon is not None
        assert r.disclaimer is not None

    def test_recommendation_is_valid_value(self):
        """Only buy/hold/sell are valid recommendations."""
        valid = {"buy", "hold", "sell"}
        r = RecommendationOutput(recommendation="buy")
        assert r.recommendation in valid

    def test_confidence_is_float(self):
        r = RecommendationOutput()
        assert isinstance(r.confidence, float)

    def test_factors_are_lists(self):
        r = RecommendationOutput()
        assert isinstance(r.supporting_factors, list)
        assert isinstance(r.dissenting_factors, list)

    def test_disclaimer_is_string(self):
        r = RecommendationOutput()
        assert isinstance(r.disclaimer, str)


class TestInvestmentHorizon:
    def test_valid_horizons(self):
        for h in ["short-term", "medium-term", "long-term"]:
            r = RecommendationOutput(investment_horizon=h)
            assert r.investment_horizon == h

    def test_custom_horizon_allowed(self):
        """Pydantic doesn't enforce enum — custom values pass through."""
        r = RecommendationOutput(investment_horizon="intraday")
        assert r.investment_horizon == "intraday"


class TestFactorQuality:
    def test_factors_are_non_empty_strings(self):
        r = RecommendationOutput(
            recommendation="buy",
            supporting_factors=["strong momentum", "low PE"],
            dissenting_factors=["high debt"],
        )
        assert all(isinstance(f, str) and len(f) > 0 for f in r.supporting_factors)
        assert all(isinstance(f, str) and len(f) > 0 for f in r.dissenting_factors)

    def test_empty_factor_list_allowed(self):
        r = RecommendationOutput()
        assert r.supporting_factors == []

    def test_duplicate_factors(self):
        """Duplicates are technically allowed — quality concern, not validation error."""
        r = RecommendationOutput(
            supporting_factors=["momentum", "momentum"],
        )
        assert len(r.supporting_factors) == 2


class TestStructuralIntegrity:
    def test_model_dump_roundtrip(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.8,
            investment_horizon="long-term",
            supporting_factors=["a", "b"],
            dissenting_factors=["c"],
            reasoning="Test reasoning",
            disclaimer="Test disclaimer",
        )
        dumped = r.model_dump()
        assert dumped["recommendation"] == "buy"
        assert dumped["confidence"] == 0.8
        assert dumped["supporting_factors"] == ["a", "b"]
        assert dumped["dissenting_factors"] == ["c"]

    def test_model_dump_contains_all_keys(self):
        r = RecommendationOutput()
        keys = set(r.model_dump().keys())
        expected = {"recommendation", "confidence", "investment_horizon",
                     "supporting_factors", "dissenting_factors", "debate_summary",
                     "reasoning", "disclaimer"}
        assert keys == expected

    def test_debate_summary_default(self):
        r = RecommendationOutput()
        assert r.debate_summary == ""

    def test_reasoning_default(self):
        r = RecommendationOutput()
        assert r.reasoning == ""


class TestDisclaimerCompliance:
    """Disclaimer must contain specific legal language for compliance."""

    def test_disclaimer_mentions_not_advice(self):
        r = RecommendationOutput()
        assert "not" in r.disclaimer.lower() or "does not constitute" in r.disclaimer.lower()

    def test_disclaimer_mentions_past_performance(self):
        r = RecommendationOutput()
        assert "past performance" in r.disclaimer.lower()

    def test_disclaimer_mentions_advisor(self):
        r = RecommendationOutput()
        assert "advisor" in r.disclaimer.lower() or "advis" in r.disclaimer.lower()

    def test_disclaimer_length(self):
        r = RecommendationOutput()
        assert len(r.disclaimer) > 80
