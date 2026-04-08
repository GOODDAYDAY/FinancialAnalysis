"""
Bull vs Bear Debate agent node.

F-16: Structured debate rounds where Bull and Bear analysts argue
using evidence from upstream analysis agents + quant signals.
Implemented as a LangGraph self-loop node with conditional edge.
"""

import logging
from backend.llm_client import call_llm_structured
from backend.state import DebateArgument
from backend.config import settings
from backend.utils.language import language_directive

logger = logging.getLogger(__name__)


def _build_analysis_context(state: dict) -> str:
    """Flatten all analysis results into text for debaters."""
    ticker = state.get("ticker", "???")
    market = state.get("market_data", {})
    sentiment = state.get("sentiment", {})
    fundamental = state.get("fundamental", {})
    quant = state.get("quant", {})
    grid = state.get("grid_strategy", {})
    announcements = state.get("announcements", [])
    social = state.get("social_sentiment", {})
    macro = state.get("macro_env", {})
    sector = state.get("sector", {})
    momentum = state.get("momentum", {})
    judge = state.get("debate_judge", {})

    # Macro environment section (important for contextualizing individual stock calls)
    macro_text = ""
    if macro and macro.get("indices"):
        macro_text = (
            f"\nMACRO ENVIRONMENT (broad Chinese market):\n"
            f"  Overall regime: {macro.get('overall_regime', 'UNKNOWN')}\n"
            f"  Primary benchmark (CSI 300) regime: {macro.get('primary_regime', 'UNKNOWN')}\n"
        )
        for sym, idx in list(macro.get("indices", {}).items())[:5]:
            macro_text += (
                f"  - {idx.get('name')}: {idx.get('price')} "
                f"({idx.get('change_pct', 0):+.2f}% today, "
                f"5d={idx.get('return_5d_pct', 'N/A')}%, "
                f"20d={idx.get('return_20d_pct', 'N/A')}%, "
                f"regime={idx.get('regime', 'UNKNOWN')})\n"
            )

    # Sector / industry section
    sector_text = ""
    if sector:
        sector_text = "\nSECTOR / INDUSTRY CONTEXT:\n"
        stock_row = sector.get("stock_sector_row")
        if stock_row:
            sector_text += (
                f"  This stock's sector: {stock_row.get('name')} "
                f"(rank #{stock_row.get('rank')}, "
                f"today {stock_row.get('change_pct', 0):+.2f}%, "
                f"advance/decline {stock_row.get('advance', 0)}/{stock_row.get('decline', 0)})\n"
            )
        elif sector.get("stock_industry", {}).get("industry_name"):
            sector_text += f"  This stock's industry: {sector['stock_industry']['industry_name']}\n"
        if sector.get("top_sectors"):
            sector_text += "  Hot sectors today: " + ", ".join(
                f"{s['name']}({s['change_pct']:+.2f}%)" for s in sector["top_sectors"][:5]
            ) + "\n"
        if sector.get("top_concepts"):
            sector_text += "  Hot concepts: " + ", ".join(
                f"{c['name']}({c['change_pct']:+.2f}%)" for c in sector["top_concepts"][:5]
            ) + "\n"

    # Momentum section — important for avoiding 'sell on rising stock'
    momentum_text = ""
    if momentum and momentum.get("score") is not None:
        mrt = momentum.get("returns", {}) or {}
        momentum_text = (
            f"\nMOMENTUM ANALYSIS (algorithmic, short/medium-term):\n"
            f"  Momentum Score: {momentum.get('score', 0)}/100 ({momentum.get('regime', 'N/A')})\n"
            f"  Recent returns: 3d={mrt.get('3d')}, 5d={mrt.get('5d')}, "
            f"10d={mrt.get('10d')}, 20d={mrt.get('20d')}, 60d={mrt.get('60d')}\n"
            f"  20-day range position: {momentum.get('range_position_pct', 'N/A')}%\n"
            f"  20-day breakout: {momentum.get('breakout_20', False)}\n"
            f"  Volume surge ratio: {momentum.get('volume_surge_ratio', 'N/A')}\n"
            f"  Trend consistency: {momentum.get('trend_consistency_pct', 'N/A')}% up days\n"
            f"  Relative strength vs CSI 300 (20d): {momentum.get('relative_strength_vs_csi300_20d', 'N/A')}%\n"
        )
        for sig in momentum.get("signals", [])[:6]:
            icon = "+" if sig["type"] == "bullish" else "-" if sig["type"] == "bearish" else "="
            momentum_text += f"  [{icon}] {sig['name']}: {sig['detail']}\n"

    # Quant section
    quant_text = ""
    if quant and quant.get("score") is not None:
        quant_text = (
            f"\nQUANT ANALYSIS (algorithmic, long-term trend):\n"
            f"  Quant Score: {quant.get('score', 0)}/100 ({quant.get('verdict', 'N/A')})\n"
            f"  Bullish Signals: {quant.get('bullish_count', 0)}\n"
            f"  Bearish Signals: {quant.get('bearish_count', 0)}\n"
        )
        for sig in quant.get("signals", []):
            icon = "+" if sig["type"] == "bullish" else "-" if sig["type"] == "bearish" else "="
            quant_text += f"  [{icon}] {sig['name']}: {sig['detail']} (weight: {sig['weight']})\n"

    # Grid strategy section
    grid_text = ""
    if grid and grid.get("score") is not None:
        grid_text = (
            f"\nGRID STRATEGY ANALYSIS:\n"
            f"  Suitability: {grid.get('score', 0)}/100 ({grid.get('verdict', 'N/A')})\n"
            f"  Annual Volatility: {grid.get('annual_volatility_pct', 0)}%\n"
            f"  Best Strategy: {grid.get('best_strategy_name', 'none')}\n"
            f"  Best Monthly Return: {grid.get('best_monthly_return_pct', 0)}%\n"
        )

    # Judge feedback from prior round (if any)
    judge_text = ""
    if judge and judge.get("verdict") == "continue":
        judge_text = (
            f"\n=== JUDGE FEEDBACK FROM PREVIOUS ROUND ===\n"
            f"  Previous round quality: {judge.get('quality_score', 'N/A')}/100\n"
            f"  Judge's reason for requesting another round: {judge.get('reason', 'N/A')}\n"
            f"  Unresolved points you MUST address in this round:\n"
        )
        for pt in judge.get("unresolved_points", []):
            judge_text += f"    - {pt}\n"

    return (
        f"=== Analysis Data for {ticker} ===\n"
        f"{macro_text}"
        f"{sector_text}"
        f"\nMARKET DATA:\n"
        f"  Price: ${market.get('current_price', 'N/A')}\n"
        f"  Change today: {market.get('price_change_pct', 'N/A')}%\n"
        f"  P/E Ratio: {market.get('pe_ratio', 'N/A')}\n"
        f"  RSI(14): {market.get('rsi_14', 'N/A')}\n"
        f"  Technical Signals: {market.get('technical_signals', [])}\n"
        f"{momentum_text}"
        f"\nSENTIMENT (news-based):\n"
        f"  Overall Score: {sentiment.get('overall_score', 'N/A')} (-1 bearish to +1 bullish)\n"
        f"  Label: {sentiment.get('overall_label', 'N/A')}\n"
        f"  Key Factors: {sentiment.get('key_factors', [])}\n"
        f"  Reasoning: {sentiment.get('reasoning', 'N/A')}\n"
        f"\nFUNDAMENTALS:\n"
        f"  Health Score: {fundamental.get('health_score', 'N/A')}/10\n"
        f"  Red Flags: {fundamental.get('red_flags', [])}\n"
        f"  Summary: {fundamental.get('summary', 'N/A')}\n"
        f"{quant_text}"
        f"{grid_text}"
        f"\nCOMPANY ANNOUNCEMENTS ({len(announcements)} items):\n"
        + ("".join(f"  - [{a.get('date','')}] {a.get('title','')[:80]}\n" for a in announcements[:5]) if announcements else "  No announcements available.\n")
        + f"\nSOCIAL SENTIMENT (Eastmoney):\n"
        f"  Summary: {social.get('summary', 'No social data')}\n"
        f"  Is Trending: {social.get('is_trending', 'N/A')}\n"
        f"  Trending Rank: {social.get('trending_rank', 'N/A')}\n"
        f"{judge_text}"
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
    language = state.get("language", "en")
    lang_dir = language_directive(language)

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

    # Bull argues
    bull_system = (
        f"You are a BULLISH investment analyst (the Bull). Your job is to make the STRONGEST "
        f"possible case for BUYING {ticker}.\n\n"
        f"Rules:\n"
        f"- Cite SPECIFIC data points from the analysis (prices, ratios, scores, quant signals)\n"
        f"- Acknowledge weaknesses but explain why they are manageable\n"
        f"- In round 2+, directly address the Bear's previous arguments\n"
        f"- Provide exactly 3 key points and supporting evidence"
    ) + lang_dir

    bull_result = call_llm_structured(
        user_prompt=f"Round {current_round}: Present your BULLISH case for {ticker}.\n\n{analysis_context}\n{prior_text}",
        response_model=DebateArgument,
        system_prompt=bull_system,
        temperature=settings.debate_temperature,
    )
    bull_result.role = "bull"
    bull_result.round_number = current_round

    # Bear argues (sees Bull's argument)
    bear_system = (
        f"You are a BEARISH investment analyst (the Bear). Your job is to make the STRONGEST "
        f"possible case for NOT buying (or SELLING) {ticker}.\n\n"
        f"Rules:\n"
        f"- Cite SPECIFIC data points from the analysis and quant signals\n"
        f"- Directly challenge the Bull's arguments with counter-evidence\n"
        f"- Highlight risks, red flags, and uncertainties\n"
        f"- Provide exactly 3 key points, evidence, and rebuttals to the Bull"
    ) + lang_dir

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


# NOTE: The fixed-rounds `should_continue_debate` has been replaced by
# debate_judge_node + should_continue_debate_with_judge in the debate_judge
# agent. The graph now routes debate -> debate_judge -> (debate|risk).
