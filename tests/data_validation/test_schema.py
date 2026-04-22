"""
Tests for ResearchState and Pydantic boundary model schema validation.

Covers: ResearchState TypedDict serialization, Pydantic model field constraints,
default values, and field type enforcement.
"""

import pytest
from pydantic import ValidationError

from backend.state import (
    ResearchState,
    MarketDataResult,
    NewsArticle,
    SentimentOutput,
    FundamentalOutput,
    RiskOutput,
    DebateArgument,
    RecommendationOutput,
    merge_lists,
)


class TestMergeLists:
    def test_merges_two_lists(self):
        assert merge_lists([1, 2], [3, 4]) == [1, 2, 3, 4]

    def test_empty_left(self):
        assert merge_lists([], [1, 2]) == [1, 2]

    def test_empty_right(self):
        assert merge_lists([1, 2], []) == [1, 2]

    def test_both_empty(self):
        assert merge_lists([], []) == []


class TestMarketDataResult:
    def test_minimal_valid(self):
        m = MarketDataResult(ticker="600519.SS")
        assert m.ticker == "600519.SS"
        assert m.current_price is None
        assert m.is_mock is False
        assert m.data_source == "live"

    def test_full_construction(self):
        m = MarketDataResult(
            ticker="AAPL", current_price=150.0, price_change=2.5,
            price_change_pct=1.69, volume=1000000, market_cap=2e12,
            pe_ratio=25.0, fifty_two_week_high=180.0, fifty_two_week_low=120.0,
            sma_20=148.0, rsi_14=55.0, technical_signals=["above_sma_20"],
        )
        assert m.current_price == 150.0
        assert m.technical_signals == ["above_sma_20"]

    def test_default_source(self):
        m = MarketDataResult(ticker="X")
        assert m.data_source == "live"


class TestSentimentOutput:
    def test_defaults(self):
        s = SentimentOutput()
        assert s.overall_score == 0.0
        assert s.confidence == 0.5
        assert s.overall_label == "neutral"

    def test_valid_range(self):
        s = SentimentOutput(overall_score=0.8, confidence=0.9)
        assert s.overall_score == 0.8

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            SentimentOutput(overall_score=2.0)

    def test_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            SentimentOutput(confidence=1.5)


class TestFundamentalOutput:
    def test_defaults(self):
        f = FundamentalOutput()
        assert f.health_score == 5.0
        assert f.red_flags == []

    def test_valid_health_score(self):
        f = FundamentalOutput(health_score=8.5, summary="strong")
        assert f.health_score == 8.5

    def test_health_score_too_low(self):
        with pytest.raises(ValidationError):
            FundamentalOutput(health_score=0.5)

    def test_health_score_too_high(self):
        with pytest.raises(ValidationError):
            FundamentalOutput(health_score=11.0)


class TestRiskOutput:
    def test_defaults(self):
        r = RiskOutput()
        assert r.risk_score == 5.0
        assert r.risk_level == "medium"

    def test_risk_score_bounds(self):
        r = RiskOutput(risk_score=1.0)
        assert r.risk_score == 1.0
        r = RiskOutput(risk_score=10.0)
        assert r.risk_score == 10.0

    def test_risk_score_out_of_range(self):
        with pytest.raises(ValidationError):
            RiskOutput(risk_score=15.0)


class TestRecommendationOutput:
    def test_defaults(self):
        r = RecommendationOutput()
        assert r.recommendation == "hold"
        assert r.confidence == 0.5
        assert r.investment_horizon == "medium-term"
        assert "educational" in r.disclaimer.lower()

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            RecommendationOutput(confidence=1.5)

    def test_disclaimer_present(self):
        r = RecommendationOutput(recommendation="buy")
        assert r.disclaimer != ""
        assert "financial advice" in r.disclaimer.lower()


class TestNewsArticle:
    def test_minimal(self):
        a = NewsArticle(title="Test")
        assert a.source == "unknown"
        assert a.relevance_score == 0.5

    def test_full(self):
        a = NewsArticle(
            title="Headline", source="Reuters", url="https://example.com",
            published="2026-01-01", summary="Summary text", relevance_score=0.9,
        )
        assert a.source == "Reuters"


class TestDebateArgument:
    def test_required_fields(self):
        d = DebateArgument(role="bull", round_number=1, argument="Economy is strong")
        assert d.role == "bull"
        assert d.round_number == 1
        assert d.key_points == []
        assert d.evidence == []

    def test_with_details(self):
        d = DebateArgument(
            role="bear", round_number=2, argument="Debt is rising",
            key_points=["debt", "inflation"],
            evidence=["fed_data"],
            rebuttals=["counter-argument"],
        )
        assert len(d.key_points) == 2


class TestResearchState:
    def test_empty_state(self):
        state: ResearchState = {}
        assert "ticker" not in state

    def test_populated_state(self):
        state: ResearchState = {
            "ticker": "600519.SS",
            "user_query": "Analyze 600519",
            "intent": "stock_query",
            "language": "zh",
            "market_data": {"current_price": 1800.0},
            "sentiment": {"overall_score": 0.5},
        }
        assert state["ticker"] == "600519.SS"
        assert state["market_data"]["current_price"] == 1800.0
