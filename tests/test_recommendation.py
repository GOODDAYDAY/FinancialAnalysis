"""
AI Test Suite: Recommendation Logic (F-17, F-18)

Tests that the advisory agent produces valid recommendations
with proper reasoning chains and compliance disclaimers.
"""
import pytest
from backend.agents.advisory import advisory_node


def _make_state(
    ticker="AAPL",
    sentiment_score=0.5,
    sentiment_label="bullish",
    health_score=8.0,
    risk_score=3.0,
    risk_level="low",
    debate_entries=None,
):
    """Helper to build a complete state for advisory testing."""
    return {
        "ticker": ticker,
        "market_data": {
            "current_price": 190.0, "pe_ratio": 28.0, "rsi_14": 55.0,
            "technical_signals": ["MACD above signal (bullish)"],
        },
        "sentiment": {
            "overall_score": sentiment_score, "overall_label": sentiment_label,
            "reasoning": f"Sentiment is {sentiment_label}", "key_factors": [],
        },
        "fundamental": {
            "health_score": health_score, "summary": "Solid fundamentals",
            "red_flags": [],
        },
        "risk": {
            "risk_score": risk_score, "risk_level": risk_level,
            "risk_factors": ["Market volatility"], "summary": "Moderate risk",
        },
        "debate_history": debate_entries or [
            {"role": "bull", "round_number": 1, "argument": "Strong buy case",
             "key_points": ["Growth"], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Sell case",
             "key_points": ["Overvalued"], "evidence": [], "rebuttals": []},
        ],
        "reasoning_chain": [],
    }


class TestRecommendationValues:
    """Recommendation must be one of buy/hold/sell with valid confidence."""

    def test_valid_recommendation(self, mock_llm):
        """Expected: recommendation in {buy, hold, sell}."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.75,
            "investment_horizon": "medium-term",
            "supporting_factors": ["Strong fundamentals"],
            "dissenting_factors": ["Some risk"],
            "debate_summary": "Bull won", "reasoning": "Good stock",
            "disclaimer": "Not financial advice.",
        })
        result = advisory_node(_make_state())
        rec = result["recommendation"]
        assert rec["recommendation"] in ("buy", "hold", "sell")

    def test_confidence_in_range(self, mock_llm):
        """Expected: confidence between 0 and 1."""
        mock_llm.set_response({
            "recommendation": "hold", "confidence": 0.6,
            "investment_horizon": "short-term",
            "supporting_factors": [], "dissenting_factors": [],
            "debate_summary": "", "reasoning": "Mixed signals",
            "disclaimer": "Not financial advice.",
        })
        result = advisory_node(_make_state())
        conf = result["recommendation"]["confidence"]
        assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of range"


class TestRecommendationConsistency:
    """Recommendation should be directionally consistent with inputs."""

    def test_bullish_inputs_suggest_buy(self, mock_llm):
        """Input: high sentiment, healthy fundamentals, low risk → Expected: buy tendency."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.8,
            "investment_horizon": "medium-term",
            "supporting_factors": ["Strong sentiment", "Healthy fundamentals", "Low risk"],
            "dissenting_factors": ["Minor concern"],
            "debate_summary": "Bull dominated",
            "reasoning": "All signals point to buy",
            "disclaimer": "Not financial advice.",
        })
        state = _make_state(sentiment_score=0.8, sentiment_label="bullish",
                            health_score=9.0, risk_score=2.0, risk_level="low")
        result = advisory_node(state)
        assert result["recommendation"]["recommendation"] == "buy"

    def test_bearish_inputs_suggest_sell(self, mock_llm):
        """Input: negative sentiment, poor fundamentals, high risk → Expected: sell tendency."""
        mock_llm.set_response({
            "recommendation": "sell", "confidence": 0.7,
            "investment_horizon": "short-term",
            "supporting_factors": [],
            "dissenting_factors": ["Negative sentiment", "Poor health", "High risk"],
            "debate_summary": "Bear dominated",
            "reasoning": "Multiple red flags",
            "disclaimer": "Not financial advice.",
        })
        state = _make_state(sentiment_score=-0.7, sentiment_label="bearish",
                            health_score=3.0, risk_score=8.0, risk_level="high")
        result = advisory_node(state)
        assert result["recommendation"]["recommendation"] == "sell"

    def test_mixed_inputs_suggest_hold(self, mock_llm):
        """Input: mixed signals → Expected: hold with lower confidence."""
        mock_llm.set_response({
            "recommendation": "hold", "confidence": 0.45,
            "investment_horizon": "medium-term",
            "supporting_factors": ["OK fundamentals"],
            "dissenting_factors": ["Bad sentiment"],
            "debate_summary": "Split decision",
            "reasoning": "Conflicting signals warrant caution",
            "disclaimer": "Not financial advice.",
        })
        state = _make_state(sentiment_score=-0.3, sentiment_label="bearish",
                            health_score=7.0, risk_score=5.0, risk_level="medium")
        result = advisory_node(state)
        rec = result["recommendation"]
        assert rec["recommendation"] == "hold"
        assert rec["confidence"] < 0.6, "Mixed signals should lower confidence"


