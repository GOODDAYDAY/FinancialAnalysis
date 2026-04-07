"""Advisory agent node: synthesize all analysis + debate into recommendation."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import RecommendationOutput
from backend.utils.language import language_directive

logger = logging.getLogger(__name__)


def advisory_node(state: dict) -> dict:
    """F-17, F-18: Synthesize recommendation with reasoning chain."""
    ticker = state.get("ticker", "???")
    market_data = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    fundamental = state.get("fundamental", {})
    quant = state.get("quant", {})
    grid = state.get("grid_strategy", {})
    risk = state.get("risk", {})
    debate_history = state.get("debate_history", [])
    language = state.get("language", "en")

    # Build debate summary
    debate_text = ""
    if debate_history:
        debate_text = "\n=== BULL vs BEAR DEBATE ===\n"
        for entry in debate_history:
            role = entry.get("role", "unknown").upper()
            rnd = entry.get("round_number", "?")
            debate_text += (
                f"\n[Round {rnd} - {role}]\n"
                f"Argument: {entry.get('argument', 'N/A')}\n"
                f"Key Points: {entry.get('key_points', [])}\n"
                f"Evidence: {entry.get('evidence', [])}\n"
                f"Rebuttals: {entry.get('rebuttals', [])}\n"
            )

    system_prompt = (
        f"You are a senior investment advisor synthesizing all analysis for {ticker}.\n\n"
        f"You have access to: market data, sentiment analysis, fundamental analysis, "
        f"quant signals (algorithmic, unbiased), risk assessment, and a structured Bull vs Bear debate.\n\n"
        f"Weight the dimensions:\n"
        f"- Fundamental analysis: 30%\n"
        f"- Quant signals: 25%\n"
        f"- Sentiment analysis: 20%\n"
        f"- Risk assessment: 15%\n"
        f"- Technical indicators: 10%\n\n"
        f"Consider the debate outcome: which side made stronger arguments? "
        f"What points were conceded vs contested?\n\n"
        f"Provide a clear recommendation (buy/hold/sell), confidence level (0-1), "
        f"and investment horizon (short-term/medium-term/long-term)."
    ) + language_directive(language)

    user_prompt = (
        f"Generate investment recommendation for {ticker}:\n\n"
        f"--- MARKET DATA ---\n"
        f"Price: ${market_data.get('current_price', 'N/A')}\n"
        f"P/E: {market_data.get('pe_ratio', 'N/A')}\n"
        f"RSI: {market_data.get('rsi_14', 'N/A')}\n"
        f"Signals: {market_data.get('technical_signals', [])}\n\n"
        f"--- SENTIMENT ---\n"
        f"Score: {sentiment.get('overall_score', 'N/A')}\n"
        f"Label: {sentiment.get('overall_label', 'N/A')}\n"
        f"Reasoning: {sentiment.get('reasoning', 'N/A')}\n\n"
        f"--- FUNDAMENTALS ---\n"
        f"Health: {fundamental.get('health_score', 'N/A')}/10\n"
        f"Red Flags: {fundamental.get('red_flags', [])}\n"
        f"Summary: {fundamental.get('summary', 'N/A')}\n\n"
        f"--- QUANT ANALYSIS (algorithmic, no AI bias) ---\n"
        f"Quant Score: {quant.get('score', 'N/A')}/100\n"
        f"Verdict: {quant.get('verdict', 'N/A')}\n"
        f"Signals: {[s['name'] + '(' + s['type'] + ')' for s in quant.get('signals', [])]}\n\n"
        f"--- GRID STRATEGY (algorithmic) ---\n"
        f"Suitability: {grid.get('score', 'N/A')}/100 ({grid.get('verdict', 'N/A')})\n"
        f"Annual Volatility: {grid.get('annual_volatility_pct', 'N/A')}%\n"
        f"Best Strategy: {grid.get('best_strategy_name', 'none')}\n"
        f"Best Monthly Return Estimate: {grid.get('best_monthly_return_pct', 0)}%\n\n"
        f"--- RISK ---\n"
        f"Risk Score: {risk.get('risk_score', 'N/A')}/10\n"
        f"Level: {risk.get('risk_level', 'N/A')}\n"
        f"Factors: {risk.get('risk_factors', [])}\n"
        f"{debate_text}"
    )

    result = call_llm_structured(
        user_prompt=user_prompt,
        response_model=RecommendationOutput,
        system_prompt=system_prompt,
    )

    logger.info(
        "Advisory for %s: %s (confidence=%.2f)",
        ticker, result.recommendation, result.confidence,
    )

    return {
        "recommendation": result.model_dump(),
        "reasoning_chain": [{
            "agent": "advisory",
            "recommendation": result.recommendation,
            "confidence": result.confidence,
            "horizon": result.investment_horizon,
            "supporting": result.supporting_factors,
            "dissenting": result.dissenting_factors,
            "debate_summary": result.debate_summary,
        }],
    }
