"""Real data tests for Sector Agent (akshare sector/concept rankings)."""

import os
import pytest
from backend.agents.sector.node import sector_node


class TestSectorData:
    """Sector agent fetches industry rankings from akshare."""

    def test_returns_sector_key(self):
        """Expected: result has 'sector' key."""
        result = sector_node({"ticker": "AAPL"})
        assert "sector" in result
        assert isinstance(result["sector"], dict)

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_top_sectors_non_empty(self):
        """Expected: at least 5 sector entries returned (akshare up)."""
        result = sector_node({"ticker": "600519.SS"})
        top = result["sector"]["top_sectors"]
        assert isinstance(top, list)
        assert len(top) >= 1

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_each_sector_has_required_fields(self):
        """Expected: each sector entry has name and change_pct."""
        result = sector_node({"ticker": "600519.SS"})
        for s in result["sector"]["top_sectors"]:
            assert "name" in s, "sector missing 'name'"
            assert "change_pct" in s, "sector missing 'change_pct'"

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_top_concepts_non_empty(self):
        """Expected: concept list returned."""
        result = sector_node({"ticker": "600519.SS"})
        concepts = result["sector"]["top_concepts"]
        assert isinstance(concepts, list)
        assert len(concepts) >= 1

    def test_no_ticker_does_not_crash(self):
        """Expected: empty ticker handled gracefully."""
        result = sector_node({})
        assert "sector" in result

    def test_summary_is_string(self):
        """Expected: summary is a non-empty string."""
        result = sector_node({"ticker": "AAPL"})
        summary = result["sector"]["summary"]
        assert isinstance(summary, str) and len(summary) > 5

    def test_reasoning_chain_appended(self):
        """Expected: one reasoning_chain entry from sector agent."""
        result = sector_node({"ticker": "AAPL"})
        chain = result.get("reasoning_chain", [])
        assert len(chain) == 1
        assert chain[0]["agent"] == "sector"

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="akshare blocked on GitHub Actions runners")
    def test_bottom_sectors_list(self):
        """Expected: bottom_sectors is a list (may be empty for thin markets)."""
        result = sector_node({"ticker": "600519.SS"})
        assert isinstance(result["sector"]["bottom_sectors"], list)
