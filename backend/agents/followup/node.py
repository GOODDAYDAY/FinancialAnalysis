"""
Follow-up Agent: answers questions about a previous analysis
with full context from all agents preserved.

Not a LangGraph node — called directly when the orchestrator
detects a follow-up question and prior analysis exists.
"""

import logging
from backend.llm_client import call_llm

logger = logging.getLogger(__name__)


def handle_followup(question: str, prior_state: dict) -> str:
    """
    Answer a follow-up question using the full context from
    a prior analysis run. All agent outputs are available.

    Args:
        question: The user's follow-up question
        prior_state: The complete state dict from the previous analysis

    Returns:
        A natural language answer string
    """
    ticker = prior_state.get("ticker", "unknown")
    logger.info("Follow-up question for %s: %s", ticker, question[:100])

    # Build comprehensive context from all agent outputs
    context = _build_full_context(prior_state)

    system_prompt = (
        f"You are a financial research assistant. The user previously analyzed {ticker} "
        f"and now has a follow-up question.\n\n"
        f"You have access to the COMPLETE analysis results from all agents:\n"
        f"- Market data (price, technicals, indicators)\n"
        f"- News articles\n"
        f"- Company announcements and financial reports\n"
        f"- Social sentiment from Chinese retail investors\n"
        f"- AI sentiment analysis\n"
        f"- Fundamental analysis (health score, red flags)\n"
        f"- Quant signals (algorithmic scoring)\n"
        f"- Bull vs Bear debate transcript (2 rounds)\n"
        f"- Risk assessment\n"
        f"- Final recommendation\n\n"
        f"Answer the user's question based on the data below. "
        f"Cite specific numbers and agent findings. "
        f"If the question asks about something not covered in the analysis, say so.\n\n"
        f"Always include: 'This is for educational purposes only. Not financial advice.'"
    )

    answer = call_llm(
        user_prompt=f"Question: {question}\n\n{context}",
        system_prompt=system_prompt,
    )

    logger.info("Follow-up answer generated for %s (%d chars)", ticker, len(answer))
    return answer


