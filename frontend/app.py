"""
Streamlit UI for Multi-Agent Investment Research System.

Chat-based interface that invokes the LangGraph pipeline and
displays recommendation, debate transcript, and reasoning chain.
"""

import sys
import os
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.graph import run_analysis  # noqa: E402
from backend.agents.followup import handle_followup  # noqa: E402

st.set_page_config(
    page_title="AI Investment Research",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)


def _render_analysis(result: dict, ticker: str):
    """Render the full analysis result."""
    recommendation = result.get("recommendation", {})
    market_data = result.get("market_data", {})
    sentiment = result.get("sentiment", {})
    fundamental = result.get("fundamental", {})
    quant = result.get("quant", {})
    grid = result.get("grid_strategy", {})
    risk = result.get("risk", {})
    debate_history = result.get("debate_history", [])
    errors = result.get("errors", [])

    # Header
    rec = recommendation.get("recommendation", "N/A").upper()
    confidence = recommendation.get("confidence", 0)
    color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}.get(rec, "gray")
    st.markdown(f"## {ticker} Analysis Result")
    st.markdown(f"### Recommendation: :{color}[**{rec}**] (Confidence: {confidence:.0%})")

    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        price = market_data.get("current_price", "N/A")
        change = market_data.get("price_change_pct", 0)
        st.metric("Price", f"${price}", f"{change:+.2f}%" if isinstance(change, (int, float)) else "N/A")
    with col2:
        st.metric("Sentiment", sentiment.get("overall_label", "N/A"),
                   f"{sentiment.get('overall_score', 0):+.2f}")
    with col3:
        st.metric("Health Score", f"{fundamental.get('health_score', 'N/A')}/10")
    with col4:
        st.metric("Risk Score", f"{risk.get('risk_score', 'N/A')}/10",
                   risk.get("risk_level", "N/A"))

    # Recommendation Details
    with st.expander("Recommendation Details", expanded=True):
        st.write(f"**Investment Horizon:** {recommendation.get('investment_horizon', 'N/A')}")
        st.write(f"**Reasoning:** {recommendation.get('reasoning', 'N/A')}")

        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Supporting Factors:**")
            for f in recommendation.get("supporting_factors", []):
                st.write(f"- {f}")
        with col_b:
            st.write("**Dissenting Factors:**")
            for f in recommendation.get("dissenting_factors", []):
                st.write(f"- {f}")

    # Bull vs Bear Debate
    if debate_history:
        with st.expander("Bull vs Bear Debate", expanded=True):
            for entry in debate_history:
                role = entry.get("role", "unknown")
                rnd = entry.get("round_number", "?")
                icon = "Bull" if role == "bull" else "Bear"
                label = "BULL" if role == "bull" else "BEAR"

                st.markdown(f"**{icon} {label} - Round {rnd}**")
                st.write(entry.get("argument", ""))

                points = entry.get("key_points", [])
                if points:
                    st.write("Key Points:")
                    for p in points:
                        st.write(f"  - {p}")

                rebuttals = entry.get("rebuttals", [])
                if rebuttals:
                    st.write("Rebuttals:")
                    for r in rebuttals:
                        st.write(f"  - {r}")

                st.divider()

            if recommendation.get("debate_summary"):
                st.write(f"**Debate Summary:** {recommendation['debate_summary']}")

    # Technical Indicators
    with st.expander("Technical Indicators"):
        tech_col1, tech_col2 = st.columns(2)
        with tech_col1:
            st.write(f"- SMA(20): {market_data.get('sma_20', 'N/A')}")
            st.write(f"- SMA(50): {market_data.get('sma_50', 'N/A')}")
            st.write(f"- SMA(200): {market_data.get('sma_200', 'N/A')}")
        with tech_col2:
            st.write(f"- RSI(14): {market_data.get('rsi_14', 'N/A')}")
            st.write(f"- MACD: {market_data.get('macd', 'N/A')}")
            st.write(f"- MACD Signal: {market_data.get('macd_signal', 'N/A')}")
        if market_data.get("technical_signals"):
            st.write("**Signals:**")
            for sig in market_data["technical_signals"]:
                st.write(f"  - {sig}")
        if market_data.get("is_mock"):
            st.warning("Using demo data - real-time data unavailable")

    # Quant Analysis
    if quant:
        with st.expander("Quant Analysis (Algorithmic)"):
            qscore = quant.get("score", 0)
            qverdict = quant.get("verdict", "N/A")
            qcolor = "green" if qscore > 10 else "red" if qscore < -10 else "orange"
            st.markdown(f"**Quant Score: :{qcolor}[{qscore}/100]** ({qverdict})")
            st.write(f"Bullish signals: {quant.get('bullish_count', 0)} | Bearish signals: {quant.get('bearish_count', 0)}")
            for sig in quant.get("signals", []):
                icon = "[+]" if sig["type"] == "bullish" else "[-]" if sig["type"] == "bearish" else "[=]"
                st.write(f"  {icon} **{sig['name']}**: {sig['detail']} (weight: {sig['weight']})")

    # Grid Strategy
    if grid and grid.get("strategies"):
        with st.expander("Grid Trading Strategies", expanded=True):
            gscore = grid.get("score", 0)
            gverdict = grid.get("verdict", "N/A")
            gcolor = "green" if gscore >= 70 else "orange" if gscore >= 50 else "red"
            st.markdown(f"**Suitability: :{gcolor}[{gscore}/100]** ({gverdict})")
            st.write(f"Annual Volatility: {grid.get('annual_volatility_pct', 0)}% | "
                      f"Daily Range: {grid.get('daily_range_pct', 0)}%")

            if grid.get("reasons"):
                st.write("**Suitability Analysis:**")
                for r in grid["reasons"]:
                    st.write(f"  - {r}")

            best_name = grid.get("best_strategy_name")
            if best_name:
                st.success(f"**Recommended Strategy:** {best_name} "
                            f"(estimated {grid.get('best_monthly_return_pct', 0)}%/month)")

            st.write("**All Strategy Variants:**")
            for s in grid["strategies"]:
                is_best = s["name"] == best_name
                title = f"{'★ ' if is_best else ''}{s['name']} ({s['horizon']})"
                with st.container():
                    st.markdown(f"#### {title}")
                    st.caption(s.get("description", ""))

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price Range", f"{s['lower_price']} - {s['upper_price']}")
                        st.metric("Grid Count", s["grid_count"])
                    with col2:
                        st.metric("Grid Step", f"{s['grid_step']} ({s['grid_step_pct']}%)")
                        st.metric("Shares per Grid", f"{s['shares_per_grid']}")
                    with col3:
                        st.metric("Capital Required", f"{s['capital_required']:.0f} CNY")
                        profit_color = "normal" if s["profit_per_cycle"] > 0 else "inverse"
                        st.metric("Profit per Cycle",
                                   f"{s['profit_per_cycle']} CNY",
                                   f"{s['profit_per_cycle_pct']}% / cycle",
                                   delta_color=profit_color)

                    st.write(f"- Fees per cycle: {s['fees_per_cycle']} CNY")
                    st.write(f"- Break-even price move: {s['break_even_move_pct']}%")
                    st.write(f"- Estimated cycles per month: {s['estimated_cycles_per_month']}")
                    st.write(f"- **Estimated monthly return: {s['estimated_monthly_return_pct']}%**")

                    if s.get("caveats"):
                        for c in s["caveats"]:
                            st.warning(c)
                    st.divider()

    # Sentiment Details
    with st.expander("Sentiment Analysis"):
        st.write(f"**Overall:** {sentiment.get('overall_label', 'N/A')} ({sentiment.get('overall_score', 0):+.2f})")
        st.write(f"**Confidence:** {sentiment.get('confidence', 0):.0%}")
        st.write(f"**Reasoning:** {sentiment.get('reasoning', 'N/A')}")
        if sentiment.get("key_factors"):
            st.write("**Key Factors:**")
            for kf in sentiment["key_factors"]:
                st.write(f"  - {kf}")

    # Fundamental Analysis
    with st.expander("Fundamental Analysis"):
        st.write(f"**Health Score:** {fundamental.get('health_score', 'N/A')}/10")
        st.write(fundamental.get("summary", "N/A"))
        if fundamental.get("red_flags"):
            st.write("**Red Flags:**")
            for rf in fundamental["red_flags"]:
                st.write(f"  - {rf}")

    # Risk Assessment
    with st.expander("Risk Assessment"):
        st.write(f"**Risk Score:** {risk.get('risk_score', 'N/A')}/10 ({risk.get('risk_level', 'N/A')})")
        st.write(risk.get("summary", "N/A"))
        if risk.get("risk_factors"):
            st.write("**Risk Factors:**")
            for rf in risk["risk_factors"]:
                st.write(f"  - {rf}")

    # Full Reasoning Chain
    with st.expander("Full Reasoning Chain"):
        for step in result.get("reasoning_chain", []):
            agent = step.get("agent", "unknown")
            st.write(f"**{agent}:**")
            for k, v in step.items():
                if k != "agent":
                    st.write(f"  - {k}: {v}")
            st.write("---")

    # Errors
    if errors:
        with st.expander("Errors"):
            for err in errors:
                st.error(f"**{err.get('agent', 'unknown')}**: {err.get('error', 'unknown error')}")

    # Disclaimer
    disclaimer = recommendation.get(
        "disclaimer",
        "This analysis is for educational and informational purposes only. "
        "It does not constitute financial advice."
    )
    st.info(f"Disclaimer: {disclaimer}")

    # Save summary to chat
    summary = (
        f"**{ticker} - {rec}** (Confidence: {confidence:.0%})\n\n"
        f"{recommendation.get('reasoning', '')}\n\n"
        f"*See detailed analysis above.*"
    )
    st.session_state.messages.append({"role": "assistant", "content": summary})


