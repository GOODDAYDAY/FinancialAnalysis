"""Advisory agent node: synthesize all analysis + debate into recommendation."""

import logging
from backend.llm_client import call_llm_structured
from backend.state import RecommendationOutput
from backend.utils.language import language_directive
from backend.config import settings
from backend import mlflow_utils

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
    macro = state.get("macro_env", {})
    sector = state.get("sector", {})
    momentum = state.get("momentum", {})
    debate_judge = state.get("debate_judge", {})
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
        f"You have access to: macro market environment, sector/industry context, "
        f"market data, momentum signals, sentiment analysis, fundamental analysis, "
        f"quant signals (algorithmic, unbiased), grid trading analysis, risk assessment, "
        f"and a judge-moderated Bull vs Bear debate.\n\n"
        f"CRITICAL: DO NOT recommend SELL on a stock that has been strongly rising "
        f"unless there is overwhelming fundamental or macro evidence against it. "
        f"Momentum agent's short-term signals must be respected. If a stock is at a 20-day "
        f"breakout with a bullish 5-day return and is riding a hot sector in a bull market, "
        f"SELL is almost certainly wrong.\n\n"
        f"Weight the dimensions:\n"
        f"- Momentum (short-term price action): 20%\n"
        f"- Fundamental analysis: 20%\n"
        f"- Quant signals (long-term trend): 15%\n"
        f"- Macro / sector context: 15%\n"
        f"- Sentiment analysis: 10%\n"
        f"- Risk assessment: 10%\n"
        f"- Technical indicators: 10%\n\n"
        f"Consider the debate outcome: which side made stronger arguments? "
        f"What points were conceded vs contested?\n\n"
        f"Provide a clear recommendation (buy/hold/sell), confidence level (0-1), "
        f"and investment horizon (short-term/medium-term/long-term)."
    ) + language_directive(language)

    macro_summary = macro.get("summary", "N/A") if macro else "N/A"
    macro_regime = macro.get("overall_regime", "UNKNOWN") if macro else "UNKNOWN"
    sector_summary = sector.get("summary", "N/A") if sector else "N/A"
    momentum_score = momentum.get("score", "N/A") if momentum else "N/A"
    momentum_regime = momentum.get("regime", "N/A") if momentum else "N/A"
    momentum_returns = momentum.get("returns", {}) if momentum else {}

    judge_summary = ""
    if debate_judge:
        judge_summary = (
            f"--- DEBATE JUDGE VERDICT ---\n"
            f"Quality score: {debate_judge.get('quality_score', 'N/A')}/100\n"
            f"Bull strength: {debate_judge.get('bull_strength', 'N/A')}/100\n"
            f"Bear strength: {debate_judge.get('bear_strength', 'N/A')}/100\n"
            f"Rounds completed: {debate_judge.get('round_evaluated', 'N/A')}\n"
            f"Reason: {debate_judge.get('reason', 'N/A')}\n\n"
        )

    user_prompt = (
        f"Generate investment recommendation for {ticker}:\n\n"
        f"--- MACRO ENVIRONMENT ---\n"
        f"Overall market regime: {macro_regime}\n"
        f"Details: {macro_summary}\n\n"
        f"--- SECTOR / INDUSTRY ---\n"
        f"{sector_summary}\n\n"
        f"--- MARKET DATA ---\n"
        f"Price: ${market_data.get('current_price', 'N/A')}\n"
        f"Change today: {market_data.get('price_change_pct', 'N/A')}%\n"
        f"P/E: {market_data.get('pe_ratio', 'N/A')}\n"
        f"RSI: {market_data.get('rsi_14', 'N/A')}\n"
        f"Signals: {market_data.get('technical_signals', [])}\n\n"
        f"--- MOMENTUM (SHORT/MEDIUM TERM) ---\n"
        f"Momentum Score: {momentum_score}/100 ({momentum_regime})\n"
        f"Recent returns: 3d={momentum_returns.get('3d')}, 5d={momentum_returns.get('5d')}, "
        f"10d={momentum_returns.get('10d')}, 20d={momentum_returns.get('20d')}\n"
        f"20d range position: {momentum.get('range_position_pct', 'N/A')}%\n"
        f"20d breakout: {momentum.get('breakout_20', False)}\n"
        f"Relative strength vs CSI 300 (20d): {momentum.get('relative_strength_vs_csi300_20d', 'N/A')}%\n\n"
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
        f"Factors: {risk.get('risk_factors', [])}\n\n"
        f"{judge_summary}"
        f"{debate_text}"
    )

    result = call_llm_structured(
        user_prompt=user_prompt,
        response_model=RecommendationOutput,
        system_prompt=system_prompt,
    )

    # Post-processing decision override — LLMs default to HOLD even
    # against strong numeric evidence. Compute a composite score from
    # momentum/quant/fundamental/sentiment/risk and override the LLM
    # verdict when it disagrees sharply with the math.
    override = _compute_decision_override(
        momentum=momentum,
        quant=quant,
        fundamental=fundamental,
        sentiment=sentiment,
        risk=risk,
        debate_judge=debate_judge,
    )
    original_rec = result.recommendation
    if override["forced_recommendation"] and override["forced_recommendation"] != original_rec:
        logger.info(
            "Advisory override: LLM said %s, algo says %s (composite=%.1f). Rule: %s",
            original_rec, override["forced_recommendation"], override["composite_score"], override["rule"],
        )
        result.recommendation = override["forced_recommendation"]
        result.confidence = max(result.confidence, override["confidence_floor"])
        result.reasoning = (
            f"[AUTO-OVERRIDE] LLM suggested {original_rec}; algorithmic composite score "
            f"{override['composite_score']:+.1f} triggered rule '{override['rule']}' → "
            f"{override['forced_recommendation']}.\n\n" + (result.reasoning or "")
        )

    logger.info(
        "Advisory for %s: %s (confidence=%.2f, composite=%.1f)",
        ticker, result.recommendation, result.confidence, override["composite_score"],
    )

    # MLflow experiment tracking
    _log_advisory_to_mlflow(ticker, result, override, market_data, sentiment,
                            fundamental, quant, risk, macro, sector, momentum)

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
            "composite_score": override["composite_score"],
            "override_applied": override["forced_recommendation"] is not None and override["forced_recommendation"] != original_rec,
            "override_rule": override["rule"],
        }],
    }


