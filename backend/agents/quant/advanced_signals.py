"""
Advanced quantitative signals: Bollinger Bands, ATR, Stochastic, OBV.

These indicators need the raw OHLCV series (not just the aggregates that
market_data/providers.py stores). The Quant agent fetches a 3-month
history via yfinance and hands it to the functions below.

Pure math, no LLM. All signals follow the same {name/type/detail/weight}
dict contract used by signals.py.
"""

import logging

logger = logging.getLogger(__name__)


def fetch_ohlcv_series(ticker: str) -> dict:
    """
    Fetch a ~3-month OHLCV history via yfinance, using the shared
    ticker normalizer. Returns {} on any failure so the caller can
    gracefully skip advanced signals.
    """
    try:
        import yfinance as yf
        from backend.utils.ticker import normalize_for_yfinance

        for cand in normalize_for_yfinance(ticker):
            try:
                stock = yf.Ticker(cand)
                hist = stock.history(period="3mo")
                if hist is None or hist.empty:
                    continue
                return {
                    "open": hist["Open"].values.tolist(),
                    "high": hist["High"].values.tolist(),
                    "low": hist["Low"].values.tolist(),
                    "close": hist["Close"].values.tolist(),
                    "volume": hist["Volume"].values.tolist(),
                }
            except Exception as inner:
                logger.debug("advanced_signals candidate %s failed: %s", cand, inner)
    except Exception as e:
        logger.warning("advanced_signals fetch failed for %s: %s", ticker, e)
    return {}


def compute_bollinger_signals(closes: list[float], period: int = 20, num_std: float = 2.0) -> list[dict]:
    """
    Bollinger Bands: mean +/- num_std * stdev over `period`.
    - Price piercing lower band = oversold / potential bounce (bullish).
    - Price piercing upper band = overbought / mean-reversion risk (bearish).
    - Band squeeze (very tight bands) flagged as neutral volatility event.
    """
    if not closes or len(closes) < period:
        return []

    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = variance ** 0.5
    upper = mean + num_std * std
    lower = mean - num_std * std
    price = closes[-1]
    width = (upper - lower) / mean * 100 if mean else 0

    signals = []
    if price >= upper:
        signals.append({
            "name": "Bollinger Upper Break",
            "type": "bearish",
            "detail": f"Price {price:.2f} above upper band {upper:.2f} — mean-reversion risk",
            "weight": -8,
        })
    elif price <= lower:
        signals.append({
            "name": "Bollinger Lower Break",
            "type": "bullish",
            "detail": f"Price {price:.2f} below lower band {lower:.2f} — oversold",
            "weight": 8,
        })
    else:
        # Position within bands (0 = lower, 100 = upper)
        band_range = upper - lower
        if band_range > 0:
            pct = (price - lower) / band_range * 100
            if pct >= 80:
                signals.append({
                    "name": "Bollinger Upper Zone",
                    "type": "bearish",
                    "detail": f"Price at {pct:.0f}% of band range",
                    "weight": -3,
                })
            elif pct <= 20:
                signals.append({
                    "name": "Bollinger Lower Zone",
                    "type": "bullish",
                    "detail": f"Price at {pct:.0f}% of band range",
                    "weight": 3,
                })

    if width < 5 and width > 0:
        signals.append({
            "name": "Bollinger Squeeze",
            "type": "neutral",
            "detail": f"Band width {width:.1f}% of mean — low volatility, breakout pending",
            "weight": 0,
        })

    return signals


