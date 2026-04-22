"""
Sector Agent node.

Determines the stock's industry, how that industry is performing today,
and what the hot / cold sectors and concepts are across the market.
This tells downstream agents whether the stock is riding or fighting
its sector trend.
"""

import logging
from backend.agents.sector.sources import (
    fetch_sector_ranking,
    fetch_concept_ranking,
    fetch_stock_industry,
)

logger = logging.getLogger(__name__)


def sector_node(state: dict) -> dict:
    """Fetch sector / industry context."""
    ticker = state.get("ticker", "")
    exchange = state.get("exchange", "UNKNOWN")

    # Sector / industry rankings via akshare cover A-share boards only.
    # For overseas stocks, skip akshare calls — downstream gets empty sector data.
    if exchange not in ("SH", "SZ", "BJ"):
        logger.info("Sector context skipped for %s (exchange=%s, not A-share)", ticker, exchange)
        return {
            "sector": {
                "stock_industry": {},
                "stock_sector_row": None,
                "top_sectors": [],
                "bottom_sectors": [],
                "top_concepts": [],
                "summary": "Sector context (A-share industry boards) not applicable for overseas stocks.",
            },
            "reasoning_chain": [{
                "agent": "sector",
                "skipped": True,
                "reason": f"exchange={exchange}, not an A-share",
            }],
        }

    logger.info("Fetching sector context for %s", ticker)

    sectors = fetch_sector_ranking(limit=20)
    concepts = fetch_concept_ranking(limit=20)
    stock_industry = fetch_stock_industry(ticker) if ticker else {}

    # Determine this stock's sector ranking
    stock_sector_name = stock_industry.get("industry_name", "")
    stock_sector_row = None
    if stock_sector_name and sectors:
        # Fuzzy match because akshare names may differ
        for i, s in enumerate(sectors):
            if s["name"] in stock_sector_name or stock_sector_name in s["name"]:
                stock_sector_row = {**s, "rank": i + 1}
                break

    top_sectors = sectors[:5]
    bottom_sectors = sectors[-5:] if len(sectors) >= 10 else []
    top_concepts = concepts[:5]

    summary = _build_summary(stock_sector_name, stock_sector_row, top_sectors, bottom_sectors, top_concepts)

    sector_data = {
        "stock_industry": stock_industry,
        "stock_sector_row": stock_sector_row,
        "top_sectors": top_sectors,
        "bottom_sectors": bottom_sectors,
        "top_concepts": top_concepts,
        "summary": summary,
    }

    logger.info("Sector: stock=%s, sector=%s, top sector=%s",
                ticker, stock_sector_name or "unknown",
                top_sectors[0]["name"] if top_sectors else "unknown")

    return {
        "sector": sector_data,
        "reasoning_chain": [{
            "agent": "sector",
            "stock_industry": stock_sector_name or "unknown",
            "stock_sector_change_pct": stock_sector_row.get("change_pct") if stock_sector_row else None,
            "top_sectors": [s["name"] for s in top_sectors],
            "top_concepts": [c["name"] for c in top_concepts],
            "summary": summary[:300],
            "exchange": exchange,
        }],
    }


def _build_summary(stock_sector_name, stock_sector_row, top_sectors, bottom_sectors, top_concepts) -> str:
    parts = []
    if stock_sector_row:
        parts.append(
            f"Stock belongs to {stock_sector_name} (rank {stock_sector_row['rank']}, "
            f"today {stock_sector_row['change_pct']:+.2f}%, "
            f"advance/decline {stock_sector_row['advance']}/{stock_sector_row['decline']})"
        )
    elif stock_sector_name:
        parts.append(f"Stock industry: {stock_sector_name}")
    if top_sectors:
        parts.append(
            "Hot sectors: " + ", ".join(
                f"{s['name']}({s['change_pct']:+.2f}%)" for s in top_sectors[:3]
            )
        )
    if bottom_sectors:
        parts.append(
            "Cold sectors: " + ", ".join(
                f"{s['name']}({s['change_pct']:+.2f}%)" for s in bottom_sectors[:3]
            )
        )
    if top_concepts:
        parts.append(
            "Hot concepts: " + ", ".join(
                f"{c['name']}({c['change_pct']:+.2f}%)" for c in top_concepts[:3]
            )
        )
    return " | ".join(parts) if parts else "No sector data available"
