"""News data sources: yfinance news + DuckDuckGo search + deduplication."""

import logging
import hashlib
from backend.state import NewsArticle
from backend.agents.market_data.mock import get_mock_news

logger = logging.getLogger(__name__)


def fetch_news(ticker: str, company_name: str = "") -> list[dict]:
    """Fetch news from multiple sources. Falls back to mock on failure."""
    articles = []

    # Source 1: yfinance news
    try:
        articles.extend(_fetch_yfinance_news(ticker))
    except Exception as e:
        logger.warning("yfinance news failed for %s: %s", ticker, e)

    # Source 2: DuckDuckGo search
    try:
        search_query = f"{ticker} {company_name} stock news" if company_name else f"{ticker} stock news"
        articles.extend(_fetch_ddg_news(search_query))
    except Exception as e:
        logger.warning("DuckDuckGo news failed for %s: %s", ticker, e)

    if not articles:
        logger.warning("No news from any source for %s, using mock", ticker)
        return get_mock_news(ticker)

    deduped = _deduplicate(articles)
    logger.info("News for %s: %d raw -> %d after dedup", ticker, len(articles), len(deduped))

    deduped.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)
    return deduped[:10]


def _fetch_yfinance_news(ticker: str) -> list[dict]:
    """Fetch news articles from yfinance."""
    import yfinance as yf
    stock = yf.Ticker(ticker)
    news = stock.news or []
    results = []
    for item in news[:10]:
        content = item.get("content", {})
        results.append(
            NewsArticle(
                title=content.get("title", item.get("title", "Untitled")),
                source=content.get("provider", {}).get("displayName", "Yahoo Finance"),
                url=content.get("canonicalUrl", {}).get("url", ""),
                published=content.get("pubDate", ""),
                summary=content.get("summary", ""),
                relevance_score=0.8,
            ).model_dump()
        )
    return results


def _fetch_ddg_news(query: str) -> list[dict]:
    """Fetch news articles from DuckDuckGo search."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=5))
    articles = []
    for item in results:
        articles.append(
            NewsArticle(
                title=item.get("title", "Untitled"),
                source=item.get("source", "DuckDuckGo"),
                url=item.get("url", ""),
                published=item.get("date", ""),
                summary=item.get("body", ""),
                relevance_score=0.6,
            ).model_dump()
        )
    return articles


def _deduplicate(articles: list[dict]) -> list[dict]:
    """Remove duplicate articles based on title similarity (simple hash)."""
    seen = set()
    unique = []
    for article in articles:
        title = article.get("title", "").lower().strip()
        normalized = "".join(c for c in title if c.isalnum() or c.isspace())
        normalized = " ".join(normalized.split())
        key = hashlib.md5(normalized.encode()).hexdigest()[:12]
        if key not in seen:
            seen.add(key)
            unique.append(article)
    return unique
