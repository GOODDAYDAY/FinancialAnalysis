"""Real API tests for Fundamental Agent (DeepSeek LLM)."""

from backend.agents.fundamental.node import fundamental_node
from backend.agents.market_data.node import market_data_node


class TestFundamentalAnalysis:
    """Real LLM fundamental analysis on real market data."""

    def test_health_score_in_range(self):
        """Expected: health score between 1 and 10."""
        md = market_data_node({"ticker": "600519.SS"})
        result = fundamental_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        score = result["fundamental"]["health_score"]
        assert 1.0 <= score <= 10.0

    def test_summary_not_empty(self):
        """Expected: LLM provides substantive summary."""
        md = market_data_node({"ticker": "AAPL"})
        result = fundamental_node({"ticker": "AAPL", "market_data": md["market_data"]})
        assert len(result["fundamental"]["summary"]) > 20

    def test_no_data_returns_default(self):
        """Expected: default health score when no market data."""
        result = fundamental_node({"ticker": "TEST", "market_data": {}})
        assert result["fundamental"]["health_score"] == 5.0
