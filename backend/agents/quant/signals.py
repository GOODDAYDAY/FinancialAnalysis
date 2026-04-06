"""
Quantitative signal computation: pure math, no LLM.

Signal categories:
- Moving average system: golden cross / death cross, price vs MA
- Momentum: RSI zones, MACD direction
- Volatility: 52-week position, drawdown
- Valuation: P/E scoring
"""


def compute_ma_signals(price, sma_20, sma_50, sma_200) -> list[dict]:
    """Compute moving average system signals."""
    signals = []

    if sma_20 and sma_50:
        if sma_20 > sma_50:
            signals.append({"name": "Golden Cross", "type": "bullish",
                            "detail": f"SMA20({sma_20:.2f}) > SMA50({sma_50:.2f})", "weight": 15})
        else:
            signals.append({"name": "Death Cross", "type": "bearish",
                            "detail": f"SMA20({sma_20:.2f}) < SMA50({sma_50:.2f})", "weight": -15})

    if sma_200 and price:
        if price > sma_200:
            signals.append({"name": "Above MA200", "type": "bullish",
                            "detail": f"Price({price:.2f}) above long-term trend({sma_200:.2f})", "weight": 10})
        else:
            pct_below = (sma_200 - price) / sma_200 * 100
            signals.append({"name": "Below MA200", "type": "bearish",
                            "detail": f"Price {pct_below:.1f}% below long-term trend", "weight": -10})

    if sma_20 and price:
        if price > sma_20:
            signals.append({"name": "Price > SMA20", "type": "bullish",
                            "detail": "Short-term uptrend confirmed", "weight": 5})
        else:
            signals.append({"name": "Price < SMA20", "type": "bearish",
                            "detail": "Short-term downtrend confirmed", "weight": -5})

    return signals


def compute_rsi_signals(rsi) -> list[dict]:
    """Compute RSI momentum signals."""
    if rsi is None:
        return []

    if rsi > 80:
        return [{"name": "RSI Extreme Overbought", "type": "bearish",
                 "detail": f"RSI={rsi:.1f}, strong sell signal", "weight": -20}]
    elif rsi > 70:
        return [{"name": "RSI Overbought", "type": "bearish",
                 "detail": f"RSI={rsi:.1f}, caution zone", "weight": -10}]
    elif rsi < 20:
        return [{"name": "RSI Extreme Oversold", "type": "bullish",
                 "detail": f"RSI={rsi:.1f}, strong buy signal", "weight": 20}]
    elif rsi < 30:
        return [{"name": "RSI Oversold", "type": "bullish",
                 "detail": f"RSI={rsi:.1f}, potential rebound", "weight": 10}]
    elif 45 <= rsi <= 55:
        return [{"name": "RSI Neutral", "type": "neutral",
                 "detail": f"RSI={rsi:.1f}, no momentum signal", "weight": 0}]
    elif rsi > 55:
        return [{"name": "RSI Bullish Momentum", "type": "bullish",
                 "detail": f"RSI={rsi:.1f}, positive momentum", "weight": 5}]
    else:
        return [{"name": "RSI Bearish Momentum", "type": "bearish",
                 "detail": f"RSI={rsi:.1f}, negative momentum", "weight": -5}]


def compute_macd_signals(macd, macd_signal) -> list[dict]:
    """Compute MACD signals."""
    if macd is None or macd_signal is None:
        return []

    diff = macd - macd_signal
    if macd > macd_signal and macd > 0:
        return [{"name": "MACD Strong Bullish", "type": "bullish",
                 "detail": f"MACD({macd:.4f}) above signal({macd_signal:.4f}) and positive", "weight": 15}]
    elif macd > macd_signal:
        return [{"name": "MACD Bullish Crossover", "type": "bullish",
                 "detail": f"MACD above signal, diff={diff:.4f}", "weight": 8}]
    elif macd < macd_signal and macd < 0:
        return [{"name": "MACD Strong Bearish", "type": "bearish",
                 "detail": f"MACD({macd:.4f}) below signal({macd_signal:.4f}) and negative", "weight": -15}]
    else:
        return [{"name": "MACD Bearish Crossover", "type": "bearish",
                 "detail": f"MACD below signal, diff={diff:.4f}", "weight": -8}]


def compute_range_signals(price, high_52w, low_52w) -> list[dict]:
    """Compute 52-week range position and drawdown signals."""
    if not (high_52w and low_52w and price):
        return []

    signals = []
    range_52w = high_52w - low_52w
    if range_52w <= 0:
        return []

    position = (price - low_52w) / range_52w * 100

    if position > 90:
        signals.append({"name": "Near 52W High", "type": "bearish",
                        "detail": f"Price at {position:.0f}% of 52-week range, limited upside", "weight": -10})
    elif position > 70:
        signals.append({"name": "Upper 52W Range", "type": "bullish",
                        "detail": f"Price at {position:.0f}% of range, strong momentum", "weight": 5})
    elif position < 20:
        signals.append({"name": "Near 52W Low", "type": "bullish",
                        "detail": f"Price at {position:.0f}% of range, potential value", "weight": 10})
    elif position < 40:
        signals.append({"name": "Lower 52W Range", "type": "bearish",
                        "detail": f"Price at {position:.0f}% of range, weak momentum", "weight": -5})
    else:
        signals.append({"name": "Mid 52W Range", "type": "neutral",
                        "detail": f"Price at {position:.0f}% of range", "weight": 0})

    drawdown = (high_52w - price) / high_52w * 100
    if drawdown > 30:
        signals.append({"name": "Severe Drawdown", "type": "bearish",
                        "detail": f"{drawdown:.1f}% from 52-week high", "weight": -10})
    elif drawdown > 15:
        signals.append({"name": "Moderate Drawdown", "type": "bearish",
                        "detail": f"{drawdown:.1f}% from 52-week high", "weight": -5})

    return signals


def compute_pe_signals(pe) -> list[dict]:
    """Compute P/E valuation signals."""
    if pe is None:
        return []

    if pe < 0:
        return [{"name": "Negative P/E", "type": "bearish", "detail": "Company is unprofitable", "weight": -10}]
    elif pe > 100:
        return [{"name": "Extreme P/E", "type": "bearish", "detail": f"P/E={pe:.1f}, extremely overvalued", "weight": -10}]
    elif pe > 40:
        return [{"name": "High P/E", "type": "bearish", "detail": f"P/E={pe:.1f}, growth premium required", "weight": -5}]
    elif pe < 10:
        return [{"name": "Low P/E", "type": "bullish", "detail": f"P/E={pe:.1f}, potential value stock", "weight": 10}]
    elif pe < 20:
        return [{"name": "Moderate P/E", "type": "bullish", "detail": f"P/E={pe:.1f}, reasonable valuation", "weight": 5}]
    return []
