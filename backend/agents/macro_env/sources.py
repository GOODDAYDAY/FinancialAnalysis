"""
Macro environment data sources.

Fetches broad market indices via akshare to assess whether the
overall market is bullish, bearish, or sideways. Used by downstream
agents to contextualize individual stock recommendations.
"""

import logging

logger = logging.getLogger(__name__)

# Key market indices to track
INDICES = {
    "sh000001": "上证指数",      # Shanghai Composite
    "sz399001": "深证成指",      # Shenzhen Component
    "sz399006": "创业板指",      # ChiNext
    "sh000300": "沪深300",       # CSI 300
    "sh000016": "上证50",        # SSE 50
}


def fetch_index_snapshot() -> dict:
    """
    Fetch the latest snapshot of key Chinese market indices.
    Returns a dict mapping index symbol -> {name, price, change, change_pct, regime}.
    """
    import akshare as ak
    import pandas as pd

    results = {}

    # Save pandas options (akshare has the \u escape issue)
    saved_infer = None
    saved_storage = None
    try:
        saved_infer = pd.get_option("future.infer_string")
    except Exception:
        pass
    try:
        saved_storage = pd.get_option("mode.string_storage")
    except Exception:
        pass

    try:
        try:
            pd.set_option("future.infer_string", False)
        except Exception:
            pass
        try:
            pd.set_option("mode.string_storage", "python")
        except Exception:
            pass

        for symbol, display_name in INDICES.items():
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
                if df is None or df.empty:
                    continue

                # Get last ~60 rows to compute trend
                recent = df.tail(60)
                closes = recent["close"].astype(float).tolist()

                if not closes:
                    continue

                current = closes[-1]
                prev = closes[-2] if len(closes) >= 2 else current
                change = current - prev
                change_pct = (change / prev * 100) if prev else 0.0

                # 5 / 20 / 60 day returns
                d5 = ((current / closes[-6] - 1) * 100) if len(closes) >= 6 else None
                d20 = ((current / closes[-21] - 1) * 100) if len(closes) >= 21 else None
                d60 = ((current / closes[0] - 1) * 100) if len(closes) >= 2 else None

                # Simple trend classification
                regime = _classify_regime(d5, d20, d60)

                results[symbol] = {
                    "name": display_name,
                    "price": round(current, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "return_5d_pct": round(d5, 2) if d5 is not None else None,
                    "return_20d_pct": round(d20, 2) if d20 is not None else None,
                    "return_60d_pct": round(d60, 2) if d60 is not None else None,
                    "regime": regime,
                }
                logger.info("Index %s: %.2f (%+.2f%%), regime=%s", symbol, current, change_pct, regime)
            except Exception as e:
                logger.warning("Failed to fetch index %s: %s", symbol, e)
    finally:
        if saved_infer is not None:
            try:
                pd.set_option("future.infer_string", saved_infer)
            except Exception:
                pass
        if saved_storage is not None:
            try:
                pd.set_option("mode.string_storage", saved_storage)
            except Exception:
                pass

    return results


def fetch_north_bound_flow() -> dict:
    """
    Fetch north-bound capital flow (HK Connect -> A-share).
    This is a key indicator of foreign sentiment on A-share.
    """
    try:
        import akshare as ak
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is None or df.empty:
            return {}
        row = df.iloc[0]
        return {
            "source": "Eastmoney HSGT",
            "summary": f"{row.to_dict()}",
        }
    except Exception as e:
        logger.warning("North-bound flow fetch failed: %s", e)
        return {}


def _classify_regime(d5, d20, d60) -> str:
    """Classify market regime based on multi-horizon returns."""
    scores = 0
    counts = 0
    for r in (d5, d20, d60):
        if r is None:
            continue
        counts += 1
        if r > 3:
            scores += 2
        elif r > 0.5:
            scores += 1
        elif r < -3:
            scores -= 2
        elif r < -0.5:
            scores -= 1

    if counts == 0:
        return "UNKNOWN"
    avg = scores / counts
    if avg >= 1.5:
        return "STRONG BULL"
    if avg >= 0.5:
        return "BULL"
    if avg <= -1.5:
        return "STRONG BEAR"
    if avg <= -0.5:
        return "BEAR"
    return "SIDEWAYS"
