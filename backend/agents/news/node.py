"""News agent node: collect and deduplicate news from multiple sources."""

import logging
from backend.agents.news.sources import fetch_news

logger = logging.getLogger(__name__)


def news_node(state: dict) -> dict:
    """F-07, F-08: Fetch news with deduplication."""
    ticker = state.get("ticker", "")
    if not ticker:
        return {
            "news_articles": [],
            "errors": [{"agent": "news", "error": "No ticker provided"}],
        }

    logger.info("Fetching news for %s", ticker)
    articles = fetch_news(ticker)
    logger.info("Got %d news articles for %s", len(articles), ticker)

    return {
        "news_articles": articles,
        "reasoning_chain": [{
            "agent": "news",
            "ticker": ticker,
            "article_count": len(articles),
            "sources": list(set(a.get("source", "unknown") for a in articles)),
        }],
    }
