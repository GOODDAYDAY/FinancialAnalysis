"""
ML Contract: LLM agent system prompts are non-empty and structurally valid.

Prompt engineering is a first-class artifact. An accidentally blanked prompt,
a missing role description, or a removed constraint silently degrades output
quality in ways that won't cause Python exceptions. These checks catch that
at commit time.

All checks are source-level (AST/text scan) — no LLM calls.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "backend" / "agents"

# Agents that call an LLM and must have a system_prompt variable
LLM_AGENTS = [
    "orchestrator",
    "sentiment",
    "fundamental",
    "debate",
    "debate_judge",
    "risk",
    "advisory",
    "followup",
]

# Minimum character length for a meaningful system prompt
MIN_PROMPT_CHARS = 80


def _read_node(agent_name: str) -> str:
    path = AGENTS_DIR / agent_name / "node.py"
    assert path.exists(), f"Missing node.py for LLM agent '{agent_name}': {path}"
    return path.read_text(encoding="utf-8")


class TestSystemPromptPresence:
    """Every LLM-using agent must define a system_prompt."""

    def test_all_llm_agents_have_system_prompt(self):
        missing = []
        for agent in LLM_AGENTS:
            source = _read_node(agent)
            if "system_prompt" not in source:
                missing.append(agent)
        assert not missing, f"Agents missing 'system_prompt' variable: {missing}"

    def test_system_prompts_are_not_empty_strings(self):
        """Guard against accidental `system_prompt = ''` commits."""
        empty_prompt_pattern = re.compile(r'system_prompt\s*=\s*["\'\s]{0,3}$', re.MULTILINE)
        found_empty = []
        for agent in LLM_AGENTS:
            source = _read_node(agent)
            if empty_prompt_pattern.search(source):
                found_empty.append(agent)
        assert not found_empty, f"Agents with suspiciously short system_prompt: {found_empty}"

    def test_advisory_prompt_contains_weight_directive(self):
        """Advisory system prompt must contain the weighting scheme (explainability requirement)."""
        source = _read_node("advisory")
        assert "%" in source and ("Momentum" in source or "momentum" in source), (
            "Advisory system_prompt appears to be missing the dimension-weighting section. "
            "This is required for explainable recommendations."
        )

    def test_advisory_prompt_has_override_caution(self):
        """Advisory prompt must warn against SELL on rising stocks (core responsible-AI rule)."""
        source = _read_node("advisory")
        assert "SELL" in source and ("momentum" in source.lower() or "rising" in source.lower()), (
            "Advisory system_prompt is missing the anti-SELL-on-rising-stock guard."
        )

    def test_debate_judge_prompt_has_criteria(self):
        """Debate judge must have explicit continue/concluded criteria."""
        source = _read_node("debate_judge")
        assert "continue" in source and "concluded" in source, (
            "debate_judge system_prompt must specify both 'continue' and 'concluded' criteria."
        )

    def test_risk_agent_prompt_present(self):
        source = _read_node("risk")
        assert "system_prompt" in source

    def test_no_agent_uses_empty_user_role(self):
        """
        Prompt injection mitigation: orchestrator must block out_of_scope intent
        before any LLM agent sees the user's raw text.
        """
        orchestrator_source = _read_node("orchestrator")
        assert "out_of_scope" in orchestrator_source or "blocked" in orchestrator_source, (
            "Orchestrator must handle out-of-scope intent to prevent prompt injection reach."
        )


class TestDisclaimerIntegrity:
    """RecommendationOutput.disclaimer is a hardcoded Pydantic default — not LLM-generated."""

    def test_disclaimer_is_pydantic_default_not_llm(self):
        """Disclaimer must be set as a Pydantic field default in state.py, not in advisory prompt."""
        state_py = (REPO_ROOT / "backend" / "state.py").read_text(encoding="utf-8")
        assert "disclaimer" in state_py, "RecommendationOutput.disclaimer must be declared in state.py"
        # Verify it's not assignable via advisory prompt (i.e., advisory prompt doesn't mention 'disclaimer')
        advisory_source = _read_node("advisory")
        # The advisory agent may reference disclaimer in logging but should not construct it
        assert "disclaimer =" not in advisory_source, (
            "Advisory node is constructing the disclaimer — it must be a Pydantic default only."
        )
