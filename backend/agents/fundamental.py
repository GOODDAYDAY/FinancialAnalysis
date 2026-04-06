"""Fundamental Analysis agent: financial ratios, peer comparison, red flags."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import FundamentalOutput

logger = logging.getLogger(__name__)


def fundamental_node(state: dict) -> dict:
    """F-11, F-12: Financial ratio analysis with peer comparison."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})

    if not market_data:
        default = FundamentalOutput(
            health_score=5.0,
            summary="Insufficient data for fundamental analysis.",
        )
        return {
            "fundamental": default.model_dump(),
            "reasoning_chain": [{"agent": "fundamental", "note": "no market data available"}],
        }

    # Extract key metrics for the prompt
    pe = market_data.get("pe_ratio", "N/A")
    cap = market_data.get("market_cap", "N/A")
    price = market_data.get("current_price", "N/A")
    high52 = market_data.get("fifty_two_week_high", "N/A")
    low52 = market_data.get("fifty_two_week_low", "N/A")

    system_prompt = (
        f"You are a financial analyst expert. Analyze the fundamental data for {ticker} "
        f"and provide a comprehensive assessment.\n\n"
        f"Consider: P/E ratio relative to sector, market capitalization, "
        f"price relative to 52-week range, and any red flags.\n"
        f"Compare with typical tech sector peers if applicable.\n"
        f"Health score: 1 (very unhealthy) to 10 (excellent health)."
    )

    user_prompt = (
        f"Analyze fundamentals for {ticker}:\n"
        f"- Current Price: ${price}\n"
        f"- P/E Ratio: {pe}\n"
        f"- Market Cap: {cap}\n"
        f"- 52-Week High: ${high52}\n"
        f"- 52-Week Low: ${low52}\n"
        f"- SMA20: {market_data.get('sma_20', 'N/A')}\n"
        f"- SMA50: {market_data.get('sma_50', 'N/A')}\n"
        f"- RSI14: {market_data.get('rsi_14', 'N/A')}\n"
    )

    result = call_llm_structured(
        user_prompt=user_prompt,
        response_model=FundamentalOutput,
        system_prompt=system_prompt,
    )

    logger.info("Fundamental for %s: health=%.1f", ticker, result.health_score)

    return {
        "fundamental": result.model_dump(),
        "reasoning_chain": [{
            "agent": "fundamental",
            "health_score": result.health_score,
            "red_flags": result.red_flags,
            "summary": result.summary,
        }],
    }
