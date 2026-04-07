"""Real data tests for Grid Strategy Agent (pure algorithms, no LLM)."""

from backend.agents.grid_strategy.node import grid_strategy_node
from backend.agents.grid_strategy.calculator import (
    compute_volatility,
    assess_suitability,
    generate_strategies,
    GridStrategy,
)
from backend.agents.market_data.node import market_data_node


class TestGridSuitability:
    """Suitability scoring on real market data."""

    def test_suitability_score_in_range(self):
        """Expected: score 0-100."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        score = result["grid_strategy"]["score"]
        assert 0 <= score <= 100

    def test_verdict_label_present(self):
        """Expected: verdict is one of the defined labels."""
        md = market_data_node({"ticker": "AAPL"})
        result = grid_strategy_node({"ticker": "AAPL", "market_data": md["market_data"]})
        verdict = result["grid_strategy"]["verdict"]
        assert verdict in ("HIGHLY SUITABLE", "MODERATELY SUITABLE", "MARGINAL", "NOT RECOMMENDED")

    def test_reasons_provided(self):
        """Expected: at least 1 reason explaining the suitability score."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        assert len(result["grid_strategy"]["reasons"]) >= 1


class TestStrategyGeneration:
    """Strategy variants generation."""

    def test_four_strategies_generated(self):
        """Expected: 4 strategy variants (short/medium/long/accumulation)."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        strategies = result["grid_strategy"]["strategies"]
        assert len(strategies) == 4

    def test_strategy_horizons_diverse(self):
        """Expected: short-term, medium-term, long-term all present."""
        md = market_data_node({"ticker": "AAPL"})
        result = grid_strategy_node({"ticker": "AAPL", "market_data": md["market_data"]})
        horizons = {s["horizon"] for s in result["grid_strategy"]["strategies"]}
        assert "short-term" in horizons
        assert "medium-term" in horizons
        assert "long-term" in horizons

    def test_each_strategy_has_required_fields(self):
        """Expected: every strategy has price range, grid count, profit, fees."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        for s in result["grid_strategy"]["strategies"]:
            assert "lower_price" in s
            assert "upper_price" in s
            assert "grid_count" in s
            assert "shares_per_grid" in s
            assert "profit_per_cycle" in s
            assert "fees_per_cycle" in s
            assert "estimated_monthly_return_pct" in s
            assert s["upper_price"] > s["lower_price"]
            assert s["grid_count"] > 0
            assert s["shares_per_grid"] >= 100  # Minimum A-share lot

    def test_fees_are_positive(self):
        """Expected: fees_per_cycle is always > 0 (real-world)."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        for s in result["grid_strategy"]["strategies"]:
            assert s["fees_per_cycle"] > 0

    def test_a_share_lot_size(self):
        """Expected: shares_per_grid is multiple of 100 (A-share lot)."""
        md = market_data_node({"ticker": "600519.SS"})
        result = grid_strategy_node({"ticker": "600519.SS", "market_data": md["market_data"]})
        for s in result["grid_strategy"]["strategies"]:
            assert s["shares_per_grid"] % 100 == 0


class TestVolatilityComputation:
    """Pure math: volatility calculation."""

    def test_zero_volatility_for_constant(self):
        """Expected: vol = 0 for constant price series."""
        vol = compute_volatility([100.0] * 30)
        assert vol == 0.0

    def test_nonzero_volatility_for_varying(self):
        """Expected: vol > 0 for varying prices."""
        prices = [100, 101, 99, 102, 98, 103, 97]
        vol = compute_volatility(prices)
        assert vol > 0


class TestNoMarketData:
    """Edge case: missing market data."""

    def test_returns_unsuitable_verdict(self):
        """Expected: NO DATA verdict when market_data is empty."""
        result = grid_strategy_node({"ticker": "TEST", "market_data": {}})
        assert result["grid_strategy"]["score"] == 0
        assert result["grid_strategy"]["suitable"] is False
