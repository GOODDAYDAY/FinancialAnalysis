"""Mock market data for demo fallback when APIs are unavailable."""

from backend.state import MarketDataResult

_MOCK_DB = {
    "AAPL": {"price": 189.50, "pe": 28.5, "cap": 2.9e12, "high52": 199.62, "low52": 164.08},
    "MSFT": {"price": 415.20, "pe": 35.2, "cap": 3.1e12, "high52": 430.82, "low52": 362.90},
    "GOOGL": {"price": 155.80, "pe": 23.1, "cap": 1.9e12, "high52": 174.90, "low52": 127.90},
    "TSLA": {"price": 248.50, "pe": 62.3, "cap": 792e9, "high52": 278.98, "low52": 138.80},
    "AMZN": {"price": 186.40, "pe": 42.8, "cap": 1.94e12, "high52": 201.20, "low52": 151.61},
}


def get_mock_market_data(ticker: str) -> MarketDataResult:
    """Return plausible mock market data for a given ticker."""
    data = _MOCK_DB.get(ticker.upper(), _MOCK_DB["AAPL"])
    return MarketDataResult(
        ticker=ticker.upper(),
        current_price=data["price"],
        price_change=1.25,
        price_change_pct=0.66,
        volume=52_000_000,
        market_cap=data["cap"],
        pe_ratio=data["pe"],
        fifty_two_week_high=data["high52"],
        fifty_two_week_low=data["low52"],
        day_high=data["price"] * 1.01,
        day_low=data["price"] * 0.99,
        sma_20=data["price"] * 0.98,
        sma_50=data["price"] * 0.96,
        sma_200=data["price"] * 0.92,
        rsi_14=55.0,
        macd=0.85,
        macd_signal=0.62,
        technical_signals=[
            "SMA20 above SMA50 (bullish)",
            "RSI=55.0 — neutral",
            "MACD above signal (bullish)",
        ],
        is_mock=True,
        data_source="mock",
    )


