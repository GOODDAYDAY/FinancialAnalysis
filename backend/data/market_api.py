"""Market data fetcher using yfinance with mock fallback."""

import logging
from backend.state import MarketDataResult
from backend.data.mock_data import mock_market_data

logger = logging.getLogger(__name__)


def fetch_market_data(ticker: str) -> MarketDataResult:
    """Fetch real-time stock data. Falls back to mock on any error."""
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")

        if hist.empty:
            logger.warning("No history data for %s, using mock", ticker)
            return mock_market_data(ticker)

        closes = hist["Close"].values.tolist()
        current_price = closes[-1] if closes else None

        # Calculate technical indicators
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        sma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        sma_200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
        rsi_14 = _compute_rsi(closes, 14)
        macd, macd_signal = _compute_macd(closes)

        # Technical signals
        signals = []
        if sma_20 and sma_50:
            if sma_20 > sma_50:
                signals.append("SMA20 above SMA50 (bullish)")
            else:
                signals.append("SMA20 below SMA50 (bearish)")
        if rsi_14 is not None:
            if rsi_14 > 70:
                signals.append(f"RSI={rsi_14:.1f} — overbought")
            elif rsi_14 < 30:
                signals.append(f"RSI={rsi_14:.1f} — oversold")
            else:
                signals.append(f"RSI={rsi_14:.1f} — neutral")
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                signals.append("MACD above signal (bullish)")
            else:
                signals.append("MACD below signal (bearish)")

        prev_close = closes[-2] if len(closes) >= 2 else current_price
        change = (current_price - prev_close) if current_price and prev_close else None
        change_pct = (change / prev_close * 100) if change and prev_close else None

        return MarketDataResult(
            ticker=ticker,
            current_price=round(current_price, 2) if current_price else None,
            price_change=round(change, 2) if change else None,
            price_change_pct=round(change_pct, 2) if change_pct else None,
            volume=int(hist["Volume"].iloc[-1]) if not hist["Volume"].empty else None,
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            day_high=info.get("dayHigh"),
            day_low=info.get("dayLow"),
            sma_20=round(sma_20, 2) if sma_20 else None,
            sma_50=round(sma_50, 2) if sma_50 else None,
            sma_200=round(sma_200, 2) if sma_200 else None,
            rsi_14=round(rsi_14, 2) if rsi_14 else None,
            macd=round(macd, 4) if macd else None,
            macd_signal=round(macd_signal, 4) if macd_signal else None,
            technical_signals=signals,
            is_mock=False,
            data_source="yfinance",
        )
    except Exception as e:
        logger.warning("Failed to fetch market data for %s: %s. Using mock.", ticker, e)
        return mock_market_data(ticker)


def _compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None]:
    if len(closes) < slow + signal:
        return None, None

    def ema(data: list[float], period: int) -> list[float]:
        result = [sum(data[:period]) / period]
        multiplier = 2 / (period + 1)
        for price in data[period:]:
            result.append((price - result[-1]) * multiplier + result[-1])
        return result

    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    # Align lengths
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]

    if len(macd_line) < signal:
        return macd_line[-1] if macd_line else None, None

    signal_line = ema(macd_line, signal)
    return macd_line[-1], signal_line[-1]
