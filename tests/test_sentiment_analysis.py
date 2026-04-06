"""
AI Test Suite: Sentiment Analysis (F-09, F-10)

Tests that the sentiment agent produces correct sentiment direction
and includes explainable reasoning given specific news inputs.
"""
import pytest
from backend.agents.sentiment import sentiment_node


class TestSentimentDirection:
    """Given news with known tone, sentiment score should match."""

    def test_positive_news_returns_bullish(self, mock_llm):
        """Input: clearly positive news → Expected: score > 0, label=bullish."""
        mock_llm.set_response({
            "overall_score": 0.75,
            "confidence": 0.85,
            "overall_label": "bullish",
            "reasoning": "Strong earnings beat and analyst upgrades indicate positive momentum",
            "article_scores": [{"title": "Earnings Beat", "score": 0.8}],
            "key_factors": ["Earnings beat expectations", "Multiple analyst upgrades"]
        })
        state = {
            "ticker": "AAPL",
            "news_articles": [
                {"title": "AAPL Smashes Earnings Estimates, Revenue Up 20%", "source": "Reuters", "summary": "Apple reported record quarterly earnings."},
                {"title": "Analysts Upgrade AAPL to Strong Buy", "source": "Bloomberg", "summary": "Wall Street consensus shifts bullish."},
            ]
        }
        result = sentiment_node(state)
        sent = result["sentiment"]

        assert sent["overall_score"] > 0, f"Positive news should give positive score, got {sent['overall_score']}"
        assert sent["overall_label"] == "bullish"
        assert sent["confidence"] > 0.5

    def test_negative_news_returns_bearish(self, mock_llm):
        """Input: clearly negative news → Expected: score < 0, label=bearish."""
        mock_llm.set_response({
            "overall_score": -0.7,
            "confidence": 0.8,
            "overall_label": "bearish",
            "reasoning": "SEC investigation and product recall signal major issues",
            "article_scores": [],
            "key_factors": ["SEC investigation", "Product recall", "Revenue miss"]
        })
        state = {
            "ticker": "XYZ",
            "news_articles": [
                {"title": "SEC Launches Investigation Into XYZ Accounting Practices", "source": "WSJ", "summary": "Federal regulators probe potential fraud."},
                {"title": "XYZ Recalls Flagship Product Over Safety Concerns", "source": "CNBC", "summary": "Massive recall impacts revenue outlook."},
                {"title": "XYZ Misses Revenue Estimates by 15%", "source": "FT", "summary": "Disappointing quarter raises concerns."},
            ]
        }
        result = sentiment_node(state)
        sent = result["sentiment"]

        assert sent["overall_score"] < 0, f"Negative news should give negative score, got {sent['overall_score']}"
        assert sent["overall_label"] == "bearish"

    def test_mixed_news_returns_neutral(self, mock_llm):
        """Input: mixed positive/negative news → Expected: score near 0, label=neutral."""
        mock_llm.set_response({
            "overall_score": 0.05,
            "confidence": 0.5,
            "overall_label": "neutral",
            "reasoning": "Mixed signals: strong earnings but regulatory concerns",
            "article_scores": [],
            "key_factors": ["Strong earnings offset by regulatory risk"]
        })
        state = {
            "ticker": "META",
            "news_articles": [
                {"title": "META Reports Record Ad Revenue", "source": "Reuters", "summary": "Strong ad business."},
                {"title": "EU Fines META $2B for Privacy Violations", "source": "BBC", "summary": "Major regulatory penalty."},
            ]
        }
        result = sentiment_node(state)
        sent = result["sentiment"]

        assert -0.3 <= sent["overall_score"] <= 0.3, f"Mixed news should be near-neutral, got {sent['overall_score']}"
        assert sent["overall_label"] == "neutral"

    def test_no_news_returns_neutral_low_confidence(self, mock_llm):
        """Input: empty news list → Expected: score=0, very low confidence."""
        state = {"ticker": "AAPL", "news_articles": []}
        result = sentiment_node(state)
        sent = result["sentiment"]

        assert sent["overall_score"] == 0.0
        assert sent["confidence"] <= 0.2  # very low confidence with no data


class TestSentimentExplainability:
    """F-10: Sentiment output must include explainable reasoning."""

    def test_reasoning_is_not_empty(self, mock_llm):
        """Expected: reasoning field is non-empty string with actual content."""
        mock_llm.set_response({
            "overall_score": 0.5,
            "confidence": 0.7,
            "overall_label": "bullish",
            "reasoning": "Positive earnings and analyst upgrades drive bullish sentiment",
            "article_scores": [],
            "key_factors": ["Earnings beat"]
        })
        state = {
            "ticker": "AAPL",
            "news_articles": [{"title": "Good News", "source": "Test", "summary": "Positive stuff"}]
        }
        result = sentiment_node(state)
        assert len(result["sentiment"]["reasoning"]) > 20, "Reasoning should be substantive"

    def test_key_factors_present(self, mock_llm):
        """Expected: key_factors list is non-empty."""
        mock_llm.set_response({
            "overall_score": 0.5,
            "confidence": 0.7,
            "overall_label": "bullish",
            "reasoning": "Strong fundamentals",
            "article_scores": [],
            "key_factors": ["Revenue growth", "Market expansion"]
        })
        state = {
            "ticker": "AAPL",
            "news_articles": [{"title": "Good", "source": "T", "summary": "S"}]
        }
        result = sentiment_node(state)
        assert len(result["sentiment"]["key_factors"]) > 0

    def test_reasoning_chain_recorded(self, mock_llm):
        """Expected: sentiment step appears in reasoning_chain."""
        mock_llm.set_response({
            "overall_score": 0.3, "confidence": 0.6,
            "overall_label": "bullish", "reasoning": "OK",
            "article_scores": [], "key_factors": []
        })
        state = {
            "ticker": "AAPL",
            "news_articles": [{"title": "T", "source": "S", "summary": "X"}]
        }
        result = sentiment_node(state)
        chain = result.get("reasoning_chain", [])
        assert any(s.get("agent") == "sentiment" for s in chain)
