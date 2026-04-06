"""
Bull vs Bear Debate agent: multi-agent debate mechanism.

F-16: Structured debate rounds where Bull and Bear analysts argue
using evidence from upstream analysis agents.

Implemented as a LangGraph self-loop node with conditional edge.
"""

import logging
from backend.llm_client import call_llm_structured
from backend.state import DebateArgument
from backend.config import settings

logger = logging.getLogger(__name__)


def _build_analysis_context(state: dict) -> str:
    """Flatten all analysis results into text for debaters."""
    ticker = state.get("ticker", "???")
    market = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    fundamental = state.get("fundamental", {})

    return (
        f"=== Analysis Data for {ticker} ===\n\n"
        f"MARKET DATA:\n"
        f"  Price: ${market.get('current_price', 'N/A')}\n"
        f"  Change: {market.get('price_change_pct', 'N/A')}%\n"
        f"  P/E Ratio: {market.get('pe_ratio', 'N/A')}\n"
        f"  RSI(14): {market.get('rsi_14', 'N/A')}\n"
        f"  Technical Signals: {market.get('technical_signals', [])}\n\n"
        f"SENTIMENT:\n"
        f"  Overall Score: {sentiment.get('overall_score', 'N/A')} (-1 bearish to +1 bullish)\n"
        f"  Label: {sentiment.get('overall_label', 'N/A')}\n"
        f"  Key Factors: {sentiment.get('key_factors', [])}\n"
        f"  Reasoning: {sentiment.get('reasoning', 'N/A')}\n\n"
        f"FUNDAMENTALS:\n"
        f"  Health Score: {fundamental.get('health_score', 'N/A')}/10\n"
        f"  Red Flags: {fundamental.get('red_flags', [])}\n"
        f"  Summary: {fundamental.get('summary', 'N/A')}\n"
    )


def debate_node(state: dict) -> dict:
    """
    One round of Bull vs Bear debate.

    Bull argues first, then Bear sees Bull's argument and rebuts.
    This node self-loops via conditional edge for multiple rounds.
    """
    ticker = state.get("ticker", "???")
    current_round = state.get("debate_round", 0) + 1
    prior_debate = state.get("debate_history", [])
    analysis_context = _build_analysis_context(state)

    logger.info("Debate Round %d for %s", current_round, ticker)

    # Build prior debate context
    prior_text = ""
    if prior_debate:
        prior_text = "\n\n=== PRIOR DEBATE ROUNDS ===\n"
        for entry in prior_debate:
            prior_text += (
                f"\n[Round {entry.get('round_number', '?')} - {entry.get('role', '?').upper()}]\n"
                f"Argument: {entry.get('argument', '')}\n"
                f"Key Points: {entry.get('key_points', [])}\n"
            )

    # ── BULL ARGUES ──
    bull_system = (
        f"You are a BULLISH investment analyst (the Bull). Your job is to make the STRONGEST "
        f"possible case for BUYING {ticker}.\n\n"
        f"Rules:\n"
        f"- Cite SPECIFIC data points from the analysis (prices, ratios, scores)\n"
        f"- Acknowledge weaknesses but explain why they are manageable\n"
        f"- Be persuasive but honest — do not fabricate data\n"
        f"- In round 2+, directly address the Bear's previous arguments\n"
        f"- Provide exactly 3 key points and supporting evidence"
    )

    bull_prompt = (
        f"Round {current_round}: Present your BULLISH case for {ticker}.\n\n"
        f"{analysis_context}\n{prior_text}"
    )

    bull_result = call_llm_structured(
        user_prompt=bull_prompt,
        response_model=DebateArgument,
        system_prompt=bull_system,
        temperature=settings.debate_temperature,
    )
    bull_result.role = "bull"
    bull_result.round_number = current_round

    # ── BEAR ARGUES (seeing Bull's argument) ──
    bear_system = (
        f"You are a BEARISH investment analyst (the Bear). Your job is to make the STRONGEST "
        f"possible case for NOT buying (or SELLING) {ticker}.\n\n"
        f"Rules:\n"
        f"- Cite SPECIFIC data points from the analysis\n"
        f"- Directly challenge the Bull's arguments with counter-evidence\n"
        f"- Highlight risks, red flags, and uncertainties\n"
        f"- Be persuasive but honest — do not fabricate data\n"
        f"- Provide exactly 3 key points, evidence, and rebuttals to the Bull"
    )

    bear_prompt = (
        f"Round {current_round}: Present your BEARISH case for {ticker}.\n\n"
        f"{analysis_context}\n{prior_text}\n\n"
        f"The Bull just argued:\n"
        f"Argument: {bull_result.argument}\n"
        f"Key Points: {bull_result.key_points}\n"
        f"Evidence: {bull_result.evidence}\n\n"
        f"Counter the Bull's arguments with your bearish case."
    )

    bear_result = call_llm_structured(
        user_prompt=bear_prompt,
        response_model=DebateArgument,
        system_prompt=bear_system,
        temperature=settings.debate_temperature,
    )
    bear_result.role = "bear"
    bear_result.round_number = current_round

    logger.info(
        "Debate R%d complete: Bull=%d points, Bear=%d points",
        current_round, len(bull_result.key_points), len(bear_result.key_points),
    )

    return {
        "debate_history": [bull_result.model_dump(), bear_result.model_dump()],
        "debate_round": current_round,
        "reasoning_chain": [{
            "agent": f"debate_round_{current_round}",
            "bull_argument": bull_result.argument[:200],
            "bear_argument": bear_result.argument[:200],
        }],
    }


def should_continue_debate(state: dict) -> str:
    """Conditional edge: continue debate or move to advisory."""
    current_round = state.get("debate_round", 0)
    max_rounds = settings.debate_max_rounds

    if current_round < max_rounds:
        logger.info("Debate continues: round %d/%d", current_round, max_rounds)
        return "debate"

    logger.info("Debate finished after %d rounds", current_round)
    return "risk"
