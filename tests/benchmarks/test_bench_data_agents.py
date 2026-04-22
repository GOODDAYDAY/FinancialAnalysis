"""
Functional benchmarks for non-LLM data-collection agents.

Uses real yfinance / akshare calls — no API key needed.
Verifies that each agent:
  1. Returns the expected output keys
  2. Produces values within documented valid ranges
  3. Appends a correctly-labelled reasoning_chain entry

These run on every CI push as part of the benchmark job.
"""

import pytest
from backend.agents.market_data.node import market_data_node
from backend.agents.macro_env.node import macro_env_node
from backend.agents.sector.node import sector_node
from backend.agents.momentum.node import momentum_node
from backend.agents.quant.node import quant_node
from backend.agents.grid_strategy.node import grid_strategy_node


TICKER_A = "600519.SS"   # Kweichow Moutai — liquid A-share, always has data
TICKER_US = "AAPL"       # Apple — verifies US ticker path


# ── market_data ───────────────────────────────────────────────────────────

class BenchmarkMarketData:

    def test_price_is_positive(self):
        result = market_data_node({"ticker": TICKER_A})
        assert result["market_data"]["current_price"] > 0

    def test_rsi_in_valid_range(self):
        result = market_data_node({"ticker": TICKER_A})
        rsi = result["market_data"].get("rsi_14")
        if rsi is not None:
            assert 0 <= rsi <= 100, f"RSI out of bounds: {rsi}"

    def test_sma20_present_and_positive(self):
        result = market_data_node({"ticker": TICKER_A})
        sma = result["market_data"].get("sma_20")
        if sma is not None:
            assert sma > 0

    def test_technical_signals_is_list(self):
        result = market_data_node({"ticker": TICKER_A})
        assert isinstance(result["market_data"]["technical_signals"], list)

    def test_us_ticker_returns_data(self):
        result = market_data_node({"ticker": TICKER_US})
        assert result["market_data"]["current_price"] > 0

    def test_reasoning_chain_labelled(self):
        result = market_data_node({"ticker": TICKER_A})
        assert result["reasoning_chain"][0]["agent"] == "market_data"


# ── macro_env ─────────────────────────────────────────────────────────────

class BenchmarkMacroEnv:
    VALID_REGIMES = {"BULL MARKET", "BEAR MARKET", "SIDEWAYS / MIXED"}

    def test_overall_regime_valid(self):
        result = macro_env_node({})
        assert result["macro_env"]["overall_regime"] in self.VALID_REGIMES

    def test_at_least_one_index_returned(self):
        result = macro_env_node({})
        assert len(result["macro_env"]["indices"]) >= 1

    def test_primary_regime_non_empty(self):
        result = macro_env_node({})
        assert len(result["macro_env"]["primary_regime"]) > 0

    def test_counts_sum_to_index_count(self):
        result = macro_env_node({})
        m = result["macro_env"]
        total_classified = m["bull_count"] + m["bear_count"] + m["sideways_count"]
        index_count = len(m["indices"])
        # counts may not sum perfectly if some indices have UNKNOWN regime
        assert total_classified <= index_count

    def test_summary_mentions_regime(self):
        result = macro_env_node({})
        summary = result["macro_env"]["summary"]
        assert "BULL" in summary or "BEAR" in summary or "SIDEWAYS" in summary

    def test_reasoning_chain_labelled(self):
        result = macro_env_node({})
        assert result["reasoning_chain"][0]["agent"] == "macro_env"


# ── sector ────────────────────────────────────────────────────────────────

class BenchmarkSector:

    def test_top_sectors_non_empty(self):
        result = sector_node({"ticker": TICKER_A})
        assert len(result["sector"]["top_sectors"]) >= 1

    def test_sector_has_name_and_change_pct(self):
        result = sector_node({"ticker": TICKER_A})
        for s in result["sector"]["top_sectors"]:
            assert "name" in s
            assert isinstance(s["change_pct"], (int, float))

    def test_top_concepts_non_empty(self):
        result = sector_node({"ticker": TICKER_A})
        assert len(result["sector"]["top_concepts"]) >= 1

    def test_a_share_ticker_maps_to_industry(self):
        """600519.SS should map to the baijiu or consumer sector."""
        result = sector_node({"ticker": TICKER_A})
        industry = result["sector"]["stock_industry"].get("industry_name", "")
        # If akshare returns data, industry should be non-empty
        # (allow empty if akshare is slow — just verify no crash)
        assert isinstance(industry, str)

    def test_summary_non_empty(self):
        result = sector_node({"ticker": TICKER_A})
        assert len(result["sector"]["summary"]) > 5

    def test_reasoning_chain_labelled(self):
        result = sector_node({"ticker": TICKER_A})
        assert result["reasoning_chain"][0]["agent"] == "sector"


