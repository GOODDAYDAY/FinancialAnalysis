"""Real API tests for Social Sentiment Agent (akshare/Eastmoney)."""

from backend.agents.social_sentiment.node import social_sentiment_node


class TestSocialSentiment:
    """Fetch real social sentiment data from Eastmoney."""

    def test_comment_score_for_moutai(self):
        """Expected: comment score exists for major A-share stock."""
        result = social_sentiment_node({"ticker": "600519.SS"})
        ss = result.get("social_sentiment", {})
        assert ss.get("summary"), "Summary should not be empty"

    def test_has_trending_info(self):
        """Expected: is_trending field present (True or False)."""
        result = social_sentiment_node({"ticker": "600519.SS"})
        ss = result.get("social_sentiment", {})
        assert "is_trending" in ss

    def test_reasoning_chain_recorded(self):
        result = social_sentiment_node({"ticker": "600519.SS"})
        agents = [s["agent"] for s in result.get("reasoning_chain", [])]
        assert "social_sentiment" in agents
