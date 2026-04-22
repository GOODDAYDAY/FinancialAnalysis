"""
Quant Agent node: pure algorithmic quantitative analysis, no LLM.

Computes technical signals and a composite score used as
"data referee" evidence in the Bull vs Bear debate.
"""

import logging
from backend.agents.quant.signals import (
    compute_ma_signals,
    compute_rsi_signals,
    compute_macd_signals,
    compute_range_signals,
    compute_pe_signals,
)
from backend.agents.quant.advanced_signals import compute_advanced_signals
from backend.config import settings
from backend import mlflow_utils
from backend.feature_store import compute_features as compute_all_features

logger = logging.getLogger(__name__)


def quant_node(state: dict) -> dict:
    """Pure algorithmic quantitative analysis. No LLM call."""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})

    if not market_data or not market_data.get("current_price"):
        return {
            "quant": {"score": 0, "signals": [], "summary": "Insufficient data for quant analysis."},
            "reasoning_chain": [{"agent": "quant", "note": "no market data"}],
        }

    logger.info("Running quant analysis for %s", ticker)

    # Compute features via the Feature Store (unified, versioned)
    features = compute_all_features(ticker)

    price = market_data.get("current_price", 0)

    # Gather all signals from sub-modules
    signals = []
    signals.extend(compute_ma_signals(
        price, market_data.get("sma_20"), market_data.get("sma_50"), market_data.get("sma_200")))
    signals.extend(compute_rsi_signals(market_data.get("rsi_14")))
    signals.extend(compute_macd_signals(market_data.get("macd"), market_data.get("macd_signal")))
    signals.extend(compute_range_signals(
        price, market_data.get("fifty_two_week_high"), market_data.get("fifty_two_week_low")))
    signals.extend(compute_pe_signals(market_data.get("pe_ratio")))
    # Advanced indicators fetched from raw OHLCV — degrades gracefully on failure
    try:
        signals.extend(compute_advanced_signals(ticker))
    except Exception as e:
        logger.warning("Advanced quant signals failed for %s: %s", ticker, e)

    # Compute composite score
    score = sum(s["weight"] for s in signals)
    score = max(-100, min(100, score))

    # Classify verdict
    if score >= 30:
        verdict = "STRONG BUY SIGNAL"
    elif score >= 10:
        verdict = "MODERATE BUY SIGNAL"
    elif score > -10:
        verdict = "NEUTRAL - NO CLEAR SIGNAL"
    elif score > -30:
        verdict = "MODERATE SELL SIGNAL"
    else:
        verdict = "STRONG SELL SIGNAL"

    bullish = [s for s in signals if s["type"] == "bullish"]
    bearish = [s for s in signals if s["type"] == "bearish"]

    summary = (
        f"Quant Score: {score}/100 ({verdict}). "
        f"{len(bullish)} bullish signals, {len(bearish)} bearish signals. "
        f"Strongest bullish: {bullish[0]['name'] if bullish else 'none'}. "
        f"Strongest bearish: {bearish[0]['name'] if bearish else 'none'}."
    )

    quant_result = {
        "score": score,
        "verdict": verdict,
        "signals": signals,
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "summary": summary,
    }

    logger.info("Quant for %s: score=%d, verdict=%s", ticker, score, verdict)

    # MLflow: log quant metrics for experiment tracking
    _log_quant_to_mlflow(ticker, score, verdict, signals, features)

    return {
        "quant": quant_result,
        "reasoning_chain": [{
            "agent": "quant",
            "score": score,
            "verdict": verdict,
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "summary": summary,
        }],
    }


def _log_quant_to_mlflow(ticker, score, verdict, signals, features: dict | None = None):
    """Log quant analysis results to MLflow for experiment tracking."""
    try:
        run_name = f"quant-{ticker}"
        with mlflow_utils.start_mlflow_run(
            experiment_name=f"{settings.mlflow_experiment_name}/quant",
            run_name=run_name,
            tracking_uri=settings.mlflow_tracking_uri or None,
        ) as run:
            if run is None:
                return
            params = {"ticker": ticker, "verdict": verdict}
            if features and "feature_schema_version" in features:
                params["feature_schema_version"] = features["feature_schema_version"]
            mlflow_utils.log_params(params)
            mlflow_utils.log_metrics({
                "quant_score": score,
                "bullish_count": len([s for s in signals if s["type"] == "bullish"]),
                "bearish_count": len([s for s in signals if s["type"] == "bearish"]),
                "neutral_count": len([s for s in signals if s["type"] == "neutral"]),
            })
    except Exception as e:
        logger.warning("MLflow logging in quant failed: %s", e)