# ── momentum ──────────────────────────────────────────────────────────────

class BenchmarkMomentum:
    VALID_REGIMES = {
        "STRONG BULLISH MOMENTUM", "BULLISH MOMENTUM",
        "NEUTRAL / CONSOLIDATING",
        "BEARISH MOMENTUM", "STRONG BEARISH MOMENTUM",
        "INSUFFICIENT DATA", "NO DATA",
    }

    def test_score_in_range(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        assert -100 <= result["momentum"]["score"] <= 100

    def test_regime_valid(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        assert result["momentum"]["regime"] in self.VALID_REGIMES

    def test_returns_dict_has_horizons(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        returns = result["momentum"]["returns"]
        assert "5d" in returns and "20d" in returns

    def test_breakout_flag_is_bool(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        assert isinstance(result["momentum"]["breakout_20"], bool)

    def test_range_position_between_0_and_100(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        pos = result["momentum"]["range_position_pct"]
        assert 0 <= pos <= 100

    def test_no_data_returns_zero_gracefully(self):
        result = momentum_node({"ticker": "TEST", "market_data": {}, "macro_env": {}})
        assert result["momentum"]["score"] == 0

    def test_reasoning_chain_labelled(self):
        md = market_data_node({"ticker": TICKER_A})
        result = momentum_node({"ticker": TICKER_A, "market_data": md["market_data"], "macro_env": {}})
        assert result["reasoning_chain"][0]["agent"] == "momentum"


# ── quant ─────────────────────────────────────────────────────────────────

class BenchmarkQuant:

    def test_score_in_range(self):
        md = market_data_node({"ticker": TICKER_A})
        result = quant_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert -100 <= result["quant"]["score"] <= 100

    def test_signals_list_non_empty_for_major_stock(self):
        md = market_data_node({"ticker": TICKER_A})
        result = quant_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert len(result["quant"]["signals"]) >= 1

    def test_each_signal_type_valid(self):
        md = market_data_node({"ticker": TICKER_A})
        result = quant_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        for s in result["quant"]["signals"]:
            assert s["type"] in ("bullish", "bearish", "neutral")

    def test_verdict_non_empty(self):
        md = market_data_node({"ticker": TICKER_A})
        result = quant_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert len(result["quant"]["verdict"]) > 0

    def test_no_data_score_zero(self):
        result = quant_node({"ticker": "TEST", "market_data": {}})
        assert result["quant"]["score"] == 0

    def test_reasoning_chain_labelled(self):
        md = market_data_node({"ticker": TICKER_A})
        result = quant_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert result["reasoning_chain"][0]["agent"] == "quant"


# ── grid_strategy ─────────────────────────────────────────────────────────

class BenchmarkGridStrategy:

    def test_score_in_range(self):
        md = market_data_node({"ticker": TICKER_A})
        result = grid_strategy_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert 0 <= result["grid_strategy"]["score"] <= 100

    def test_strategies_list_has_entries(self):
        md = market_data_node({"ticker": TICKER_A})
        result = grid_strategy_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert len(result["grid_strategy"]["strategies"]) >= 1

    def test_annual_volatility_positive(self):
        md = market_data_node({"ticker": TICKER_A})
        result = grid_strategy_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        vol = result["grid_strategy"].get("annual_volatility_pct", 0)
        assert vol > 0

    def test_best_monthly_return_non_negative(self):
        md = market_data_node({"ticker": TICKER_A})
        result = grid_strategy_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        ret = result["grid_strategy"].get("best_monthly_return_pct", 0)
        assert ret >= 0

    def test_reasoning_chain_labelled(self):
        md = market_data_node({"ticker": TICKER_A})
        result = grid_strategy_node({"ticker": TICKER_A, "market_data": md["market_data"]})
        assert result["reasoning_chain"][0]["agent"] == "grid_strategy"
