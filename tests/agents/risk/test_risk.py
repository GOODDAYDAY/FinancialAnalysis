"""Real API tests for Risk Agent (DeepSeek LLM)."""

from backend.agents.risk.node import risk_node
from backend.agents.market_data.node import market_data_node


class TestRiskAssessment:
    """Real LLM risk assessment on real data."""

    def test_risk_score_in_range(self):
        """Expected: risk score between 1 and 10."""
        md = market_data_node({"ticker": "600519.SS"})
        result = risk_node({
            "ticker": "600519.SS",
            "market_data": md["market_data"],
            "sentiment": {"overall_score": 0.3, "overall_label": "bullish", "key_factors": []},
            "fundamental": {"health_score": 8, "red_flags": []},
        })
        assert 1.0 <= result["risk"]["risk_score"] <= 10.0

    def test_risk_factors_present(self):
        """Expected: at least 1 risk factor listed."""
        md = market_data_node({"ticker": "AAPL"})
        result = risk_node({
            "ticker": "AAPL",
            "market_data": md["market_data"],
            "sentiment": {"overall_score": -0.3, "overall_label": "bearish", "key_factors": ["Bad news"]},
            "fundamental": {"health_score": 5, "red_flags": ["High debt"]},
        })
        assert len(result["risk"]["risk_factors"]) >= 1

    def test_risk_level_label_present(self):
        """Expected: risk_level is one of low/medium/high/critical."""
        md = market_data_node({"ticker": "600519.SS"})
        result = risk_node({
            "ticker": "600519.SS",
            "market_data": md["market_data"],
            "sentiment": {}, "fundamental": {},
        })
        assert result["risk"]["risk_level"] in ("low", "medium", "high", "critical")