def compute_atr_signals(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[dict]:
    """
    Average True Range — volatility measure.
    We report ATR as % of price and flag:
    - very high ATR% (>5%) = elevated risk
    - very low ATR% (<1%) = volatility contraction (neutral)
    """
    if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
        return []

    trs = []
    for i in range(1, len(closes)):
        hi, lo, prev = highs[i], lows[i], closes[i - 1]
        tr = max(hi - lo, abs(hi - prev), abs(lo - prev))
        trs.append(tr)

    recent_trs = trs[-period:]
    atr = sum(recent_trs) / period
    price = closes[-1]
    atr_pct = atr / price * 100 if price else 0

    if atr_pct >= 5:
        return [{
            "name": "High Volatility (ATR)",
            "type": "bearish",
            "detail": f"ATR = {atr_pct:.2f}% of price — elevated risk",
            "weight": -5,
        }]
    if atr_pct <= 1:
        return [{
            "name": "Low Volatility (ATR)",
            "type": "neutral",
            "detail": f"ATR = {atr_pct:.2f}% of price — volatility compression",
            "weight": 0,
        }]
    return [{
        "name": "Normal Volatility (ATR)",
        "type": "neutral",
        "detail": f"ATR = {atr_pct:.2f}% of price",
        "weight": 0,
    }]


def compute_stochastic_signals(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[dict]:
    """
    Stochastic Oscillator (%K): position of close within N-period range.
    - %K > 80 = overbought
    - %K < 20 = oversold
    """
    if len(closes) < period or len(highs) < period or len(lows) < period:
        return []

    window_high = max(highs[-period:])
    window_low = min(lows[-period:])
    close = closes[-1]
    if window_high == window_low:
        return []

    k = (close - window_low) / (window_high - window_low) * 100

    if k >= 80:
        return [{
            "name": "Stochastic Overbought",
            "type": "bearish",
            "detail": f"%K = {k:.1f} (>80)",
            "weight": -8,
        }]
    if k <= 20:
        return [{
            "name": "Stochastic Oversold",
            "type": "bullish",
            "detail": f"%K = {k:.1f} (<20)",
            "weight": 8,
        }]
    return []


def compute_obv_signals(closes: list[float], volumes: list[float]) -> list[dict]:
    """
    On-Balance Volume — cumulative volume weighted by price direction.
    We compare the 10-day slope of OBV to flag accumulation / distribution.
    """
    if len(closes) < 21 or len(volumes) < 21:
        return []

    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])

    recent = obv[-10:]
    slope = recent[-1] - recent[0]
    baseline = abs(obv[-11]) if abs(obv[-11]) > 1 else 1

    pct_change = slope / baseline * 100 if baseline else 0

    # Compare to price direction
    price_change_pct = (closes[-1] / closes[-11] - 1) * 100 if closes[-11] else 0

    if pct_change > 5 and price_change_pct > 0:
        return [{
            "name": "OBV Confirms Uptrend",
            "type": "bullish",
            "detail": f"OBV rising while price up {price_change_pct:.1f}% — accumulation",
            "weight": 8,
        }]
    if pct_change < -5 and price_change_pct < 0:
        return [{
            "name": "OBV Confirms Downtrend",
            "type": "bearish",
            "detail": f"OBV falling while price down {price_change_pct:.1f}% — distribution",
            "weight": -8,
        }]
    if pct_change > 5 and price_change_pct < 0:
        return [{
            "name": "Bullish OBV Divergence",
            "type": "bullish",
            "detail": "OBV rising while price falling — hidden accumulation",
            "weight": 10,
        }]
    if pct_change < -5 and price_change_pct > 0:
        return [{
            "name": "Bearish OBV Divergence",
            "type": "bearish",
            "detail": "OBV falling while price rising — hidden distribution",
            "weight": -10,
        }]
    return []


def compute_advanced_signals(ticker: str) -> list[dict]:
    """
    Top-level helper: fetch OHLCV and run all advanced indicators.
    Returns [] on any failure so Quant degrades gracefully to the
    classical signal set.
    """
    ohlcv = fetch_ohlcv_series(ticker)
    if not ohlcv:
        return []

    closes = ohlcv["close"]
    highs = ohlcv["high"]
    lows = ohlcv["low"]
    volumes = ohlcv["volume"]

    signals: list[dict] = []
    signals.extend(compute_bollinger_signals(closes))
    signals.extend(compute_atr_signals(highs, lows, closes))
    signals.extend(compute_stochastic_signals(highs, lows, closes))
    signals.extend(compute_obv_signals(closes, volumes))
    return signals
