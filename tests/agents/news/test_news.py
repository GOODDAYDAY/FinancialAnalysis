"""Real API tests for News Agent (yfinance + DuckDuckGo)."""

from backend.agents.news.node import news_node


class TestNewsCollection:
    """Fetch real news articles."""

    def test_fetch_news_for_major_stock(self):
        """Expected: at least 1 article for a major stock."""
        result = news_node({"ticker": "AAPL"})
        articles = result["news_articles"]
        assert len(articles) >= 1

    def test_articles_have_required_fields(self):
        """Expected: each article has title and source."""
        result = news_node({"ticker": "600519.SS"})
        for article in result["news_articles"][:3]:
            assert "title" in article
            assert "source" in article
            assert len(article["title"]) > 0

    def test_invalid_ticker_does_not_crash(self):
        """Expected: unknown ticker returns empty list gracefully — no exception."""
        result = news_node({"ticker": "ZZZZZZ_INVALID"})
        assert isinstance(result["news_articles"], list)  # May be empty — no crash
