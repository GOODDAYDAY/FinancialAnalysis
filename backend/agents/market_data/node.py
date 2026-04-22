"""Market Data agent node: fetch stock prices and technical indicators."""

import logging
from backend.agents.market_data.providers import fetch_market_data
from backend.feature_store import compute_features as compute_all_features

logger = logging.getLogger(__name__)


def market_data_node(state: dict) -> dict:
    """F-04, F-05, F-06: Fetch market data with mock fallback."""
    ticker = state.get("ticker", "")
    if not ticker:
        return {
            "market_data": {},
            "errors": [{"agent": "market_data", "error": "No ticker provided"}],
        }

    logger.info("Fetching market data for %s", ticker)
    result = fetch_market_data(ticker)
    data = result.model_dump()

    # Compute features via the Feature Store for training/inference consistency
    try:
        features = compute_all_features(ticker)
        data["feature_schema_version"] = features.get("feature_schema_version", "unknown")
    except Exception as e:
        logger.warning("Feature Store compute failed for %s: %s", ticker, e)
        data["feature_schema_version"] = "unknown"

    logger.info(
        "Market data for %s: price=%.2f, source=%s, feature_schema=%s",
        ticker, result.current_price or 0, result.data_source,
        data.get("feature_schema_version", "unknown"),
    )

    return {
        "market_data": data,
        "reasoning_chain": [{
            "agent": "market_data",
            "ticker": ticker,
            "price": result.current_price,
            "source": result.data_source,
            "is_mock": result.is_mock,
            "signals": result.technical_signals,
            "feature_schema_version": data.get("feature_schema_version", "unknown"),
        }],
    }
