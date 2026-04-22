"""
ML Contract: Pydantic boundary models maintain valid field constraints.

Agents use Pydantic to validate LLM structured output at boundaries.
These tests confirm model schemas haven't drifted (field renamed, constraint
loosened, required field added without default, etc.).
All checks run offline — no LLM, no network.
"""

import pytest
from pydantic import ValidationError
from backend.state import (
    MarketDataResult,
    SentimentOutput,
    FundamentalOutput,
    RiskOutput,
    RecommendationOutput,
    DebateArgument,
)


class TestMarketDataResult:
    def test_minimal_construction(self):
        """Only ticker is required; all numeric fields are optional."""
        m = MarketDataResult(ticker="600519.SS")
        assert m.ticker == "600519.SS"
        assert m.current_price is None

    def test_is_mock_defaults_false(self):
        m = MarketDataResult(ticker="TEST")
        assert m.is_mock is False

    def test_technical_signals_defaults_empty(self):
        m = MarketDataResult(ticker="TEST")
        assert m.technical_signals == []


class TestSentimentOutput:
    def test_score_bounds_respected(self):
        """overall_score must be in [-1, +1]."""
        with pytest.raises(ValidationError):
            SentimentOutput(overall_score=1.5)
        with pytest.raises(ValidationError):
            SentimentOutput(overall_score=-1.5)

    def test_confidence_bounds_respected(self):
        with pytest.raises(ValidationError):
            SentimentOutput(confidence=-0.1)
        with pytest.raises(ValidationError):
            SentimentOutput(confidence=1.1)

    def test_defaults_are_neutral(self):
        s = SentimentOutput()
        assert s.overall_score == 0.0
        assert s.overall_label == "neutral"


class TestFundamentalOutput:
    def test_health_score_lower_bound(self):
        """health_score < 1.0 must be rejected."""
        with pytest.raises(ValidationError):
            FundamentalOutput(health_score=0.5)

    def test_health_score_upper_bound(self):
        """health_score > 10.0 must be rejected."""
        with pytest.raises(ValidationError):
            FundamentalOutput(health_score=10.5)

    def test_valid_health_score(self):
        f = FundamentalOutput(health_score=7.5)
        assert f.health_score == 7.5

    def test_red_flags_defaults_empty(self):
        f = FundamentalOutput()
        assert f.red_flags == []


class TestRiskOutput:
    def test_risk_score_bounds(self):
        with pytest.raises(ValidationError):
            RiskOutput(risk_score=0.5)
        with pytest.raises(ValidationError):
            RiskOutput(risk_score=10.5)

    def test_valid_risk_score(self):
        r = RiskOutput(risk_score=6.0)
        assert r.risk_score == 6.0

    def test_risk_level_default(self):
        assert RiskOutput().risk_level == "medium"


class TestRecommendationOutput:
    def test_disclaimer_is_hardcoded(self):
        """Disclaimer must be non-empty and fixed — LLM cannot override it."""
        r = RecommendationOutput()
        assert len(r.disclaimer) > 50
        assert "financial advice" in r.disclaimer.lower() or "informational" in r.disclaimer.lower()

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            RecommendationOutput(confidence=-0.1)
        with pytest.raises(ValidationError):
            RecommendationOutput(confidence=1.1)

    def test_default_recommendation_is_hold(self):
        assert RecommendationOutput().recommendation == "hold"

    def test_supporting_factors_defaults_empty(self):
        assert RecommendationOutput().supporting_factors == []


class TestDebateArgument:
    def test_required_fields(self):
        """role and round_number are required; optional lists default to empty."""
        d = DebateArgument(role="bull", round_number=1, argument="Strong earnings growth.")
        assert d.role == "bull"
        assert d.key_points == []
        assert d.evidence == []

    def test_missing_role_raises(self):
        with pytest.raises(ValidationError):
            DebateArgument(round_number=1, argument="test")
