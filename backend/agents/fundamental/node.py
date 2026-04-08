"""Fundamental Analysis agent node: financial ratios, peer comparison, red flags."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import FundamentalOutput
from backend.utils.language import language_directive
from backend.agents.fundamental.valuation_calc import compute_valuation_summary

logger = logging.getLogger(__name__)


def fundamental_node(state: dict) -> dict:
    """F-11, F-12: Financial ratio analysis with peer comparison."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})
    language = state.get("language", "en")

    if not market_data:
        default = FundamentalOutput(summary="Insufficient data for fundamental analysis.")
        return {
            "fundamental": default.model_dump(),
            "reasoning_chain": [{"agent": "fundamental", "note": "no market data available"}],
        }

    pe = market_data.get("pe_ratio", "N/A")
    cap = market_data.get("market_cap", "N/A")
    price = market_data.get("current_price", "N/A")
    high52 = market_data.get("fifty_two_week_high", "N/A")
    low52 = market_data.get("fifty_two_week_low", "N/A")

    # Algorithmic valuation anchors — gives the LLM numeric ground truth
    valuation = compute_valuation_summary(market_data)

    system_prompt = (
        f"You are a financial analyst expert. Analyze the fundamental data for {ticker} "
        f"and provide a comprehensive assessment.\n\n"
        f"Consider: P/E ratio relative to sector, market capitalization, "
        f"price relative to 52-week range, and any red flags.\n"
        f"Compare with typical sector peers if applicable.\n"
        f"Health score: 1 (very unhealthy) to 10 (excellent health)."
    ) + language_directive(language)

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
        f"\n--- Algorithmic Valuation Anchors ---\n"
        f"- PEG ratio: {valuation['peg_ratio']}\n"
        f"- DCF intrinsic value / share: {valuation['dcf_value_per_share']}\n"
        f"- Margin of safety vs DCF: {valuation['margin_of_safety_pct']}%\n"
        f"- Earnings yield: {valuation['earnings_yield_pct']}%\n"
        f"- Model verdicts: {valuation['verdicts']}\n"
        f"(Assumptions: {valuation['assumptions']})\n"
    )

    result = call_llm_structured(
        user_prompt=user_prompt,
        response_model=FundamentalOutput,
        system_prompt=system_prompt,
    )

    logger.info("Fundamental for %s: health=%.1f", ticker, result.health_score)

    fundamental_out = result.model_dump()
    fundamental_out["valuation"] = valuation

    return {
        "fundamental": fundamental_out,
        "reasoning_chain": [{
            "agent": "fundamental",
            "health_score": result.health_score,
            "red_flags": result.red_flags,
            "valuation_anchors": valuation,
            "summary": result.summary,
        }],
    }
