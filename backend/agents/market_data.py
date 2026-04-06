"""Market Data agent: fetch stock prices and technical indicators."""

import logging
from backend.data.market_api import fetch_market_data

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

    logger.info(
        "Market data for %s: price=%.2f, source=%s",
        ticker, result.current_price or 0, result.data_source,
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
        }],
    }