def _build_full_context(state: dict) -> str:
    """Build a comprehensive text context from all agent outputs."""
    ticker = state.get("ticker", "?")
    md = state.get("market_data", {})
    news = state.get("news_articles", [])
    anns = state.get("announcements", [])
    fin = state.get("financial_summary", {})
    social = state.get("social_sentiment", {})
    sent = state.get("sentiment", {})
    fund = state.get("fundamental", {})
    quant = state.get("quant", {})
    grid = state.get("grid_strategy", {})
    debate = state.get("debate_history", [])
    risk = state.get("risk", {})
    rec = state.get("recommendation", {})

    sections = []

    # Market Data
    sections.append(
        f"=== MARKET DATA ({ticker}) ===\n"
        f"Price: ${md.get('current_price', 'N/A')}\n"
        f"Change: {md.get('price_change_pct', 'N/A')}%\n"
        f"P/E: {md.get('pe_ratio', 'N/A')}\n"
        f"Market Cap: {md.get('market_cap', 'N/A')}\n"
        f"52W High: {md.get('fifty_two_week_high', 'N/A')}\n"
        f"52W Low: {md.get('fifty_two_week_low', 'N/A')}\n"
        f"RSI(14): {md.get('rsi_14', 'N/A')}\n"
        f"SMA20: {md.get('sma_20', 'N/A')}\n"
        f"SMA50: {md.get('sma_50', 'N/A')}\n"
        f"SMA200: {md.get('sma_200', 'N/A')}\n"
        f"MACD: {md.get('macd', 'N/A')}\n"
        f"Technical Signals: {md.get('technical_signals', [])}\n"
        f"Data Source: {md.get('data_source', 'N/A')}"
    )

    # News
    if news:
        news_text = f"=== NEWS ({len(news)} articles) ===\n"
        for i, a in enumerate(news[:5], 1):
            news_text += f"{i}. [{a.get('source', '?')}] {a.get('title', '')}\n   {a.get('summary', '')[:200]}\n"
        sections.append(news_text)

    # Announcements
    if anns:
        ann_text = f"=== COMPANY ANNOUNCEMENTS ({len(anns)} items) ===\n"
        for a in anns[:5]:
            ann_text += f"- [{a.get('date', '')}] {a.get('title', '')}\n"
        sections.append(ann_text)

    # Financial Summary (akshare)
    if fin:
        sections.append(
            f"=== FINANCIAL SUMMARY (akshare) ===\n"
            f"Report Date: {fin.get('report_date', 'N/A')}\n"
            f"Revenue: {fin.get('revenue', 'N/A')}\n"
            f"Net Profit: {fin.get('net_profit', 'N/A')}\n"
            f"ROE: {fin.get('roe', 'N/A')}\n"
            f"Gross Margin: {fin.get('gross_margin', 'N/A')}\n"
            f"Debt Ratio: {fin.get('debt_ratio', 'N/A')}"
        )

    # Social Sentiment
    if social:
        sections.append(
            f"=== SOCIAL SENTIMENT (Eastmoney) ===\n"
            f"Summary: {social.get('summary', 'N/A')}\n"
            f"Is Trending: {social.get('is_trending', 'N/A')}\n"
            f"Trending Rank: {social.get('trending_rank', 'N/A')}"
        )

    # AI Sentiment
    sections.append(
        f"=== SENTIMENT ANALYSIS ===\n"
        f"Score: {sent.get('overall_score', 'N/A')} (-1 to +1)\n"
        f"Label: {sent.get('overall_label', 'N/A')}\n"
        f"Confidence: {sent.get('confidence', 'N/A')}\n"
        f"Reasoning: {sent.get('reasoning', 'N/A')}\n"
        f"Key Factors: {sent.get('key_factors', [])}"
    )

    # Fundamental
    sections.append(
        f"=== FUNDAMENTAL ANALYSIS ===\n"
        f"Health Score: {fund.get('health_score', 'N/A')}/10\n"
        f"Summary: {fund.get('summary', 'N/A')}\n"
        f"Red Flags: {fund.get('red_flags', [])}"
    )

    # Quant
    if quant:
        quant_text = (
            f"=== QUANT ANALYSIS (algorithmic) ===\n"
            f"Score: {quant.get('score', 'N/A')}/100\n"
            f"Verdict: {quant.get('verdict', 'N/A')}\n"
        )
        for sig in quant.get("signals", []):
            icon = "+" if sig["type"] == "bullish" else "-" if sig["type"] == "bearish" else "="
            quant_text += f"  [{icon}] {sig['name']}: {sig['detail']}\n"
        sections.append(quant_text)

    # Grid Strategy
    if grid and grid.get("strategies"):
        grid_text = (
            f"=== GRID TRADING STRATEGY ===\n"
            f"Suitability: {grid.get('score', 'N/A')}/100 ({grid.get('verdict', 'N/A')})\n"
            f"Annual Volatility: {grid.get('annual_volatility_pct', 'N/A')}%\n"
            f"Best Strategy: {grid.get('best_strategy_name', 'none')} "
            f"(estimated {grid.get('best_monthly_return_pct', 0)}%/month)\n"
            f"Suitability Reasons: {grid.get('reasons', [])}\n"
        )
        for s in grid.get("strategies", []):
            grid_text += (
                f"\n  [{s['name']}] ({s['horizon']})\n"
                f"    Range: {s['lower_price']} - {s['upper_price']}, "
                f"{s['grid_count']} grids, step {s['grid_step']} ({s['grid_step_pct']}%)\n"
                f"    {s['shares_per_grid']} shares/grid, "
                f"capital {s['capital_required']} yuan\n"
                f"    Profit/cycle: {s['profit_per_cycle']} yuan ({s['profit_per_cycle_pct']}%) "
                f"after {s['fees_per_cycle']} fees\n"
                f"    Est. {s['estimated_cycles_per_month']} cycles/month, "
                f"~{s['estimated_monthly_return_pct']}%/month\n"
            )
            if s.get("caveats"):
                grid_text += f"    Caveats: {s['caveats']}\n"
        sections.append(grid_text)

    # Debate
    if debate:
        debate_text = f"=== BULL vs BEAR DEBATE ({len(debate)} entries) ===\n"
        for entry in debate:
            role = entry.get("role", "?").upper()
            rnd = entry.get("round_number", "?")
            debate_text += (
                f"\n[Round {rnd} - {role}]\n"
                f"Argument: {entry.get('argument', '')}\n"
                f"Key Points: {entry.get('key_points', [])}\n"
                f"Evidence: {entry.get('evidence', [])}\n"
                f"Rebuttals: {entry.get('rebuttals', [])}\n"
            )
        sections.append(debate_text)

    # Risk
    sections.append(
        f"=== RISK ASSESSMENT ===\n"
        f"Score: {risk.get('risk_score', 'N/A')}/10\n"
        f"Level: {risk.get('risk_level', 'N/A')}\n"
        f"Factors: {risk.get('risk_factors', [])}\n"
        f"Summary: {risk.get('summary', 'N/A')}"
    )

    # Recommendation
    sections.append(
        f"=== FINAL RECOMMENDATION ===\n"
        f"Decision: {rec.get('recommendation', 'N/A')}\n"
        f"Confidence: {rec.get('confidence', 'N/A')}\n"
        f"Horizon: {rec.get('investment_horizon', 'N/A')}\n"
        f"Supporting: {rec.get('supporting_factors', [])}\n"
        f"Dissenting: {rec.get('dissenting_factors', [])}\n"
        f"Debate Summary: {rec.get('debate_summary', 'N/A')}\n"
        f"Reasoning: {rec.get('reasoning', 'N/A')}"
    )

    return "\n\n".join(sections)
