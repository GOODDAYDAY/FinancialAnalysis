"""
Social Sentiment Agent node: collects retail investor sentiment
from Chinese financial social platforms (Eastmoney Guba, etc.).

Uses akshare to fetch stock comment sentiment scores, hot stock rankings,
and individual stock attention metrics. All free, no API key.
"""

import logging
from backend.agents.social_sentiment.sources import (
    fetch_stock_comments,
    fetch_hot_stocks,
    fetch_individual_stock_hotrank,
)

logger = logging.getLogger(__name__)


def social_sentiment_node(state: dict) -> dict:
    """Fetch social sentiment data from Chinese financial platforms."""
    ticker = state.get("ticker", "")
    if not ticker:
        return {
            "social_sentiment": {},
            "errors": [{"agent": "social_sentiment", "error": "No ticker provided"}],
        }

    logger.info("Fetching social sentiment for %s", ticker)

    # Collect from multiple sources
    comments = fetch_stock_comments(ticker)
    hotrank = fetch_individual_stock_hotrank(ticker)
    hot_stocks = fetch_hot_stocks()

    # Check if our stock is in the hot list
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    is_trending = any(s.get("code") == symbol for s in hot_stocks)
    trending_rank = next(
        (s.get("rank") for s in hot_stocks if s.get("code") == symbol), None
    )

    social_data = {
        "comment_sentiment": comments,
        "hot_rank": hotrank,
        "is_trending": is_trending,
        "trending_rank": trending_rank,
        "hot_stocks_sample": hot_stocks[:5],  # Top 5 for context
    }

    # Generate a summary
    summary_parts = []
    if comments:
        score = comments.get("overall_score", 0)
        summary_parts.append(f"Eastmoney comment score: {score}")
    if is_trending:
        summary_parts.append(f"Currently trending (rank #{trending_rank})")
    else:
        summary_parts.append("Not in top trending stocks")
    if hotrank:
        summary_parts.append(f"Hot rank data: {hotrank.get('rank', 'N/A')}")

    social_data["summary"] = ". ".join(summary_parts) if summary_parts else "No social data available"

    logger.info("Social sentiment for %s: trending=%s, comments=%s",
                ticker, is_trending, bool(comments))

    return {
        "social_sentiment": social_data,
        "reasoning_chain": [{
            "agent": "social_sentiment",
            "ticker": ticker,
            "has_comments": bool(comments),
            "is_trending": is_trending,
            "trending_rank": trending_rank,
            "summary": social_data["summary"],
        }],
    }
