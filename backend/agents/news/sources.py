"""News data sources: yfinance + akshare + DuckDuckGo + deduplication."""

import logging
import hashlib
from backend.state import NewsArticle

logger = logging.getLogger(__name__)


def fetch_news(ticker: str, company_name: str = "") -> list[dict]:
    """
    Fetch news from multiple sources. Returns an empty list when no
    real news is found — NEVER fabricates mock articles, because
    fake news would poison the sentiment agent downstream.
    """
    articles = []

    # Source 1: akshare Eastmoney stock news (best for Chinese A-shares)
    try:
        articles.extend(_fetch_akshare_news(ticker))
    except Exception as e:
        logger.warning("akshare news failed for %s: %s", ticker, e)

    # Source 2: yfinance news (best for US/HK)
    try:
        articles.extend(_fetch_yfinance_news(ticker))
    except Exception as e:
        logger.warning("yfinance news failed for %s: %s", ticker, e)

    # Source 3: DuckDuckGo search (general fallback)
    try:
        search_query = f"{ticker} {company_name} stock news" if company_name else f"{ticker} stock news"
        articles.extend(_fetch_ddg_news(search_query))
    except Exception as e:
        logger.warning("DuckDuckGo news failed for %s: %s", ticker, e)

    if not articles:
        logger.warning(
            "No news found for %s from any source — returning EMPTY list "
            "(downstream sentiment will record neutral with low confidence)",
            ticker,
        )
        return []

    deduped = _deduplicate(articles)
    logger.info("News for %s: %d raw -> %d after dedup", ticker, len(articles), len(deduped))

    deduped.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)
    return deduped[:10]


def _fetch_akshare_news(ticker: str) -> list[dict]:
    """
    Fetch individual stock news from Eastmoney via akshare.
    Best source for Chinese A-share stocks.

    NOTE: ak.stock_news_em() internally uses pandas .str.replace with
    a Python unicode escape (\\u3000). On pandas 2.x with the pyarrow
    string backend (RE2 regex engine), \\u is rejected as invalid.
    Workaround: temporarily switch to the python string backend.
    """
    import akshare as ak
    import pandas as pd

    # akshare expects bare digit code: '300565' from '300565.SZ'
    symbol = ticker.split(".")[0] if "." in ticker else ticker
    if not symbol.isdigit():
        return []  # akshare individual-stock news only supports A-share codes

    # Save and override pandas options to avoid the pyarrow regex issue
    saved_infer = None
    saved_storage = None
    try:
        saved_infer = pd.get_option("future.infer_string")
    except Exception:
        pass
    try:
        saved_storage = pd.get_option("mode.string_storage")
    except Exception:
        pass

    try:
        try:
            pd.set_option("future.infer_string", False)
        except Exception:
            pass
        try:
            pd.set_option("mode.string_storage", "python")
        except Exception:
            pass
        df = ak.stock_news_em(symbol=symbol)
    except Exception as e:
        logger.warning("ak.stock_news_em(%s) failed: %s", symbol, e)
        return []
    finally:
        if saved_infer is not None:
            try:
                pd.set_option("future.infer_string", saved_infer)
            except Exception:
                pass
        if saved_storage is not None:
            try:
                pd.set_option("mode.string_storage", saved_storage)
            except Exception:
                pass

    if df is None or df.empty:
        return []

    results = []
    # Eastmoney returns columns like 关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接
    for _, row in df.head(10).iterrows():
        title = str(row.get("新闻标题") or row.get("title") or "").strip()
        if not title:
            continue
        results.append(
            NewsArticle(
                title=title,
                source=str(row.get("文章来源") or "Eastmoney"),
                url=str(row.get("新闻链接") or ""),
                published=str(row.get("发布时间") or ""),
                summary=str(row.get("新闻内容") or "")[:500],
                relevance_score=0.9,
            ).model_dump()
        )
    logger.info("akshare Eastmoney news for %s: %d articles", symbol, len(results))
    return results


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