def _is_followup_question(query: str, last_analysis: dict | None) -> bool:
    """
    Heuristic to detect if a query is a follow-up about the last analysis
    rather than a new stock analysis request.
    """
    if not last_analysis:
        return False

    query_lower = query.lower()
    last_ticker = last_analysis.get("ticker", "").lower()

    import re
    has_ticker_pattern = bool(re.search(r'\d{4,6}(\.(SS|SZ|SH|HK))?', query))

    # Explicit new analysis keywords + ticker = new analysis
    new_analysis_keywords = ["analyze", "analyse", "analysis of", "what about", "look at"]
    for kw in new_analysis_keywords:
        if kw in query_lower and has_ticker_pattern:
            return False

    # Follow-up indicator keywords
    followup_keywords = [
        "why", "how", "what", "tell me more", "explain", "detail",
        "which", "can you", "could you", "elaborate",
        "risk", "debate", "bull", "bear", "sentiment",
        "fundamental", "quant", "announcement", "social",
        "compared", "versus", "support", "against",
    ]
    if any(kw in query_lower for kw in followup_keywords):
        if not has_ticker_pattern:
            return True

    # Short query referencing the last ticker = follow-up
    if last_ticker and last_ticker in query_lower:
        if len(query.split()) < 15:
            return True

    return False


