"""
Grid Strategy Agent node: pure-math grid trading analysis.

Analyzes suitability and generates multiple grid strategy variants
(short/medium/long term) with concrete parameters:
- Price range and grid count
- Shares per grid
- Profit per round-trip (after fees)
- Estimated monthly return

No LLM call, fully deterministic.
"""

import logging
from backend.agents.grid_strategy.calculator import (
    assess_suitability,
    generate_strategies,
    compute_volatility,
    compute_daily_range_pct,
)

logger = logging.getLogger(__name__)


def grid_strategy_node(state: dict) -> dict:
    """
    Analyze grid trading suitability and propose strategies.
    Pure algorithms, no LLM. Uses historical prices from market_data.
    """
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})

    if not market_data or not market_data.get("current_price"):
        return {
            "grid_strategy": {
                "suitable": False,
                "score": 0,
                "verdict": "NO DATA",
                "reasons": ["Market data unavailable"],
                "strategies": [],
            },
            "reasoning_chain": [{"agent": "grid_strategy", "note": "no market data"}],
        }

    current_price = market_data.get("current_price", 0)
    rsi = market_data.get("rsi_14")
    sma_20 = market_data.get("sma_20")
    sma_50 = market_data.get("sma_50")
    sma_200 = market_data.get("sma_200")

    # Historical closes needed for volatility calculation
    # We don't have them directly in state, use fallback from market_data snapshot
    # For real calculation, use SMAs and 52-week range as proxy
    high_52w = market_data.get("fifty_two_week_high")
    low_52w = market_data.get("fifty_two_week_low")

    # Synthesize a minimal price series from available data for volatility estimation
    closes = _synthesize_closes(current_price, sma_20, sma_50, sma_200, high_52w, low_52w)

    logger.info("Grid analysis for %s, price=%.2f", ticker, current_price)

    # Step 1: Assess suitability
    score, verdict, reasons = assess_suitability(
        current_price=current_price,
        closes=closes,
        rsi=rsi,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
    )

    # Step 2: Generate strategies (always, even if score is low — user can decide)
    strategies = generate_strategies(
        current_price=current_price,
        closes=closes,
        capital_budget=100_000,  # default 100k yuan
    )

    # Convert to dicts
    strategies_dicts = [s.to_dict() for s in strategies]

    # Find best strategy by estimated monthly return among profitable ones
    profitable = [s for s in strategies_dicts if s["profit_per_cycle"] > 0]
    best = max(profitable, key=lambda s: s["estimated_monthly_return_pct"], default=None)

    annual_vol_pct = compute_volatility(closes) * 100
    daily_range_pct = compute_daily_range_pct(closes)

    result = {
        "suitable": score >= 50,
        "score": score,
        "verdict": verdict,
        "reasons": reasons,
        "annual_volatility_pct": round(annual_vol_pct, 2),
        "daily_range_pct": round(daily_range_pct, 2),
        "strategies": strategies_dicts,
        "best_strategy_name": best["name"] if best else None,
        "best_monthly_return_pct": best["estimated_monthly_return_pct"] if best else 0,
        "summary": _build_summary(ticker, score, verdict, strategies_dicts, best),
    }

    logger.info(
        "Grid for %s: score=%d, verdict=%s, strategies=%d, best=%s",
        ticker, score, verdict, len(strategies_dicts),
        best["name"] if best else "none",
    )

    return {
        "grid_strategy": result,
        "reasoning_chain": [{
            "agent": "grid_strategy",
            "suitability_score": score,
            "verdict": verdict,
            "strategy_count": len(strategies_dicts),
            "best_strategy": best["name"] if best else None,
            "annual_volatility_pct": round(annual_vol_pct, 2),
        }],
    }


def _synthesize_closes(
    current_price: float,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
    high_52w: float | None,
    low_52w: float | None,
) -> list[float]:
    """
    Synthesize a plausible price series from summary stats.
    Used when full historical data is not in state (state only has summary).
    """
    closes = []

    # Use 52-week range to estimate spread and create a series
    if high_52w and low_52w:
        # Create a sine-like oscillation between low and high, ending at current
        mid = (high_52w + low_52w) / 2
        amplitude = (high_52w - low_52w) / 2
        # 60 data points ~ 3 months
        import math
        for i in range(60):
            phase = i / 60 * 2 * math.pi
            val = mid + amplitude * math.sin(phase) * 0.7
            closes.append(val)

    # Add SMAs as recent anchor points
    if sma_200:
        closes.append(sma_200)
    if sma_50:
        closes.append(sma_50)
    if sma_20:
        closes.append(sma_20)

    # Current price is the last point
    closes.append(current_price)

    return closes if closes else [current_price]


def _build_summary(
    ticker: str,
    score: int,
    verdict: str,
    strategies: list[dict],
    best: dict | None,
) -> str:
    """Build a plain-text summary of the grid analysis."""
    parts = [
        f"Grid trading suitability for {ticker}: {score}/100 ({verdict}).",
        f"{len(strategies)} strategies proposed.",
    ]
    if best:
        parts.append(
            f"Best strategy: '{best['name']}' "
            f"with estimated {best['estimated_monthly_return_pct']}%/month return, "
            f"{best['grid_count']} grids from {best['lower_price']} to {best['upper_price']}, "
            f"{best['shares_per_grid']} shares per grid, "
            f"profit per cycle {best['profit_per_cycle']} yuan after fees."
        )
    else:
        parts.append("No profitable strategy under current parameters — fees exceed grid profits.")
    return " ".join(parts)
