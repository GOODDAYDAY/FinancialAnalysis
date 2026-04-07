"""Real API tests for Market Data Agent (yfinance)."""

import pytest
from backend.agents.market_data.node import market_data_node
from backend.agents.market_data.providers import fetch_market_data


class TestLiveMarketData:
    """Fetch real stock data from yfinance."""

    @pytest.mark.parametrize("ticker", ["600519.SS", "000858.SZ", "AAPL"])
    def test_fetch_price(self, ticker):
        """Expected: non-null price for known tickers."""
        result = market_data_node({"ticker": ticker})
        md = result["market_data"]
        assert md["current_price"] is not None
        assert md["current_price"] > 0

    def test_technical_indicators_computed(self):
        """Expected: RSI, SMA, MACD all present for major stock."""
        result = market_data_node({"ticker": "600519.SS"})
        md = result["market_data"]
        assert md.get("rsi_14") is not None
        assert md.get("sma_20") is not None
        assert md.get("technical_signals") is not None
        assert len(md["technical_signals"]) > 0

    def test_reasoning_chain_recorded(self):
        """Expected: market_data agent appears in reasoning chain."""
        result = market_data_node({"ticker": "AAPL"})
        agents = [s["agent"] for s in result.get("reasoning_chain", [])]
        assert "market_data" in agents


class TestMockFallback:
    """Invalid ticker should fall back to mock data."""

    def test_invalid_ticker_returns_mock(self):
        result = market_data_node({"ticker": "ZZZZZZ_INVALID"})
        md = result["market_data"]
        assert md["is_mock"] is True
        assert md["current_price"] is not None

    def test_empty_ticker_returns_error(self):
        result = market_data_node({"ticker": ""})
        assert len(result.get("errors", [])) > 0
