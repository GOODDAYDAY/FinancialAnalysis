"""Real API tests for Debate Agent (DeepSeek LLM)."""

from backend.agents.debate.node import debate_node
from backend.agents.debate_judge.node import should_continue_debate_with_judge
from backend.agents.market_data.node import market_data_node


def _make_debate_state(ticker="600519.SS"):
    """Build a minimal state for debate testing with real market data."""
    md = market_data_node({"ticker": ticker})
    return {
        "ticker": ticker,
        "debate_round": 0,
        "debate_history": [],
        "market_data": md["market_data"],
        "sentiment": {"overall_score": 0.3, "overall_label": "bullish", "key_factors": ["Test"], "reasoning": "Test"},
        "fundamental": {"health_score": 7.5, "red_flags": [], "summary": "Solid"},
        "quant": {"score": 10, "verdict": "MODERATE BUY", "signals": [], "bullish_count": 2, "bearish_count": 1, "summary": "Moderate buy"},
        "announcements": [],
        "social_sentiment": {"summary": "No data"},
        "reasoning_chain": [],
    }


class TestDebateRounds:
    """Real LLM debate with Bull and Bear roles."""

    def test_round_1_produces_bull_and_bear(self):
        """Expected: 2 entries (bull + bear) after round 1."""
        state = _make_debate_state()
        result = debate_node(state)
        history = result["debate_history"]
        assert len(history) == 2
        roles = {h["role"] for h in history}
        assert roles == {"bull", "bear"}

    def test_arguments_are_substantive(self):
        """Expected: each argument has real content, not empty."""
        state = _make_debate_state()
        result = debate_node(state)
        for entry in result["debate_history"]:
            assert len(entry["argument"]) > 30, f"{entry['role']} argument too short"

    def test_round_increments(self):
        """Expected: debate_round goes from 0 to 1."""
        state = _make_debate_state()
        result = debate_node(state)
        assert result["debate_round"] == 1


class TestDebateRouting:
    """Conditional edge logic via debate_judge (no LLM needed)."""

    def test_continue_verdict_routes_to_debate(self):
        state = {"debate_judge": {"verdict": "continue"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "debate"

    def test_concluded_verdict_routes_to_risk(self):
        state = {"debate_judge": {"verdict": "concluded"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "risk"

    def test_missing_judge_routes_to_risk(self):
        assert should_continue_debate_with_judge({"debate_round": 2}) == "risk"
