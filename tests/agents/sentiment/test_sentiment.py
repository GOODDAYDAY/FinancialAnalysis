"""Real API tests for Sentiment Agent (DeepSeek LLM)."""

from backend.agents.sentiment.node import sentiment_node
from backend.agents.news.node import news_node


class TestSentimentAnalysis:
    """Real LLM sentiment analysis on real news."""

    def test_sentiment_on_real_news(self):
        """Expected: valid sentiment score and label from real news."""
        # First fetch real news
        news_result = news_node({"ticker": "AAPL"})
        articles = news_result["news_articles"]

        # Then analyze sentiment
        result = sentiment_node({"ticker": "AAPL", "news_articles": articles})
        sent = result["sentiment"]

        assert -1.0 <= sent["overall_score"] <= 1.0
        assert sent["overall_label"] in ("bullish", "bearish", "neutral")
        assert sent["confidence"] > 0

    def test_reasoning_not_empty(self):
        """Expected: LLM provides substantive reasoning."""
        news_result = news_node({"ticker": "600519.SS"})
        result = sentiment_node({"ticker": "600519.SS", "news_articles": news_result["news_articles"]})
        assert len(result["sentiment"]["reasoning"]) > 20

    def test_no_news_returns_neutral(self):
        """Expected: neutral with low confidence when no articles."""
        result = sentiment_node({"ticker": "TEST", "news_articles": []})
        assert result["sentiment"]["overall_score"] == 0.0
        assert result["sentiment"]["confidence"] <= 0.2
