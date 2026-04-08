"""
Momentum Agent — pure algorithmic short/medium-term trend analysis.

Exists specifically to fix the problem where the system recommends
SELL on a stock that's been strongly rising recently. Quant's SMA/MACD
signals lag; momentum agent catches the fresh price action.

Computes:
  - 3d / 5d / 10d / 20d cumulative returns
  - Recent breakout detection (new highs vs 20d range)
  - Volume surge (today's volume vs 20d average)
  - Trend strength (ADX-like directional movement)
  - Relative strength vs market index (if macro_env provides one)
  - Composite momentum score and regime tag

Pure math, no LLM. Runs fast (<100ms).
"""

import logging

logger = logging.getLogger(__name__)


def momentum_node(state: dict) -> dict:
    """Compute multi-horizon momentum signals from market_data."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})
    macro_env = state.get("macro_env", {})

    current_price = market_data.get("current_price")
    if not current_price:
        return {
            "momentum": {"score": 0, "regime": "NO DATA", "signals": []},
            "reasoning_chain": [{"agent": "momentum", "note": "no market data"}],
        }

    # We need recent closes. market_data provider already computed SMAs
    # from a 1y history but didn't store the raw series. Recompute here
    # by calling providers directly — cheap because yfinance caches.
    closes, volumes = _fetch_recent_series(ticker)
    if not closes or len(closes) < 5:
        logger.warning("Momentum: insufficient price history for %s", ticker)
        return {
            "momentum": {"score": 0, "regime": "INSUFFICIENT DATA", "signals": []},
            "reasoning_chain": [{"agent": "momentum", "note": "insufficient data"}],
        }

    # Compute returns over multiple horizons
    returns = {}
    for days in (3, 5, 10, 20, 60):
        if len(closes) > days:
            returns[days] = (closes[-1] / closes[-1 - days] - 1) * 100
        else:
            returns[days] = None

    # 20-day range position
    recent20 = closes[-20:] if len(closes) >= 20 else closes
    range_low = min(recent20)
    range_high = max(recent20)
    range_position = (
        (current_price - range_low) / (range_high - range_low) * 100
        if range_high > range_low else 50.0
    )

    # Breakout: price at or above 20d high
    breakout_20 = current_price >= range_high * 0.995

    # Volume surge
    volume_surge = None
    if volumes and len(volumes) >= 21:
        recent_vol = volumes[-1]
        avg_vol_20 = sum(volumes[-21:-1]) / 20
        if avg_vol_20 > 0:
            volume_surge = recent_vol / avg_vol_20

    # Trend strength: how consistently the price has moved in one direction
    if len(closes) >= 20:
        ups = sum(1 for i in range(len(closes) - 19, len(closes))
                  if closes[i] > closes[i - 1])
        trend_consistency = ups / 20 * 100   # % of up days out of last 20
    else:
        trend_consistency = 50.0

    # Relative strength vs macro benchmark
    rs_vs_market = None
    if macro_env and macro_env.get("indices"):
        # Use CSI 300 as reference
        csi300 = macro_env["indices"].get("sh000300", {})
        ref_20d = csi300.get("return_20d_pct")
        if ref_20d is not None and returns.get(20) is not None:
            rs_vs_market = returns[20] - ref_20d

    # Score momentum (-100 .. +100)
    score = 0
    signals = []

    # Short-term momentum (3-5 day) is HEAVILY weighted — this is the
    # core fix for "rising stock gets SELL"
    r5 = returns.get(5)
    if r5 is not None:
        if r5 >= 10:
            score += 30
            signals.append({
                "name": "Strong 5-day Surge",
                "type": "bullish",
                "detail": f"+{r5:.2f}% in 5 days — strong short-term momentum",
                "weight": 30,
            })
        elif r5 >= 5:
            score += 20
            signals.append({
                "name": "5-day Uptrend",
                "type": "bullish",
                "detail": f"+{r5:.2f}% in 5 days",
                "weight": 20,
            })
        elif r5 >= 2:
            score += 10
            signals.append({
                "name": "Mild 5-day Uptrend",
                "type": "bullish",
                "detail": f"+{r5:.2f}% in 5 days",
                "weight": 10,
            })
        elif r5 <= -10:
            score -= 30
            signals.append({
                "name": "Strong 5-day Crash",
                "type": "bearish",
                "detail": f"{r5:.2f}% in 5 days — severe drop",
                "weight": -30,
            })
        elif r5 <= -5:
            score -= 20
            signals.append({
                "name": "5-day Downtrend",
                "type": "bearish",
                "detail": f"{r5:.2f}% in 5 days",
                "weight": -20,
            })

    # 20-day momentum
    r20 = returns.get(20)
    if r20 is not None:
        if r20 >= 15:
            score += 20
            signals.append({
                "name": "20-day Strong Rally",
                "type": "bullish",
                "detail": f"+{r20:.2f}% in 20 days",
                "weight": 20,
            })
        elif r20 >= 5:
            score += 10
            signals.append({
                "name": "20-day Uptrend",
                "type": "bullish",
                "detail": f"+{r20:.2f}% in 20 days",
                "weight": 10,
            })
        elif r20 <= -15:
            score -= 20
            signals.append({
                "name": "20-day Decline",
                "type": "bearish",
                "detail": f"{r20:.2f}% in 20 days",
                "weight": -20,
            })
        elif r20 <= -5:
            score -= 10
            signals.append({
                "name": "20-day Downtrend",
                "type": "bearish",
                "detail": f"{r20:.2f}% in 20 days",
                "weight": -10,
            })

    # Breakout signal
    if breakout_20:
        score += 15
        signals.append({
            "name": "20-day Breakout",
            "type": "bullish",
            "detail": f"Price at 20-day high ({range_high:.2f})",
            "weight": 15,
        })

    # Range position
    if range_position >= 90 and r5 is not None and r5 > 0:
        score += 10
        signals.append({
            "name": "Near Range Top (bullish w/ momentum)",
            "type": "bullish",
            "detail": f"At {range_position:.0f}% of 20-day range with positive 5d return",
            "weight": 10,
        })
    elif range_position <= 10:
        score -= 5
        signals.append({
            "name": "Near Range Bottom",
            "type": "bearish",
            "detail": f"At {range_position:.0f}% of 20-day range",
            "weight": -5,
        })

    # Volume surge on up days is bullish
    if volume_surge is not None and r5 is not None:
        if volume_surge >= 2.0 and r5 > 0:
            score += 10
            signals.append({
                "name": "Bullish Volume Surge",
                "type": "bullish",
                "detail": f"Volume {volume_surge:.1f}x 20-day avg on positive day",
                "weight": 10,
            })
        elif volume_surge >= 2.0 and r5 < 0:
            score -= 10
            signals.append({
                "name": "Bearish Volume Surge",
                "type": "bearish",
                "detail": f"Volume {volume_surge:.1f}x 20-day avg on negative day",
                "weight": -10,
            })

    # Trend consistency
    if trend_consistency >= 70:
        score += 5
        signals.append({
            "name": "Consistent Uptrend",
            "type": "bullish",
            "detail": f"{trend_consistency:.0f}% up days in last 20 sessions",
            "weight": 5,
        })
    elif trend_consistency <= 30:
        score -= 5
        signals.append({
            "name": "Consistent Downtrend",
            "type": "bearish",
            "detail": f"{trend_consistency:.0f}% up days in last 20 sessions",
            "weight": -5,
        })

    # Relative strength vs market
    if rs_vs_market is not None:
        if rs_vs_market >= 5:
            score += 10
            signals.append({
                "name": "Outperforming Market",
                "type": "bullish",
                "detail": f"+{rs_vs_market:.2f}% relative to CSI 300 over 20 days",
                "weight": 10,
            })
        elif rs_vs_market <= -5:
            score -= 10
            signals.append({
                "name": "Underperforming Market",
                "type": "bearish",
                "detail": f"{rs_vs_market:.2f}% relative to CSI 300 over 20 days",
                "weight": -10,
            })

    score = max(-100, min(100, score))

    if score >= 40:
        regime = "STRONG BULLISH MOMENTUM"
    elif score >= 15:
        regime = "BULLISH MOMENTUM"
    elif score >= -15:
        regime = "NEUTRAL / CONSOLIDATING"
    elif score >= -40:
        regime = "BEARISH MOMENTUM"
    else:
        regime = "STRONG BEARISH MOMENTUM"

    momentum = {
        "score": score,
        "regime": regime,
        "signals": signals,
        "returns": {f"{k}d": round(v, 2) if v is not None else None for k, v in returns.items()},
        "range_position_pct": round(range_position, 1),
        "breakout_20": breakout_20,
        "volume_surge_ratio": round(volume_surge, 2) if volume_surge else None,
        "trend_consistency_pct": round(trend_consistency, 1),
        "relative_strength_vs_csi300_20d": round(rs_vs_market, 2) if rs_vs_market is not None else None,
        "summary": (
            f"Momentum score {score}/100 ({regime}). "
            f"Returns: 5d={returns.get(5)}, 20d={returns.get(20)}. "
            f"Range position {range_position:.0f}%. "
            f"{len(signals)} signals."
        ),
    }

    logger.info("Momentum for %s: score=%d, regime=%s", ticker, score, regime)

    return {
        "momentum": momentum,
        "reasoning_chain": [{
            "agent": "momentum",
            "score": score,
            "regime": regime,
            "return_5d_pct": returns.get(5),
            "return_20d_pct": returns.get(20),
            "breakout_20": breakout_20,
        }],
    }


def _fetch_recent_series(ticker: str) -> tuple[list[float], list[float]]:
    """
    Fetch recent close and volume series directly from yfinance.
    Uses the same normalization as market_data/providers.py.
    """
    try:
        import yfinance as yf
        from backend.agents.market_data.providers import normalize_ticker

        candidates = normalize_ticker(ticker)
        for cand in candidates:
            try:
                stock = yf.Ticker(cand)
                hist = stock.history(period="3mo")
                if hist is not None and not hist.empty:
                    closes = hist["Close"].values.tolist()
                    volumes = hist["Volume"].values.tolist()
                    return closes, volumes
            except Exception:
                continue
    except Exception as e:
        logger.warning("Could not fetch series for %s: %s", ticker, e)
    return [], []