def _log_advisory_to_mlflow(ticker, result, override, market_data, sentiment,
                             fundamental, quant, risk, macro, sector, momentum):
    """Log advisory output to MLflow for experiment tracking and audit."""
    try:
        run_name = f"{ticker}-{result.recommendation}"
        with mlflow_utils.start_mlflow_run(
            experiment_name=settings.mlflow_experiment_name,
            run_name=run_name,
            tracking_uri=settings.mlflow_tracking_uri or None,
        ) as run:
            if run is None:
                return  # mlflow not available
            mlflow_utils.log_params({
                "ticker": ticker,
                "recommendation": result.recommendation,
                "investment_horizon": result.investment_horizon,
                "composite_score": override["composite_score"],
                "override_applied": bool(override["forced_recommendation"] and override["forced_recommendation"] != result.recommendation),
            })
            mlflow_utils.log_metrics({
                "confidence": result.confidence,
                "composite_score": override["composite_score"],
            })
            # Log key inputs as context
            mlflow_utils.log_params({
                "market_price": market_data.get("current_price", "N/A"),
                "sentiment_score": sentiment.get("overall_score", "N/A"),
                "fundamental_health": fundamental.get("health_score", "N/A"),
                "quant_score": quant.get("score", "N/A"),
                "risk_score": risk.get("risk_score", "N/A"),
            })
    except Exception as e:
        logger.warning("MLflow logging in advisory failed: %s", e)