# ── Page Layout ──

st.title("Multi-Agent Investment Research System")
st.caption("Powered by LangGraph + DeepSeek | 7 AI Agents with Bull vs Bear Debate")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "results" not in st.session_state:
    st.session_state.results = []
if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None  # Stores full state for follow-up

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
query = st.chat_input("Ask about any stock, or ask follow-up questions about the last analysis")

if query:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        # Check if this is a follow-up question about a prior analysis
        is_followup = _is_followup_question(query, st.session_state.last_analysis)

        if is_followup and st.session_state.last_analysis:
            # Follow-up: use stored context from all agents
            ticker = st.session_state.last_analysis.get("ticker", "?")
            with st.spinner(f"Answering follow-up about {ticker}..."):
                try:
                    answer = handle_followup(query, st.session_state.last_analysis)
                    st.write(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Follow-up failed: {e}")
        else:
            # New analysis: run full pipeline
            with st.spinner("Agents are analyzing... (this may take 60-90 seconds)"):
                try:
                    result = run_analysis(query)
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    result = None

            if result:
                intent = result.get("intent", "")
                ticker = result.get("ticker", "")

                if intent in ("chitchat", "out_of_scope", "rejected"):
                    if intent == "rejected":
                        msg = "Your query was flagged for safety reasons. Please rephrase."
                    elif intent == "out_of_scope":
                        msg = "This system is designed for stock analysis. Try asking about a specific stock!"
                    else:
                        msg = "Hello! I'm an investment research assistant. Ask me about any stock - for example, 'Analyze AAPL' or 'What do you think about Microsoft?'"
                    st.write(msg)
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                else:
                    # Store full state for follow-up questions
                    st.session_state.last_analysis = result
                    st.session_state.results.append(result)
                    _render_analysis(result, ticker)


