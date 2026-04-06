"""Smoke test: verify all imports and basic functionality."""
import sys
sys.path.insert(0, ".")


def test_config():
    from backend.config import settings
    assert settings.deepseek_model == "deepseek-chat"
    print("Config OK")


def test_state_models():
    from backend.state import (
        ResearchState, MarketDataResult, SentimentOutput,
        FundamentalOutput, RiskOutput, DebateArgument, RecommendationOutput,
    )
    # Test Pydantic model creation
    md = MarketDataResult(ticker="AAPL", current_price=189.5)
    assert md.ticker == "AAPL"
    assert md.current_price == 189.5

    da = DebateArgument(role="bull", round_number=1, argument="test")
    assert da.role == "bull"

    ro = RecommendationOutput()
    assert ro.recommendation == "hold"
    print("State models OK")


def test_json_extraction():
    from backend.llm_client import _extract_json
    # Test markdown fence stripping
    result = _extract_json('```json\n{"a": 1}\n```')
    assert '"a"' in result
    # Test finding JSON in text
    result2 = _extract_json('Some text {"b": 2} more text')
    assert '"b"' in result2
    print("JSON extraction OK")


def test_mock_data():
    from backend.data.mock_data import mock_market_data, mock_news
    md = mock_market_data("AAPL")
    assert md.current_price == 189.5
    assert md.is_mock is True
    news = mock_news("AAPL")
    assert len(news) > 0
    print("Mock data OK")


def test_agent_imports():
    from backend.agents.orchestrator import orchestrator_node
    from backend.agents.market_data import market_data_node
    from backend.agents.news import news_node
    from backend.agents.sentiment import sentiment_node
    from backend.agents.fundamental import fundamental_node
    from backend.agents.risk import risk_node
    from backend.agents.debate import debate_node, should_continue_debate
    from backend.agents.advisory import advisory_node
    print("All agent imports OK")


def test_graph_build():
    from backend.graph import build_graph
    graph = build_graph()
    assert graph is not None
    print("Graph compiled OK")


def test_debate_routing():
    from backend.agents.debate import should_continue_debate
    # Round 0 of 2 → continue
    assert should_continue_debate({"debate_round": 0}) == "debate"
    assert should_continue_debate({"debate_round": 1}) == "debate"
    # Round 2 of 2 → done
    assert should_continue_debate({"debate_round": 2}) == "risk"
    print("Debate routing OK")


if __name__ == "__main__":
    test_config()
    test_state_models()
    test_json_extraction()
    test_mock_data()
    test_agent_imports()
    test_graph_build()
    test_debate_routing()
    print("\n✓ All tests passed!")
