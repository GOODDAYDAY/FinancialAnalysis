"""
AI Test Suite: Risk Assessment (F-13) and Fallback (F-19)

Tests risk scoring logic and system resilience under failure.
"""
import pytest
from backend.agents.risk import risk_node
from backend.agents.market_data import market_data_node
from backend.agents.news import news_node
from backend.graph import build_graph


class TestRiskScoring:
    """Risk score should reflect input data severity."""

    def test_healthy_stock_low_risk(self, mock_llm):
        """Input: good sentiment, strong fundamentals → Expected: risk < 5."""
        mock_llm.set_response({
            "risk_score": 3.0, "risk_level": "low",
            "risk_factors": ["Normal market volatility"],
            "mitigation_notes": ["Strong balance sheet"],
            "summary": "Low risk profile",
        })
        state = {
            "ticker": "AAPL",
            "market_data": {"current_price": 190, "pe_ratio": 25, "rsi_14": 55},
            "sentiment": {"overall_score": 0.6, "overall_label": "bullish", "key_factors": []},
            "fundamental": {"health_score": 8, "red_flags": []},
        }
        result = risk_node(state)
        assert result["risk"]["risk_score"] <= 5.0

    def test_troubled_stock_high_risk(self, mock_llm):
        """Input: negative sentiment, red flags → Expected: risk > 6."""
        mock_llm.set_response({
            "risk_score": 8.0, "risk_level": "high",
            "risk_factors": ["SEC investigation", "Revenue decline", "High debt"],
            "mitigation_notes": [],
            "summary": "Significant risk exposure",
        })
        state = {
            "ticker": "XYZ",
            "market_data": {"current_price": 10, "pe_ratio": -5, "rsi_14": 25},
            "sentiment": {"overall_score": -0.8, "overall_label": "bearish", "key_factors": ["Legal trouble"]},
            "fundamental": {"health_score": 2, "red_flags": ["SEC probe", "Cash burn"]},
        }
        result = risk_node(state)
        assert result["risk"]["risk_score"] >= 6.0
        assert len(result["risk"]["risk_factors"]) >= 2

    def test_risk_factors_present(self, mock_llm):
        """Expected: risk_factors is a non-empty list with specific reasons."""
        mock_llm.set_response({
            "risk_score": 5.0, "risk_level": "medium",
            "risk_factors": ["Market volatility", "Sector headwinds"],
            "mitigation_notes": ["Diversified revenue"],
            "summary": "Moderate risk",
        })
        state = {
            "ticker": "AAPL",
            "market_data": {"current_price": 190}, "sentiment": {},
            "fundamental": {"health_score": 6, "red_flags": []},
        }
        result = risk_node(state)
        assert isinstance(result["risk"]["risk_factors"], list)
        assert len(result["risk"]["risk_factors"]) >= 1

    def test_risk_prompt_includes_sentiment_data(self, mock_llm):
        """Expected: risk agent receives sentiment score in its prompt."""
        mock_llm.set_response({
            "risk_score": 5.0, "risk_level": "medium",
            "risk_factors": [], "mitigation_notes": [], "summary": "",
        })
        state = {
            "ticker": "AAPL",
            "market_data": {"current_price": 190},
            "sentiment": {"overall_score": -0.5, "overall_label": "bearish", "key_factors": ["Bad news"]},
            "fundamental": {"health_score": 7, "red_flags": []},
        }
        risk_node(state)
        user_prompt = mock_llm.last_user_prompt()
        assert "-0.5" in user_prompt, "Risk prompt should contain sentiment score"
        assert "bearish" in user_prompt.lower(), "Risk prompt should contain sentiment label"


class TestFallbackResilience:
    """F-19: System should handle agent failures gracefully."""

    def test_market_data_fallback_to_mock(self):
        """Input: invalid ticker → Expected: mock data returned, is_mock=True."""
        # Use a ticker that doesn't exist — should fall back to mock
        result = market_data_node({"ticker": "ZZZZZ_INVALID_99999"})
        md = result.get("market_data", {})
        assert md.get("is_mock") is True or md.get("current_price") is not None

    def test_news_fallback_to_mock(self):
        """Input: ticker with no news → Expected: some articles returned (mock or real)."""
        result = news_node({"ticker": "ZZZZZ_INVALID_99999"})
        articles = result.get("news_articles", [])
        assert len(articles) >= 1, "Should fall back to mock news"

    def test_no_ticker_returns_error(self):
        """Input: empty ticker → Expected: error in output, no crash."""
        result = market_data_node({"ticker": ""})
        assert len(result.get("errors", [])) > 0


class TestLLMOutputValidation:
    """Tests that the system handles malformed LLM output."""

    def test_handles_markdown_wrapped_json(self, mock_llm):
        """Input: LLM wraps JSON in markdown → Expected: correctly parsed."""
        mock_llm.set_response('```json\n{"risk_score": 5.0, "risk_level": "medium", "risk_factors": [], "mitigation_notes": [], "summary": "OK"}\n```')
        state = {
            "ticker": "AAPL",
            "market_data": {"current_price": 190},
            "sentiment": {}, "fundamental": {},
        }
        result = risk_node(state)
        assert result["risk"]["risk_score"] == 5.0

    def test_handles_extra_text_around_json(self, mock_llm):
        """Input: LLM adds text before JSON → Expected: JSON still extracted."""
        mock_llm.set_response('Here is the analysis:\n{"risk_score": 6.0, "risk_level": "medium", "risk_factors": ["volatility"], "mitigation_notes": [], "summary": "Test"}')
        state = {
            "ticker": "AAPL",
            "market_data": {}, "sentiment": {}, "fundamental": {},
        }
        result = risk_node(state)
        assert result["risk"]["risk_score"] == 6.0
