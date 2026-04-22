"""Real data tests for Momentum Agent (pure algorithmic, no LLM)."""

from backend.agents.momentum.node import momentum_node
from backend.agents.market_data.node import market_data_node


def _base_state(ticker="600519.SS"):
    md = market_data_node({"ticker": ticker})
    return {
        "ticker": ticker,
        "market_data": md["market_data"],
        "macro_env": {},
    }


class TestMomentumScore:
    """Momentum score computation on real price history."""

    def test_score_in_range(self):
        """Expected: score between -100 and 100."""
        result = momentum_node(_base_state("600519.SS"))
        assert -100 <= result["momentum"]["score"] <= 100

    def test_regime_is_valid(self):
        """Expected: regime is one of the five defined labels."""
        valid = {
            "STRONG BULLISH MOMENTUM", "BULLISH MOMENTUM",
            "NEUTRAL / CONSOLIDATING",
            "BEARISH MOMENTUM", "STRONG BEARISH MOMENTUM",
        }
        result = momentum_node(_base_state("600519.SS"))
        assert result["momentum"]["regime"] in valid

    def test_signals_are_list(self):
        """Expected: signals is a list (may be empty for flat stocks)."""
        result = momentum_node(_base_state("AAPL"))
        assert isinstance(result["momentum"]["signals"], list)

    def test_each_signal_has_structure(self):
        """Expected: every signal has name, type, detail, weight."""
        result = momentum_node(_base_state("600519.SS"))
        for sig in result["momentum"]["signals"]:
            assert "name" in sig
            assert sig["type"] in ("bullish", "bearish", "neutral")
            assert "detail" in sig
            assert "weight" in sig

    def test_returns_keys_present(self):
        """Expected: returns dict has 3d/5d/10d/20d/60d keys."""
        result = momentum_node(_base_state("600519.SS"))
        returns = result["momentum"]["returns"]
        for k in ("3d", "5d", "10d", "20d", "60d"):
            assert k in returns

    def test_no_market_data_returns_zero(self):
        """Expected: graceful no-data path returns score 0."""
        result = momentum_node({"ticker": "TEST", "market_data": {}, "macro_env": {}})
        assert result["momentum"]["score"] == 0

    def test_reasoning_chain_appended(self):
        """Expected: one reasoning_chain entry from momentum agent."""
        result = momentum_node(_base_state("600519.SS"))
        chain = result.get("reasoning_chain", [])
        assert len(chain) == 1
        assert chain[0]["agent"] == "momentum"

    def test_range_position_bounded(self):
        """Expected: range_position_pct between 0 and 100."""
        result = momentum_node(_base_state("000858.SZ"))
        pos = result["momentum"]["range_position_pct"]
        assert 0 <= pos <= 100

    def test_breakout_flag_is_bool(self):
        """Expected: breakout_20 is a boolean."""
        result = momentum_node(_base_state("600519.SS"))
        assert isinstance(result["momentum"]["breakout_20"], bool)
