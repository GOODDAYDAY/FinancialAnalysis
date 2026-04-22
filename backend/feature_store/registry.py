"""
Feature Registry: unified entry point for computing all quantitative
features for a given ticker.

Ensures training and inference use the same computation logic by
centralizing feature definitions and compute functions.

Usage:
    from backend.feature_store.registry import compute_features
    features = compute_features("600519.SS")
    # features["sma_20"], features["rsi_14"], features["feature_schema_version"], ...
"""

import logging
from typing import Any

from backend.feature_store.definitions import (
    FEATURES,
    FEATURE_SCHEMA_VERSION,
    Feature,
    get_feature,
)

logger = logging.getLogger(__name__)


def _sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


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
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]

    if len(macd_line) < signal:
        return macd_line[-1] if macd_line else None, None

    signal_line = ema(macd_line, signal)
    return macd_line[-1], signal_line[-1]


def _compute_bollinger(
    closes: list[float], period: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None]:
    if len(closes) < period:
        return None, None
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((x - mean) ** 2 for x in window) / period
    std = variance ** 0.5
    return mean + num_std * std, mean - num_std * std


def _compute_atr(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    if len(closes) < period + 1 or len(highs) < period + 1 or len(lows) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-period:]) / period


def _compute_stochastic(
    highs: list[float], lows: list[float], closes: list[float], period: int = 14
) -> float | None:
    if len(closes) < period or len(highs) < period or len(lows) < period:
        return None
    window_high = max(highs[-period:])
    window_low = min(lows[-period:])
    if window_high == window_low:
        return None
    return (closes[-1] - window_low) / (window_high - window_low) * 100


def _compute_obv_slope(
    closes: list[float], volumes: list[float], lookback: int = 10
) -> float | None:
    if len(closes) < lookback + 11 or len(volumes) < lookback + 11:
        return None
    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    recent = obv[-lookback:]
    slope = recent[-1] - recent[0]
    baseline = abs(obv[-lookback - 1]) if abs(obv[-lookback - 1]) > 1 else 1
    return slope / baseline * 100


# Map feature name -> compute function. Each takes (ohlcv_dict) and returns a value.
_COMPUTE_FNS: dict[str, callable] = {
    "sma_20": lambda d: _sma(d["closes"], 20),
    "sma_50": lambda d: _sma(d["closes"], 50),
    "sma_200": lambda d: _sma(d["closes"], 200),
    "rsi_14": lambda d: _compute_rsi(d["closes"], 14),
    "macd": lambda d: _compute_macd(d["closes"])[0],
    "macd_signal": lambda d: _compute_macd(d["closes"])[1],
    "bollinger_upper": lambda d: _compute_bollinger(d["closes"])[0],
    "bollinger_lower": lambda d: _compute_bollinger(d["closes"])[1],
    "atr_14": lambda d: _compute_atr(d["highs"], d["lows"], d["closes"], 14),
    "stochastic_k": lambda d: _compute_stochastic(d["highs"], d["lows"], d["closes"], 14),
    "obv_slope_pct": lambda d: _compute_obv_slope(d["closes"], d["volumes"]),
}


def compute_features(ticker: str, ohlcv: dict | None = None) -> dict[str, Any]:
    """
    Compute all registered features for a ticker.

    Args:
        ticker: stock ticker string
        ohlcv: optional pre-fetched OHLCV data. If None, fetched via yfinance.
               Expected keys: closes, highs, lows, volumes, current_price,
               pe_ratio, fifty_two_week_high, fifty_two_week_low, price_change_pct

    Returns:
        dict with all feature values + feature_schema_version metadata.
    """
    if ohlcv is None:
        ohlcv = _fetch_ohlcv(ticker)
        if not ohlcv:
            logger.warning("No OHLCV data for %s, returning empty features", ticker)
            return {"feature_schema_version": FEATURE_SCHEMA_VERSION}

    result: dict[str, Any] = {}

    # Computed features
    for name, fn in _COMPUTE_FNS.items():
        try:
            value = fn(ohlcv)
            result[name] = value
        except Exception as e:
            logger.warning("Feature compute failed for %s/%s: %s", ticker, name, e)
            result[name] = None

    # Pass-through features (direct from OHLCV / market data)
    for key in ("current_price", "volume", "pe_ratio",
                "fifty_two_week_high", "fifty_two_week_low", "price_change_pct"):
        if key in ohlcv:
            result[key] = ohlcv[key]

    # Metadata
    result["feature_schema_version"] = FEATURE_SCHEMA_VERSION

    return result


def _fetch_ohlcv(ticker: str) -> dict | None:
    """Fetch raw OHLCV data via yfinance. Returns None on failure."""
    try:
        import yfinance as yf
        from backend.utils.ticker import normalize_for_yfinance

        for cand in normalize_for_yfinance(ticker):
            try:
                stock = yf.Ticker(cand)
                hist = stock.history(period="1y")
                if hist is None or hist.empty:
                    continue
                closes = hist["Close"].values.tolist()
                highs = hist["High"].values.tolist()
                lows = hist["Low"].values.tolist()
                volumes = hist["Volume"].values.tolist()
                info = stock.info
                prev_close = closes[-2] if len(closes) >= 2 else closes[-1]
                change_pct = ((closes[-1] - prev_close) / prev_close * 100) if prev_close else None
                return {
                    "closes": closes,
                    "highs": highs,
                    "lows": lows,
                    "volumes": volumes,
                    "current_price": round(closes[-1], 2) if closes else None,
                    "pe_ratio": info.get("trailingPE"),
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                    "price_change_pct": round(change_pct, 2) if change_pct else None,
                }
            except Exception:
                continue
    except Exception as e:
        logger.warning("OHLCV fetch failed for %s: %s", ticker, e)
    return None
