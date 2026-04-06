"""Risk & Compliance agent: risk assessment, disclaimer injection."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import RiskOutput

logger = logging.getLogger(__name__)


def risk_node(state: dict) -> dict:
    """F-13, F-15: Risk assessment with compliance disclaimer."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    fundamental = state.get("fundamental", {})

    system_prompt = (
        f"You are a financial risk assessment expert. Evaluate the investment risk for {ticker} "
        f"based on all available data.\n\n"
        f"Consider: market risk (volatility, beta), industry risk, company-specific risk "
        f"(litigation, regulatory, key-person), and liquidity risk.\n"
        f"Risk score: 1 (lowest risk) to 10 (highest risk).\n"
        f"Risk level: low (1-3), medium (4-6), high (7-8), critical (9-10)."
    )

    data_summary = (
        f"Analyze risk for {ticker}:\n"
        f"\n--- Market Data ---\n"
        f"Price: ${market_data.get('current_price', 'N/A')}\n"
        f"P/E: {market_data.get('pe_ratio', 'N/A')}\n"
        f"RSI: {market_data.get('rsi_14', 'N/A')}\n"
        f"Technical signals: {market_data.get('technical_signals', [])}\n"
        f"\n--- Sentiment ---\n"
        f"Score: {sentiment.get('overall_score', 'N/A')}\n"
        f"Label: {sentiment.get('overall_label', 'N/A')}\n"
        f"Key factors: {sentiment.get('key_factors', [])}\n"
        f"\n--- Fundamentals ---\n"
        f"Health score: {fundamental.get('health_score', 'N/A')}\n"
        f"Red flags: {fundamental.get('red_flags', [])}\n"
    )

    result = call_llm_structured(
        user_prompt=data_summary,
        response_model=RiskOutput,
        system_prompt=system_prompt,
    )

    logger.info("Risk for %s: score=%.1f, level=%s", ticker, result.risk_score, result.risk_level)

    return {
        "risk": result.model_dump(),
        "reasoning_chain": [{
            "agent": "risk",
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "risk_factors": result.risk_factors,
            "summary": result.summary,
        }],
    }
