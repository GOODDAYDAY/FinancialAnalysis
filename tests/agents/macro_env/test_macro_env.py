"""Real data tests for Macro Environment Agent (akshare index data)."""

import os
import pytest
from backend.agents.macro_env.node import macro_env_node


class TestMacroEnvData:
    """Macro env fetches real index snapshots from akshare."""

    def test_returns_macro_env_key(self):
        """Expected: result has 'macro_env' key with dict value."""
        result = macro_env_node({})
        assert "macro_env" in result
        assert isinstance(result["macro_env"], dict)

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_overall_regime_is_valid(self):
        """Expected: overall_regime is one of the three known labels."""
        result = macro_env_node({})
        regime = result["macro_env"]["overall_regime"]
        assert regime in ("BULL MARKET", "BEAR MARKET", "SIDEWAYS / MIXED")

    def test_primary_regime_present(self):
        """Expected: primary_regime is a non-empty string."""
        result = macro_env_node({})
        primary = result["macro_env"]["primary_regime"]
        assert isinstance(primary, str) and len(primary) > 0

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_indices_non_empty(self):
        """Expected: at least one index returned (akshare up)."""
        result = macro_env_node({})
        indices = result["macro_env"]["indices"]
        assert isinstance(indices, dict)
        assert len(indices) >= 1

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_each_index_has_required_fields(self):
        """Expected: name, price, change_pct, regime on every index entry."""
        result = macro_env_node({})
        for sym, idx in result["macro_env"]["indices"].items():
            assert "name" in idx, f"{sym} missing 'name'"
            assert "price" in idx, f"{sym} missing 'price'"
            assert "change_pct" in idx, f"{sym} missing 'change_pct'"
            assert "regime" in idx, f"{sym} missing 'regime'"

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_summary_is_non_empty(self):
        """Expected: human-readable summary string produced."""
        result = macro_env_node({})
        summary = result["macro_env"]["summary"]
        assert isinstance(summary, str) and len(summary) > 10

    def test_reasoning_chain_appended(self):
        """Expected: reasoning_chain has one entry from macro_env agent."""
        result = macro_env_node({})
        chain = result.get("reasoning_chain", [])
        assert len(chain) == 1
        assert chain[0]["agent"] == "macro_env"

    def test_counts_non_negative(self):
        """Expected: bull/bear/sideways counts are non-negative integers."""
        result = macro_env_node({})
        macro = result["macro_env"]
        assert macro["bull_count"] >= 0
        assert macro["bear_count"] >= 0
        assert macro["sideways_count"] >= 0
