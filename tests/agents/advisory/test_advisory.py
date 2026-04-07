"""Real API tests for Advisory Agent (DeepSeek LLM)."""

from backend.agents.advisory.node import advisory_node


def _make_advisory_state():
    """Build a complete state for advisory testing."""
    return {
        "ticker": "600519.SS",
        "market_data": {"current_price": 1460, "pe_ratio": 20.4, "rsi_14": 50, "technical_signals": ["RSI neutral"]},
        "sentiment": {"overall_score": 0.3, "overall_label": "bullish", "reasoning": "Positive earnings", "key_factors": ["Strong Q4"]},
        "fundamental": {"health_score": 8.5, "summary": "Strong brand", "red_flags": []},
        "quant": {"score": 15, "verdict": "MODERATE BUY", "signals": [{"name": "MACD Bullish", "type": "bullish", "detail": "Above signal"}]},
        "risk": {"risk_score": 4.5, "risk_level": "medium", "risk_factors": ["Valuation premium"], "summary": "Moderate"},
        "debate_history": [
            {"role": "bull", "round_number": 1, "argument": "Strong moat", "key_points": ["ROE 54%"], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Overvalued", "key_points": ["PE premium"], "evidence": [], "rebuttals": []},
        ],
        "reasoning_chain": [],
    }


class TestRecommendation:
    """Real LLM recommendation synthesis."""

    def test_valid_recommendation(self):
        """Expected: buy/hold/sell."""
        result = advisory_node(_make_advisory_state())
        assert result["recommendation"]["recommendation"] in ("buy", "hold", "sell")

    def test_confidence_in_range(self):
        """Expected: confidence 0-1."""
        result = advisory_node(_make_advisory_state())
        assert 0.0 <= result["recommendation"]["confidence"] <= 1.0

    def test_disclaimer_present(self):
        """Expected: disclaimer always included."""
        result = advisory_node(_make_advisory_state())
        assert len(result["recommendation"]["disclaimer"]) > 10

    def test_supporting_factors_present(self):
        """Expected: at least 1 supporting factor."""
        result = advisory_node(_make_advisory_state())
        assert len(result["recommendation"]["supporting_factors"]) >= 1
