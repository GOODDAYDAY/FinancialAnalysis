"""
Tests for data quality validation of agent inputs and outputs.

Covers: mock data quality checks, boundary values, None handling,
and edge cases in market data, sentiment, and recommendation payloads.
"""

import pytest

from backend.state import (
    MarketDataResult,
    SentimentOutput,
    FundamentalOutput,
    RiskOutput,
    RecommendationOutput,
)


class TestMarketDataQuality:
    def test_zero_price_valid(self):
        """Price of 0 is technically valid (delisted stock, etc.)."""
        m = MarketDataResult(ticker="X", current_price=0.0)
        assert m.current_price == 0.0

    def test_negative_price_allowed(self):
        """Pydantic doesn't forbid negative prices — data quality check."""
        m = MarketDataResult(ticker="X", current_price=-1.0)
        assert m.current_price == -1.0

    def test_large_market_cap(self):
        m = MarketDataResult(ticker="AAPL", market_cap=3e12)
        assert m.market_cap == 3e12

    def test_all_none_fields(self):
        m = MarketDataResult(ticker="X")
        assert m.pe_ratio is None
        assert m.rsi_14 is None
        assert m.macd is None

    def test_ticker_required(self):
        """ticker is a required field — no default."""
        with pytest.raises(Exception):
            MarketDataResult()

    def test_price_change_pct_none_allowed(self):
        m = MarketDataResult(ticker="X", price_change_pct=None)
        assert m.price_change_pct is None

    def test_technical_signals_default_empty(self):
        m = MarketDataResult(ticker="X")
        assert m.technical_signals == []


class TestSentimentDataQuality:
    def test_extreme_bullish(self):
        s = SentimentOutput(overall_score=1.0, confidence=1.0, overall_label="very_bullish")
        assert s.overall_score == 1.0

    def test_extreme_bearish(self):
        s = SentimentOutput(overall_score=-1.0, confidence=1.0, overall_label="very_bearish")
        assert s.overall_score == -1.0

    def test_neutral_default(self):
        s = SentimentOutput()
        assert s.overall_score == 0.0
        assert s.overall_label == "neutral"

    def test_empty_reasoning(self):
        s = SentimentOutput(overall_score=0.5)
        assert s.reasoning == ""

    def test_article_scores_empty(self):
        s = SentimentOutput()
        assert s.article_scores == []


class TestFundamentalDataQuality:
    def test_minimal_score(self):
        f = FundamentalOutput(health_score=1.0)
        assert f.health_score == 1.0

    def test_max_score(self):
        f = FundamentalOutput(health_score=10.0)
        assert f.health_score == 10.0

    def test_boundary_at_1(self):
        f = FundamentalOutput(health_score=1.0)
        assert f.health_score >= 1.0

    def test_boundary_at_10(self):
        f = FundamentalOutput(health_score=10.0)
        assert f.health_score <= 10.0

    def test_default_red_flags_empty(self):
        f = FundamentalOutput()
        assert f.red_flags == []

    def test_multiple_red_flags(self):
        f = FundamentalOutput(
            health_score=3.0,
            red_flags=["declining_revenue", "high_debt", "negative_cash_flow"],
        )
        assert len(f.red_flags) == 3


class TestRiskDataQuality:
    def test_min_risk(self):
        r = RiskOutput(risk_score=1.0, risk_level="low")
        assert r.risk_score == 1.0

    def test_max_risk(self):
        r = RiskOutput(risk_score=10.0, risk_level="critical")
        assert r.risk_score == 10.0

    def test_default_mitigation_empty(self):
        r = RiskOutput()
        assert r.mitigation_notes == []

    def test_risk_factors_list(self):
        r = RiskOutput(risk_factors=["volatility", "concentration"])
        assert len(r.risk_factors) == 2


class TestRecommendationDataQuality:
    def test_valid_recommendations(self):
        for rec in ["buy", "hold", "sell"]:
            r = RecommendationOutput(recommendation=rec)
            assert r.recommendation == rec

    def test_confidence_zero(self):
        r = RecommendationOutput(confidence=0.0)
        assert r.confidence == 0.0

    def test_confidence_one(self):
        r = RecommendationOutput(confidence=1.0)
        assert r.confidence == 1.0

    def test_disclaimer_always_present(self):
        r = RecommendationOutput()
        assert r.disclaimer is not None
        assert len(r.disclaimer) > 50

    def test_empty_factors(self):
        r = RecommendationOutput()
        assert r.supporting_factors == []
        assert r.dissenting_factors == []

    def test_full_output(self):
        r = RecommendationOutput(
            recommendation="buy", confidence=0.85, investment_horizon="long-term",
            supporting_factors=["strong momentum", "good fundamentals"],
            dissenting_factors=["high valuation"],
            reasoning="All signals align.",
        )
        assert len(r.supporting_factors) == 2
        assert len(r.dissenting_factors) == 1
