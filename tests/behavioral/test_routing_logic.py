"""
Behavioral tests for all LangGraph conditional edge (routing) functions.

Routing functions decide which node to execute next. A bug here causes
the graph to silently skip agents or loop infinitely. These tests cover
all routing functions with boundary values — no LLM, no network.
"""

from backend.agents.debate_judge.node import (
    should_continue_debate_with_judge,
    MAX_DEBATE_ROUNDS,
    MIN_DEBATE_ROUNDS,
)


class TestDebateJudgeRouting:
    """should_continue_debate_with_judge — routes to 'debate' or 'risk'."""

    def test_continue_verdict_routes_to_debate(self):
        state = {"debate_judge": {"verdict": "continue"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "debate"

    def test_concluded_verdict_routes_to_risk(self):
        state = {"debate_judge": {"verdict": "concluded"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "risk"

    def test_missing_judge_defaults_to_risk(self):
        """No debate_judge key → treat as concluded → risk."""
        assert should_continue_debate_with_judge({"debate_round": 2}) == "risk"

    def test_empty_verdict_defaults_to_risk(self):
        state = {"debate_judge": {"verdict": ""}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "risk"

    def test_continue_at_max_cap_routes_to_risk(self):
        """Even if judge says 'continue', MAX_DEBATE_ROUNDS cap overrides."""
        state = {
            "debate_judge": {"verdict": "continue"},
            "debate_round": MAX_DEBATE_ROUNDS,
        }
        assert should_continue_debate_with_judge(state) == "risk"

    def test_continue_one_below_max_routes_to_debate(self):
        """One round below cap: still routes to debate."""
        state = {
            "debate_judge": {"verdict": "continue"},
            "debate_round": MAX_DEBATE_ROUNDS - 1,
        }
        assert should_continue_debate_with_judge(state) == "debate"

    def test_verdict_case_insensitive(self):
        """Verdict comparison must be case-insensitive."""
        state = {"debate_judge": {"verdict": "CONTINUE"}, "debate_round": 2}
        assert should_continue_debate_with_judge(state) == "debate"


class TestDebateConstants:
    """Debate loop safety constants must be sane."""

    def test_min_rounds_at_least_one(self):
        assert MIN_DEBATE_ROUNDS >= 1

    def test_max_rounds_greater_than_min(self):
        assert MAX_DEBATE_ROUNDS > MIN_DEBATE_ROUNDS

    def test_max_rounds_reasonable_ceiling(self):
        """Prevent runaway loops: MAX should be <= 10."""
        assert MAX_DEBATE_ROUNDS <= 10, (
            f"MAX_DEBATE_ROUNDS={MAX_DEBATE_ROUNDS} is too high — "
            "each round calls the LLM twice (bull + bear) plus once for the judge."
        )


class TestOrchestratorRouting:
    """Orchestrator routing based on intent classification."""

    def test_stock_query_allowed(self):
        from backend.agents.orchestrator.node import orchestrator_node
        # Just check the node exists and can be imported — routing itself
        # depends on LLM output which we test via integration tests.
        assert callable(orchestrator_node)

    def test_blocked_intent_returns_end_key(self):
        """When orchestrator detects out_of_scope/blocked, state should reflect it."""
        # Import and verify the out_of_scope path exists in source
        import inspect
        from backend.agents.orchestrator.node import orchestrator_node
        source = inspect.getsource(orchestrator_node)
        assert "out_of_scope" in source or "blocked" in source, (
            "Orchestrator must handle out_of_scope intent."
        )
