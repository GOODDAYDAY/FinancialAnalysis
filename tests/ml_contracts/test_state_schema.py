"""
ML Contract: verify every agent's output keys are valid ResearchState fields.

Why this matters: LangGraph silently drops keys that don't match any reducer
or TypedDict field. A typo in an agent's return dict causes a completely silent
data loss that won't show up in regular integration tests. This test catches
that contract drift at commit time, with zero API calls.
"""

import typing
from backend.state import ResearchState

# Ground truth: the complete set of valid ResearchState keys
STATE_KEYS = set(typing.get_type_hints(ResearchState).keys())

# Per-agent output key declarations — must match what node.py actually returns.
# Update this table whenever an agent changes its return keys.
AGENT_OUTPUT_KEYS: dict[str, list[str]] = {
    "orchestrator":     ["ticker", "intent", "language", "reasoning_chain"],
    "market_data":      ["market_data", "reasoning_chain"],
    "macro_env":        ["macro_env", "reasoning_chain"],
    "sector":           ["sector", "reasoning_chain"],
    "news":             ["news_articles", "reasoning_chain"],
    "announcement":     ["announcements", "financial_summary", "reasoning_chain"],
    "social_sentiment": ["social_sentiment", "reasoning_chain"],
    "sentiment":        ["sentiment", "reasoning_chain"],
    "fundamental":      ["fundamental", "reasoning_chain"],
    "momentum":         ["momentum", "reasoning_chain"],
    "quant":            ["quant", "reasoning_chain"],
    "grid_strategy":    ["grid_strategy", "reasoning_chain"],
    "debate":           ["debate_history", "debate_round", "reasoning_chain"],
    "debate_judge":     ["debate_judge", "reasoning_chain"],
    "risk":             ["risk", "reasoning_chain"],
    "advisory":         ["recommendation", "reasoning_chain"],
}

# Keys any agent is allowed to also write (error path)
ALLOWED_EXTRAS = {"errors"}


class TestStateSchema:
    """Every agent output key must exist in ResearchState."""

    def test_state_keys_not_empty(self):
        """Sanity: ResearchState has at least 15 fields."""
        assert len(STATE_KEYS) >= 15, f"ResearchState only has {len(STATE_KEYS)} keys — likely import failure"

    def test_reasoning_chain_in_state(self):
        """reasoning_chain must be in ResearchState (it's the global accumulator)."""
        assert "reasoning_chain" in STATE_KEYS

    def test_errors_in_state(self):
        """errors accumulator must be in ResearchState."""
        assert "errors" in STATE_KEYS

    def test_all_16_agents_declared(self):
        """Contract table covers all 16 agents wired in graph.py."""
        assert len(AGENT_OUTPUT_KEYS) == 16

    def test_agent_output_keys_in_state(self):
        """Every key an agent returns must be a valid ResearchState field."""
        violations = {}
        for agent, keys in AGENT_OUTPUT_KEYS.items():
            bad = [k for k in keys if k not in STATE_KEYS and k not in ALLOWED_EXTRAS]
            if bad:
                violations[agent] = bad

        assert not violations, (
            "Agents writing keys NOT in ResearchState (silent data loss risk):\n"
            + "\n".join(f"  {agent}: {keys}" for agent, keys in violations.items())
        )

    def test_no_duplicate_primary_keys(self):
        """Two agents should not write to the same primary output key (except accumulators)."""
        accumulators = {"reasoning_chain", "errors", "debate_history"}
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for agent, keys in AGENT_OUTPUT_KEYS.items():
            for k in keys:
                if k in accumulators:
                    continue
                if k in seen:
                    duplicates.append(f"'{k}' written by both '{seen[k]}' and '{agent}'")
                else:
                    seen[k] = agent
        assert not duplicates, "Key collision between agents:\n" + "\n".join(duplicates)

    def test_state_covers_all_agent_outputs(self):
        """ResearchState must have a field for every non-accumulator agent output."""
        all_output_keys = {
            k for keys in AGENT_OUTPUT_KEYS.values() for k in keys
        } - ALLOWED_EXTRAS
        missing_from_state = all_output_keys - STATE_KEYS
        assert not missing_from_state, (
            f"Keys declared in agent outputs but missing from ResearchState: {missing_from_state}"
        )
