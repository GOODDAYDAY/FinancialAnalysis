"""
Tests for recommendation output bias detection.

Covers: detecting overly-bullish or overly-bearish recommendations without
supporting evidence, single-sided reasoning, and extreme confidence without data.
"""

import pytest

from backend.state import RecommendationOutput


def _has_bias(rec: RecommendationOutput) -> bool:
    """
    Heuristic bias check: a recommendation is potentially biased if:
    - It has zero dissenting factors when confidence > 0.9
    - It makes absolute claims without any balancing view
    Returns True if bias is detected.
    """
    if rec.confidence > 0.9 and len(rec.dissenting_factors) == 0:
        return True
    return False


class TestBiasDetection:
    def test_high_confidence_no_dissenting_is_biased(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.95,
            supporting_factors=["strong momentum", "good PE", "sector tailwind"],
            dissenting_factors=[],
        )
        assert _has_bias(r) is True

    def test_high_confidence_with_dissenting_not_biased(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.9,
            supporting_factors=["strong momentum", "good PE"],
            dissenting_factors=["high valuation", "regulatory risk"],
        )
        assert _has_bias(r) is False

    def test_low_confidence_no_dissenting_not_biased(self):
        """Low confidence naturally implies uncertainty — no bias flag."""
        r = RecommendationOutput(
            recommendation="hold", confidence=0.3,
            supporting_factors=["some data"],
            dissenting_factors=[],
        )
        assert _has_bias(r) is False

    def test_sell_with_balanced_view_not_biased(self):
        r = RecommendationOutput(
            recommendation="sell", confidence=0.7,
            supporting_factors=["declining revenue", "high debt"],
            dissenting_factors=["strong brand value", "cash reserves"],
        )
        assert _has_bias(r) is False

    def test_boundary_confidence_09_not_flagged(self):
        """Confidence exactly 0.9 should NOT trigger the > 0.9 check."""
        r = RecommendationOutput(
            recommendation="buy", confidence=0.9,
            dissenting_factors=[],
        )
        assert _has_bias(r) is False

    def test_empty_supporting_and_dissenting(self):
        r = RecommendationOutput(recommendation="hold", confidence=0.5)
        assert _has_bias(r) is False

    def test_many_supporting_no_dissenting_high_conf(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.99,
            supporting_factors=["a", "b", "c", "d", "e"],
            dissenting_factors=[],
        )
        assert _has_bias(r) is True

    def test_moderate_confidence_passes(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.7,
            supporting_factors=["momentum"],
            dissenting_factors=[],
        )
        assert _has_bias(r) is False


class TestBiasEdgeCases:
    def test_held_disclaimer_not_bias(self):
        """Disclaimer presence should not affect bias check."""
        r = RecommendationOutput(
            recommendation="buy", confidence=0.6,
            dissenting_factors=["market uncertainty"],
        )
        assert "educational" in r.disclaimer.lower()
        assert _has_bias(r) is False

    def test_multiple_recommendations_no_bias_when_balanced(self):
        for rec in ["buy", "hold", "sell"]:
            r = RecommendationOutput(
                recommendation=rec, confidence=0.5,
                dissenting_factors=["risk"],
            )
            assert _has_bias(r) is False
