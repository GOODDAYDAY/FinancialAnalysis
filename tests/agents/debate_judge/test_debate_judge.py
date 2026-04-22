"""Tests for Debate Judge Agent — deterministic branches + real LLM path."""

from backend.agents.debate_judge.node import (
    debate_judge_node,
    should_continue_debate_with_judge,
    MIN_DEBATE_ROUNDS,
    MAX_DEBATE_ROUNDS,
)
from backend.agents.debate.node import debate_node
from backend.agents.market_data.node import market_data_node


# ---------------------------------------------------------------------------
# Deterministic branches (no LLM call)
# ---------------------------------------------------------------------------

class TestJudgeDeterministicBranches:
    """Safety floor and ceiling handled without LLM."""

    def test_below_min_rounds_auto_continues(self):
        """Expected: judge auto-continues without LLM when round < MIN."""
        state = {"ticker": "600519.SS", "debate_history": [], "debate_round": 0}
        result = debate_judge_node(state)
        assert result["debate_judge"]["verdict"] == "continue"
        assert "Minimum" in result["debate_judge"]["reason"]

    def test_at_max_rounds_auto_concludes(self):
        """Expected: judge forces conclusion when round >= MAX."""
        state = {
            "ticker": "600519.SS",
            "debate_history": [],
            "debate_round": MAX_DEBATE_ROUNDS,
        }
        result = debate_judge_node(state)
        assert result["debate_judge"]["verdict"] == "concluded"
        assert "cap" in result["debate_judge"]["reason"].lower() or "Safety" in result["debate_judge"]["reason"]

    def test_reasoning_chain_appended_below_min(self):
        """Expected: reasoning_chain has one entry even for fast paths."""
        state = {"ticker": "TEST", "debate_history": [], "debate_round": 0}
        result = debate_judge_node(state)
        chain = result.get("reasoning_chain", [])
        assert len(chain) == 1
        assert chain[0]["agent"] == "debate_judge"

    def test_output_fields_present(self):
        """Expected: all required keys in debate_judge dict."""
        state = {"ticker": "TEST", "debate_history": [], "debate_round": 0}
        dj = debate_judge_node(state)["debate_judge"]
        for key in ("verdict", "quality_score", "reason", "unresolved_points",
                    "bull_strength", "bear_strength", "round_evaluated"):
            assert key in dj, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Routing function
# ---------------------------------------------------------------------------

class TestJudgeRouting:
    """should_continue_debate_with_judge conditional edge."""

    def test_continue_verdict_routes_to_debate(self):
        state = {"debate_judge": {"verdict": "continue"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "debate"

    def test_concluded_verdict_routes_to_risk(self):
        state = {"debate_judge": {"verdict": "concluded"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "risk"

    def test_missing_judge_routes_to_risk(self):
        """Expected: no debate_judge key defaults to 'concluded' path."""
        assert should_continue_debate_with_judge({"debate_round": 2}) == "risk"

    def test_continue_at_max_routes_to_risk(self):
        """Expected: even if judge says continue, max cap overrides."""
        state = {
            "debate_judge": {"verdict": "continue"},
            "debate_round": MAX_DEBATE_ROUNDS,
        }
        assert should_continue_debate_with_judge(state) == "risk"


# ---------------------------------------------------------------------------
# Real LLM path (requires DeepSeek key + network)
# ---------------------------------------------------------------------------

class TestJudgeWithRealDebate:
    """Judge evaluates a real debate transcript via LLM."""

    def test_judge_evaluates_real_debate(self):
        """Expected: judge returns valid verdict after 2 real debate rounds."""
        md = market_data_node({"ticker": "600519.SS"})
        base = {
            "ticker": "600519.SS",
            "market_data": md["market_data"],
            "sentiment": {"overall_score": 0.3, "overall_label": "bullish",
                          "key_factors": ["steady earnings"], "reasoning": "OK"},
            "fundamental": {"health_score": 7.5, "red_flags": [], "summary": "Solid"},
            "quant": {"score": 15, "verdict": "MODERATE BUY", "signals": [],
                      "bullish_count": 2, "bearish_count": 1, "summary": "Moderate"},
            "announcements": [],
            "social_sentiment": {"summary": ""},
            "reasoning_chain": [],
            "language": "en",
        }

        # Run 2 real debate rounds to get a transcript
        base["debate_round"] = 0
        base["debate_history"] = []
        r1 = debate_node(base)
        base["debate_history"] = r1["debate_history"]
        base["debate_round"] = 1
        r2 = debate_node(base)
        base["debate_history"] = r2["debate_history"]
        base["debate_round"] = MIN_DEBATE_ROUNDS  # 2 — within judge evaluation range

        result = debate_judge_node(base)
        dj = result["debate_judge"]

        assert dj["verdict"] in ("continue", "concluded")
        assert 0 <= dj["quality_score"] <= 100
        assert 0 <= dj["bull_strength"] <= 100
        assert 0 <= dj["bear_strength"] <= 100
        assert isinstance(dj["reason"], str) and len(dj["reason"]) > 5
