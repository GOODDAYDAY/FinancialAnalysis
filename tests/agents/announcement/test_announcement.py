"""Real API tests for Announcement Agent (akshare)."""

from backend.agents.announcement.node import announcement_node


class TestAnnouncements:
    """Fetch real company data from akshare."""

    def test_financial_summary_for_moutai(self):
        """Expected: financial summary with ROE for blue chip stock."""
        result = announcement_node({"ticker": "600519.SS"})
        fin = result.get("financial_summary", {})
        assert fin, "Financial summary should not be empty for Moutai"
        assert fin.get("roe"), "ROE should be present"

    def test_reasoning_chain_recorded(self):
        result = announcement_node({"ticker": "600519.SS"})
        agents = [s["agent"] for s in result.get("reasoning_chain", [])]
        assert "announcement" in agents

    def test_hk_stock_graceful_fallback(self):
        """Expected: HK stocks not supported by akshare, should not crash."""
        result = announcement_node({"ticker": "0700.HK"})
        assert result is not None  # No crash
