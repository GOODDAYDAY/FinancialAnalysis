"""
ML Contract: LLM model configuration is valid and pinned.

Model governance checks — verifies the system is pointed at the intended
model with sensible token budget and temperature settings.
These run offline; no API call is made.
"""

from backend.config import Settings


class TestModelPinning:
    """Model ID must be pinned to the approved model."""

    def test_default_model_is_deepseek_chat(self):
        """DEEPSEEK_MODEL must default to 'deepseek-chat' — not a test model, not empty."""
        s = Settings()
        assert s.deepseek_model == "deepseek-chat", (
            f"Model default changed to '{s.deepseek_model}'. "
            "Update this test only after deliberate model upgrade review."
        )

    def test_base_url_points_to_deepseek(self):
        """API base URL must route to the approved DeepSeek endpoint."""
        s = Settings()
        assert "deepseek.com" in s.deepseek_base_url, (
            f"Base URL '{s.deepseek_base_url}' does not point to deepseek.com"
        )

    def test_env_override_preserved(self, monkeypatch):
        """DEEPSEEK_MODEL env var must be honoured (supply-chain: can't be silently ignored)."""
        monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
        # BaseSettings reads env vars automatically on instantiation
        s = Settings()
        assert s.deepseek_model == "deepseek-reasoner"


class TestTokenBudget:
    """Token limits must be set to non-zero values to prevent runaway LLM calls."""

    def test_max_tokens_is_positive(self):
        assert Settings().llm_max_tokens > 0

    def test_max_tokens_reasonable_upper_bound(self):
        """Sanity: max_tokens should not exceed 32k (protects against config typos)."""
        assert Settings().llm_max_tokens <= 32_000, (
            f"llm_max_tokens={Settings().llm_max_tokens} looks too high — check config"
        )

    def test_agent_timeout_positive(self):
        assert Settings().agent_timeout > 0


class TestTemperatureSettings:
    """Temperature values must be in the valid range [0, 2]."""

    def test_llm_temperature_range(self):
        s = Settings()
        assert 0.0 <= s.llm_temperature <= 2.0

    def test_debate_temperature_range(self):
        s = Settings()
        assert 0.0 <= s.debate_temperature <= 2.0

    def test_debate_temperature_higher_than_analysis(self):
        """Debate agents use higher temp for creative argument diversity."""
        s = Settings()
        assert s.debate_temperature > s.llm_temperature, (
            "Debate temperature should be higher than base LLM temperature "
            "to generate diverse bull/bear arguments."
        )


class TestDebateConfig:
    """Debate round limits prevent runaway agent loops."""

    def test_debate_max_rounds_positive(self):
        assert Settings().debate_max_rounds >= 1

    def test_debate_max_rounds_has_ceiling(self):
        """Safety cap: should not exceed MAX_DEBATE_ROUNDS defined in debate_judge."""
        from backend.agents.debate_judge.node import MAX_DEBATE_ROUNDS
        assert Settings().debate_max_rounds <= MAX_DEBATE_ROUNDS, (
            f"config.debate_max_rounds ({Settings().debate_max_rounds}) exceeds "
            f"judge MAX_DEBATE_ROUNDS ({MAX_DEBATE_ROUNDS})"
        )