class TestRecommendationCompleteness:
    """Recommendation must include all required fields."""

    def test_has_supporting_factors(self, mock_llm):
        """Expected: at least 1 supporting factor."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.7,
            "investment_horizon": "medium-term",
            "supporting_factors": ["Strong growth", "Low risk", "Positive sentiment"],
            "dissenting_factors": ["High valuation"],
            "debate_summary": "Bull won", "reasoning": "Good overall",
            "disclaimer": "Not financial advice.",
        })
        result = advisory_node(_make_state())
        assert len(result["recommendation"]["supporting_factors"]) >= 1

    def test_has_dissenting_factors(self, mock_llm):
        """Expected: at least 1 dissenting factor (balanced analysis)."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.7,
            "investment_horizon": "medium-term",
            "supporting_factors": ["Growth"],
            "dissenting_factors": ["Valuation risk", "Market uncertainty"],
            "debate_summary": "Bull won but Bear valid",
            "reasoning": "Buy with awareness of risks",
            "disclaimer": "Not financial advice.",
        })
        result = advisory_node(_make_state())
        assert len(result["recommendation"]["dissenting_factors"]) >= 1

    def test_has_debate_summary(self, mock_llm):
        """Expected: debate_summary references Bull/Bear outcome."""
        mock_llm.set_response({
            "recommendation": "hold", "confidence": 0.5,
            "investment_horizon": "medium-term",
            "supporting_factors": ["A"], "dissenting_factors": ["B"],
            "debate_summary": "Bull argued growth potential while Bear highlighted valuation risk. Bear conceded on fundamentals.",
            "reasoning": "Balanced view",
            "disclaimer": "Not financial advice.",
        })
        result = advisory_node(_make_state())
        summary = result["recommendation"]["debate_summary"]
        assert len(summary) > 10, "Debate summary should be substantive"


class TestComplianceDisclaimer:
    """F-15: Every recommendation MUST include a disclaimer."""

    def test_disclaimer_present(self, mock_llm):
        """Expected: disclaimer field is non-empty."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.7,
            "investment_horizon": "medium-term",
            "supporting_factors": [], "dissenting_factors": [],
            "debate_summary": "", "reasoning": "",
            "disclaimer": "This is for educational purposes only. Not financial advice.",
        })
        result = advisory_node(_make_state())
        disclaimer = result["recommendation"]["disclaimer"]
        assert len(disclaimer) > 20, "Disclaimer must be substantive"
        assert "not" in disclaimer.lower() and "advice" in disclaimer.lower()

    def test_disclaimer_default_if_llm_omits(self, mock_llm):
        """Expected: even if LLM omits disclaimer, default is injected."""
        mock_llm.set_response({
            "recommendation": "hold", "confidence": 0.5,
            "investment_horizon": "medium-term",
            "supporting_factors": [], "dissenting_factors": [],
            "debate_summary": "", "reasoning": "",
            # Note: no disclaimer field — Pydantic default should kick in
        })
        result = advisory_node(_make_state())
        disclaimer = result["recommendation"].get("disclaimer", "")
        assert len(disclaimer) > 0, "Default disclaimer should be injected"


class TestReasoningChain:
    """F-18: Advisory must contribute to the reasoning chain."""

    def test_advisory_in_reasoning_chain(self, mock_llm):
        """Expected: reasoning_chain includes advisory step."""
        mock_llm.set_response({
            "recommendation": "buy", "confidence": 0.7,
            "investment_horizon": "medium-term",
            "supporting_factors": ["A"], "dissenting_factors": ["B"],
            "debate_summary": "S", "reasoning": "R",
            "disclaimer": "D",
        })
        result = advisory_node(_make_state())
        chain = result.get("reasoning_chain", [])
        assert any(s.get("agent") == "advisory" for s in chain)

    def test_reasoning_chain_has_recommendation(self, mock_llm):
        """Expected: reasoning chain step includes the recommendation value."""
        mock_llm.set_response({
            "recommendation": "sell", "confidence": 0.65,
            "investment_horizon": "short-term",
            "supporting_factors": [], "dissenting_factors": [],
            "debate_summary": "", "reasoning": "",
            "disclaimer": "D",
        })
        result = advisory_node(_make_state())
        chain = result.get("reasoning_chain", [])
        advisory_step = [s for s in chain if s.get("agent") == "advisory"][0]
        assert advisory_step["recommendation"] == "sell"