def _compute_decision_override(
    momentum: dict, quant: dict, fundamental: dict,
    sentiment: dict, risk: dict, debate_judge: dict,
) -> dict:
    """
    Weighted composite score from numeric dimensions, combined with
    hard-rule triggers. Returns:

      {
        "composite_score":   float in [-100, +100],
        "forced_recommendation": "buy" | "hold" | "sell" | None,
        "confidence_floor": float,
        "rule":              str,
      }

    Rationale: LLMs have strong HOLD bias. When numeric evidence is
    lopsided, we override. When numeric evidence is ambiguous, we defer
    to the LLM.
    """
    # Normalize components to [-100, +100]
    mom_score = _safe_number(momentum.get("score"), default=0)
    quant_score = _safe_number(quant.get("score"), default=0)
    health = _safe_number(fundamental.get("health_score"), default=5)
    fund_score = (health - 5) * 20                     # maps [1..10] -> [-80..+100]
    sent_raw = _safe_number(sentiment.get("overall_score"), default=0)
    sent_score = sent_raw * 100                        # [-1..+1] -> [-100..+100]
    risk_raw = _safe_number(risk.get("risk_score"), default=5)
    risk_score = (5 - risk_raw) * 20                   # higher risk → more negative

    # Weighted composite (matches prompt weights)
    composite = (
        0.25 * mom_score +
        0.20 * fund_score +
        0.20 * quant_score +
        0.15 * sent_score +
        0.20 * risk_score
    )

    # Hard rule: strong recent rally → never sell
    r5 = _safe_number((momentum.get("returns") or {}).get("5d"), default=0)
    r20 = _safe_number((momentum.get("returns") or {}).get("20d"), default=0)
    breakout = bool(momentum.get("breakout_20"))

    # Debate judge strength (if present, influences confidence floor)
    bull_strength = _safe_number(debate_judge.get("bull_strength"), default=50)
    bear_strength = _safe_number(debate_judge.get("bear_strength"), default=50)

    # Rules in priority order
    if r5 >= 8 and mom_score >= 30 and composite >= 0:
        return {
            "composite_score": composite,
            "forced_recommendation": "buy",
            "confidence_floor": 0.65,
            "rule": "strong_short_term_rally",
        }

    if composite >= 35:
        return {
            "composite_score": composite,
            "forced_recommendation": "buy",
            "confidence_floor": 0.60,
            "rule": "composite_strongly_bullish",
        }

    if composite <= -35:
        return {
            "composite_score": composite,
            "forced_recommendation": "sell",
            "confidence_floor": 0.55,
            "rule": "composite_strongly_bearish",
        }

    if breakout and r5 > 0 and composite >= 10:
        return {
            "composite_score": composite,
            "forced_recommendation": "buy",
            "confidence_floor": 0.55,
            "rule": "breakout_with_positive_composite",
        }

    if r5 >= 5 and composite >= 0:
        # Prevent SELL when stock is rising — LLM may still choose BUY/HOLD
        return {
            "composite_score": composite,
            "forced_recommendation": None,
            "confidence_floor": 0.0,
            "rule": "rising_stock_no_sell_guard",
        }

    if bull_strength - bear_strength >= 25 and composite >= 10:
        return {
            "composite_score": composite,
            "forced_recommendation": "buy",
            "confidence_floor": 0.55,
            "rule": "debate_bull_dominant",
        }

    if bear_strength - bull_strength >= 25 and composite <= -10:
        return {
            "composite_score": composite,
            "forced_recommendation": "sell",
            "confidence_floor": 0.55,
            "rule": "debate_bear_dominant",
        }

    return {
        "composite_score": composite,
        "forced_recommendation": None,
        "confidence_floor": 0.0,
        "rule": "no_override",
    }


def _safe_number(value, default: float = 0.0) -> float:
    """Coerce to float, falling back to default on None / str / bad data."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
