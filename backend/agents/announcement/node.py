"""
Announcement Agent node: fetches company announcements and financial reports
from Chinese financial data sources (akshare / Eastmoney).

Provides structured corporate disclosure data to the analysis pipeline.
"""

import logging
from backend.agents.announcement.sources import fetch_announcements, fetch_financial_summary

logger = logging.getLogger(__name__)


def announcement_node(state: dict) -> dict:
    """Fetch company announcements and financial summary via akshare."""
    ticker = state.get("ticker", "")
    exchange = state.get("exchange", "UNKNOWN")

    if not ticker:
        return {
            "announcements": [],
            "financial_summary": {},
            "errors": [{"agent": "announcement", "error": "No ticker provided"}],
        }

    # Announcements via akshare cover Chinese A-share disclosures only.
    # For HK / US stocks, skip — downstream agents handle empty gracefully.
    if exchange not in ("SH", "SZ", "BJ"):
        logger.info("Announcements skipped for %s (exchange=%s, not A-share)", ticker, exchange)
        return {
            "announcements": [],
            "financial_summary": {},
            "reasoning_chain": [{
                "agent": "announcement",
                "skipped": True,
                "reason": f"exchange={exchange}, not an A-share",
            }],
        }

    logger.info("Fetching announcements for %s", ticker)

    # Fetch announcements
    announcements = fetch_announcements(ticker, limit=8)

    # Fetch financial summary
    fin_summary = fetch_financial_summary(ticker)

    logger.info(
        "Announcements for %s: %d items, financial_summary=%s",
        ticker, len(announcements), "available" if fin_summary else "unavailable",
    )

    return {
        "announcements": announcements,
        "financial_summary": fin_summary,
        "reasoning_chain": [{
            "agent": "announcement",
            "ticker": ticker,
            "announcement_count": len(announcements),
            "has_financial_summary": bool(fin_summary),
            "top_announcements": [a["title"][:80] for a in announcements[:3]],
        }],
    }
