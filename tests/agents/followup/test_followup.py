"""Real API tests for Follow-up Agent (DeepSeek LLM)."""

from backend.agents.followup.node import handle_followup


def _make_prior_state():
    return {
        "ticker": "600519.SS",
        "market_data": {"current_price": 1460, "pe_ratio": 20.4, "rsi_14": 50},
        "news_articles": [{"title": "Moutai Q4 beats", "source": "Reuters", "summary": "Strong earnings"}],
        "announcements": [{"title": "Annual Report 2025", "date": "2026-03-30"}],
        "financial_summary": {"roe": "54.27%", "revenue": "6.28B"},
        "social_sentiment": {"summary": "Comment score 75.8"},
        "sentiment": {"overall_score": 0.3, "overall_label": "bullish", "reasoning": "Good", "key_factors": [], "confidence": 0.7},
        "fundamental": {"health_score": 8.5, "summary": "Strong", "red_flags": []},
        "quant": {"score": 15, "verdict": "MODERATE BUY", "signals": [{"name": "MACD", "type": "bullish", "detail": "Above signal"}]},
        "debate_history": [
            {"role": "bull", "round_number": 1, "argument": "Strong moat", "key_points": ["ROE 54%"], "evidence": [], "rebuttals": []},
            {"role": "bear", "round_number": 1, "argument": "Overvalued", "key_points": ["PE premium"], "evidence": [], "rebuttals": []},
        ],
        "risk": {"risk_score": 4.5, "risk_level": "medium", "risk_factors": ["Valuation"], "summary": "Moderate"},
        "recommendation": {"recommendation": "hold", "confidence": 0.55, "investment_horizon": "long-term",
                           "supporting_factors": ["Strong brand"], "dissenting_factors": ["High PE"],
                           "debate_summary": "Bull won on fundamentals", "reasoning": "Hold due to mixed signals"},
    }


class TestFollowUp:
    """Follow-up questions using full prior context."""

    def test_answer_about_debate(self):
        """Expected: answer references debate content."""
        answer = handle_followup("Who won the debate, bull or bear?", _make_prior_state())
        assert len(answer) > 50
        assert "bull" in answer.lower() or "bear" in answer.lower()

    def test_answer_about_quant(self):
        """Expected: answer references quant score."""
        answer = handle_followup("What was the quant score?", _make_prior_state())
        assert "15" in answer or "quant" in answer.lower()

    def test_answer_about_risk(self):
        """Expected: answer references risk factors."""
        answer = handle_followup("What are the main risks?", _make_prior_state())
        assert len(answer) > 30
