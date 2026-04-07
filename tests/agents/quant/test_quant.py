"""Real data tests for Quant Agent (pure algorithms, no LLM)."""

from backend.agents.quant.node import quant_node
from backend.agents.market_data.node import market_data_node


class TestQuantSignals:
    """Quant signals on real market data."""

    def test_score_in_range(self):
        """Expected: quant score between -100 and 100."""
        md = market_data_node({"ticker": "600519.SS"})
        result = quant_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        score = result["quant"]["score"]
        assert -100 <= score <= 100

    def test_signals_present(self):
        """Expected: at least 3 signals for major stock with full data."""
        md = market_data_node({"ticker": "600519.SS"})
        result = quant_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        assert len(result["quant"]["signals"]) >= 3

    def test_each_signal_has_structure(self):
        """Expected: every signal has name, type, detail, weight."""
        md = market_data_node({"ticker": "AAPL"})
        result = quant_node({"ticker": "AAPL", "market_data": md["market_data"]})
        for sig in result["quant"]["signals"]:
            assert "name" in sig
            assert sig["type"] in ("bullish", "bearish", "neutral")
            assert "detail" in sig
            assert "weight" in sig

    def test_verdict_matches_score(self):
        """Expected: verdict label consistent with score direction."""
        md = market_data_node({"ticker": "600519.SS"})
        result = quant_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        q = result["quant"]
        if q["score"] >= 30:
            assert "BUY" in q["verdict"]
        elif q["score"] <= -30:
            assert "SELL" in q["verdict"]

    def test_no_data_returns_zero(self):
        """Expected: score 0 when no market data."""
        result = quant_node({"ticker": "TEST", "market_data": {}})
        assert result["quant"]["score"] == 0
