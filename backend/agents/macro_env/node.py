"""
Macro Environment Agent node.

Gathers broad market context (major indices, regime) so downstream
agents can contextualize individual stock recommendations.
A stock might look overbought on technicals, but if the whole market
is in a strong bull regime, SELL may be the wrong call.
"""

import logging
from backend.agents.macro_env.sources import fetch_index_snapshot, fetch_north_bound_flow

logger = logging.getLogger(__name__)


def macro_env_node(state: dict) -> dict:
    """Fetch macro environment snapshot from akshare."""
    exchange = state.get("exchange", "UNKNOWN")
    ticker = state.get("ticker", "")

    # Macro environment via akshare tracks Chinese market indices only.
    # For HK / US stocks, skip the akshare call — downstream agents will
    # see empty macro and proceed without China market context.
    if exchange not in ("SH", "SZ", "BJ"):
        logger.info("Macro env skipped for %s (exchange=%s, not A-share)", ticker, exchange)
        return {
            "macro_env": {
                "indices": {},
                "primary_regime": "N/A (overseas stock)",
                "overall_regime": "N/A (overseas stock)",
                "bull_count": 0,
                "bear_count": 0,
                "sideways_count": 0,
                "summary": "Macro context (Chinese indices) not applicable for overseas stocks.",
            },
            "reasoning_chain": [{
                "agent": "macro_env",
                "skipped": True,
                "reason": f"exchange={exchange}, not an A-share",
            }],
        }

    logger.info("Fetching macro environment snapshot")

    indices = fetch_index_snapshot()

    # Compute aggregate market regime from CSI 300 (primary benchmark)
    primary = indices.get("sh000300") or (list(indices.values())[0] if indices else {})
    primary_regime = primary.get("regime", "UNKNOWN") if primary else "UNKNOWN"

    # Tally regimes across all indices for a robust view
    regimes = [idx.get("regime") for idx in indices.values() if idx.get("regime")]
    bull_count = sum(1 for r in regimes if r and "BULL" in r)
    bear_count = sum(1 for r in regimes if r and "BEAR" in r)
    sideways_count = sum(1 for r in regimes if r == "SIDEWAYS")

    if bull_count >= 2 and bull_count > bear_count:
        overall_regime = "BULL MARKET"
    elif bear_count >= 2 and bear_count > bull_count:
        overall_regime = "BEAR MARKET"
    else:
        overall_regime = "SIDEWAYS / MIXED"

    summary_parts = []
    for sym, idx in indices.items():
        summary_parts.append(
            f"{idx['name']}: {idx['price']} ({idx['change_pct']:+.2f}%), "
            f"5d {idx.get('return_5d_pct', 'N/A')}%, 20d {idx.get('return_20d_pct', 'N/A')}%, "
            f"regime={idx['regime']}"
        )
    summary = f"Overall regime: {overall_regime}. " + " | ".join(summary_parts)

    macro = {
        "indices": indices,
        "primary_regime": primary_regime,
        "overall_regime": overall_regime,
        "bull_count": bull_count,
        "bear_count": bear_count,
        "sideways_count": sideways_count,
        "summary": summary,
    }

    logger.info("Macro env: overall=%s, bull=%d, bear=%d, sideways=%d",
                overall_regime, bull_count, bear_count, sideways_count)

    return {
        "macro_env": macro,
        "reasoning_chain": [{
            "agent": "macro_env",
            "overall_regime": overall_regime,
            "primary_regime": primary_regime,
            "index_count": len(indices),
            "summary": summary[:300],
            "exchange": exchange,
        }],
    }
