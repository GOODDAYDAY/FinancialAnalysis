"""
Quant Agent node: pure algorithmic quantitative analysis, no LLM.

Computes technical signals and a composite score used as
"data referee" evidence in the Bull vs Bear debate.
"""

import logging
from backend.agents.quant.signals import (
    compute_ma_signals,
    compute_rsi_signals,
    compute_macd_signals,
    compute_range_signals,
    compute_pe_signals,
)

logger = logging.getLogger(__name__)


def quant_node(state: dict) -> dict:
    """Pure algorithmic quantitative analysis. No LLM call."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})

    if not market_data or not market_data.get("current_price"):
        return {
            "quant": {"score": 0, "signals": [], "summary": "Insufficient data for quant analysis."},
            "reasoning_chain": [{"agent": "quant", "note": "no market data"}],
        }

    logger.info("Running quant analysis for %s", ticker)

    price = market_data.get("current_price", 0)

    # Gather all signals from sub-modules
    signals = []
    signals.extend(compute_ma_signals(
        price, market_data.get("sma_20"), market_data.get("sma_50"), market_data.get("sma_200")))
    signals.extend(compute_rsi_signals(market_data.get("rsi_14")))
    signals.extend(compute_macd_signals(market_data.get("macd"), market_data.get("macd_signal")))
    signals.extend(compute_range_signals(
        price, market_data.get("fifty_two_week_high"), market_data.get("fifty_two_week_low")))
    signals.extend(compute_pe_signals(market_data.get("pe_ratio")))

    # Compute composite score
    score = sum(s["weight"] for s in signals)
    score = max(-100, min(100, score))

    # Classify verdict
    if score >= 30:
        verdict = "STRONG BUY SIGNAL"
    elif score >= 10:
        verdict = "MODERATE BUY SIGNAL"
    elif score > -10:
        verdict = "NEUTRAL - NO CLEAR SIGNAL"
    elif score > -30:
        verdict = "MODERATE SELL SIGNAL"
    else:
        verdict = "STRONG SELL SIGNAL"

    bullish = [s for s in signals if s["type"] == "bullish"]
    bearish = [s for s in signals if s["type"] == "bearish"]

    summary = (
        f"Quant Score: {score}/100 ({verdict}). "
        f"{len(bullish)} bullish signals, {len(bearish)} bearish signals. "
        f"Strongest bullish: {bullish[0]['name'] if bullish else 'none'}. "
        f"Strongest bearish: {bearish[0]['name'] if bearish else 'none'}."
    )

    quant_result = {
        "score": score,
        "verdict": verdict,
        "signals": signals,
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "summary": summary,
    }

    logger.info("Quant for %s: score=%d, verdict=%s", ticker, score, verdict)

    return {
        "quant": quant_result,
        "reasoning_chain": [{
            "agent": "quant",
            "score": score,
            "verdict": verdict,
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "summary": summary,
        }],
    }
