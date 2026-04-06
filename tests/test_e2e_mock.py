"""
End-to-end test with mocked LLM calls.
Verifies the full LangGraph pipeline works correctly.
"""
import sys
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from unittest.mock import patch, MagicMock
import json


def mock_llm_response(model_class):
    """Create a mock LLM response for a given Pydantic model."""
    schema = model_class.model_json_schema()
    # Build a minimal valid instance
    instance = model_class.model_validate({})
    return instance


def test_full_pipeline():
    """Test the complete analysis pipeline with mocked LLM."""

    # Mock OpenAI client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.usage = MagicMock(total_tokens=100)

    call_count = [0]

    def fake_create(**kwargs):
        call_count[0] += 1
        messages = kwargs.get("messages", [])
        system_msg = messages[0]["content"].lower() if messages and messages[0]["role"] == "system" else ""
        user_msg = messages[-1]["content"].lower() if messages else ""

        # Route by system prompt first (more specific), then user prompt
        if "bullish investment analyst" in system_msg:
            resp = json.dumps({
                "role": "bull",
                "round_number": 1,
                "argument": "AAPL shows strong fundamentals with healthy P/E and growing revenue",
                "key_points": ["Strong earnings beat", "AI growth potential", "Solid cash position"],
                "evidence": ["P/E of 28 with growth", "RSI neutral zone", "Positive sentiment 0.65"],
                "rebuttals": []
            })
        elif "bearish investment analyst" in system_msg:
            resp = json.dumps({
                "role": "bear",
                "round_number": 1,
                "argument": "AAPL faces valuation risk and regulatory headwinds",
                "key_points": ["Premium valuation", "Regulatory concerns", "Market saturation"],
                "evidence": ["P/E above sector average", "SMA20 below SMA50", "Regulatory news"],
                "rebuttals": ["Earnings growth may not sustain premium P/E"]
            })
        elif "intent classification" in system_msg or "classify" in user_msg:
            resp = json.dumps({
                "intent": "stock_query",
                "ticker": "AAPL",
                "company_name": "Apple Inc.",
                "explanation": "User wants to analyze Apple stock"
            })
        elif "sentiment analysis" in system_msg:
            resp = json.dumps({
                "overall_score": 0.65,
                "confidence": 0.8,
                "overall_label": "bullish",
                "reasoning": "Strong earnings and positive analyst sentiment",
                "article_scores": [],
                "key_factors": ["Strong earnings", "Positive analyst coverage"]
            })
        elif "financial analyst" in system_msg or "fundamental" in system_msg:
            resp = json.dumps({
                "health_score": 8.0,
                "pe_assessment": "P/E of 28 is above sector average, indicating premium valuation",
                "pb_assessment": "P/B reasonable for tech sector",
                "roe_assessment": "Strong ROE indicates efficient capital usage",
                "debt_assessment": "Manageable debt levels",
                "peer_comparison": "Outperforms most tech peers on profitability",
                "red_flags": [],
                "summary": "Strong financial fundamentals with premium valuation"
            })
        elif "risk assessment" in system_msg:
            resp = json.dumps({
                "risk_score": 4.5,
                "risk_level": "medium",
                "risk_factors": ["Market volatility", "Regulatory risk", "Valuation premium"],
                "mitigation_notes": ["Strong cash position provides buffer"],
                "summary": "Moderate risk with strong underlying fundamentals"
            })
        elif "senior investment advisor" in system_msg:
            resp = json.dumps({
                "recommendation": "buy",
                "confidence": 0.72,
                "investment_horizon": "medium-term",
                "supporting_factors": [
                    "Strong fundamentals with health score 8/10",
                    "Positive market sentiment",
                    "AI growth catalyst"
                ],
                "dissenting_factors": [
                    "Premium valuation vs sector average",
                    "Regulatory headwinds"
                ],
                "debate_summary": "Bull won on fundamentals and growth. Bear raised valid valuation concerns.",
                "reasoning": "AAPL demonstrates strong fundamentals backed by positive sentiment.",
                "disclaimer": "This is for educational purposes only. Not financial advice."
            })
        else:
            resp = json.dumps({"result": "ok"})

        mock_response.choices[0].message.content = resp
        return mock_response

    mock_client = MagicMock()
    mock_client.chat.completions.create = fake_create

    with patch("backend.llm_client._get_client", return_value=mock_client):
        from backend.graph import run_analysis
        # Need to reset singleton
        import backend.graph
        backend.graph._graph = None

        result = run_analysis("What do you think about AAPL?")

    # Verify results
    print(f"Intent: {result.get('intent')}")
    print(f"Ticker: {result.get('ticker')}")
    print(f"Market Data: price={result.get('market_data', {}).get('current_price')}")
    print(f"News: {len(result.get('news_articles', []))} articles")
    print(f"Sentiment: {result.get('sentiment', {}).get('overall_label')}")
    print(f"Fundamental: health={result.get('fundamental', {}).get('health_score')}")
    print(f"Risk: score={result.get('risk', {}).get('risk_score')}")
    print(f"Debate rounds: {result.get('debate_round')}")
    print(f"Debate history: {len(result.get('debate_history', []))} entries")
    print(f"Recommendation: {result.get('recommendation', {}).get('recommendation')}")
    print(f"Confidence: {result.get('recommendation', {}).get('confidence')}")
    print(f"Reasoning chain: {len(result.get('reasoning_chain', []))} steps")
    print(f"Errors: {result.get('errors', [])}")
    print(f"LLM calls made: {call_count[0]}")

    # Assertions — verify pipeline structure, not exact mock values
    assert result["intent"] == "stock_query", f"Expected stock_query, got {result['intent']}"
    assert result["ticker"] == "AAPL", f"Expected AAPL, got {result['ticker']}"
    assert result["market_data"].get("current_price") is not None, "No market price"
    assert len(result["news_articles"]) > 0, "No news articles"
    assert result["sentiment"].get("overall_label") is not None, "No sentiment label"
    assert result["fundamental"].get("health_score") is not None, "No health score"
    assert result["debate_round"] == 2, f"Expected 2 debate rounds, got {result['debate_round']}"
    assert len(result["debate_history"]) >= 2, f"Expected >=2 debate entries, got {len(result['debate_history'])}"
    assert result["recommendation"] is not None, "No recommendation"
    assert result["recommendation"].get("recommendation") in ("buy", "hold", "sell"), f"Invalid rec: {result['recommendation'].get('recommendation')}"
    assert len(result["reasoning_chain"]) >= 7, f"Expected >=7 reasoning steps, got {len(result['reasoning_chain'])}"
    assert len(result["errors"]) == 0, f"Errors: {result['errors']}"

    print("\nAll E2E assertions passed!")
    print(f"Pipeline: orchestrator -> market_data -> news -> sentiment -> fundamental -> debate(x2) -> risk -> advisory")


if __name__ == "__main__":
    test_full_pipeline()
