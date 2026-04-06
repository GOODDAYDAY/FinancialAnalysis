"""
Announcement data sources using akshare (Eastmoney backend).

Fetches company announcements, financial reports, and analyst research
for Chinese A-share stocks. Free, no API key required.
"""

import logging

logger = logging.getLogger(__name__)


def fetch_announcements(ticker: str, limit: int = 10) -> list[dict]:
    """
    Fetch recent company announcements from Eastmoney via akshare.
    Returns a list of dicts with title, date, content, source.
    """
    try:
        import akshare as ak

        # Normalize ticker: "600519.SS" -> "600519", "000858.SZ" -> "000858"
        symbol = _normalize_ticker(ticker)
        if not symbol:
            logger.warning("Cannot normalize ticker %s for akshare", ticker)
            return []

        # Fetch stock news from Caixin via akshare (more reliable than stock_news_em)
        try:
            df = ak.stock_news_main_cx()
            if df is not None and not df.empty:
                results = []
                for _, row in df.head(limit).iterrows():
                    results.append({
                        "title": str(row.iloc[0]) if len(row) > 0 else "Untitled",
                        "date": str(row.iloc[1]) if len(row) > 1 else "",
                        "content": str(row.iloc[2])[:500] if len(row) > 2 else "",
                        "source": "Caixin Finance (akshare)",
                        "type": "news",
                    })
                logger.info("Fetched %d news items from Caixin", len(results))
                return results
        except Exception as e2:
            logger.warning("Caixin news also failed: %s", e2)

        # Fallback: fetch general market report disclosure
        try:
            df = ak.stock_report_disclosure(symbol="沪深", market="全部")
            if df is not None and not df.empty:
                match = df[df.iloc[:, 0].astype(str).str.contains(symbol)]
                results = []
                for _, row in match.head(limit).iterrows():
                    results.append({
                        "title": str(row.iloc[2]) if len(row) > 2 else "Report",
                        "date": str(row.iloc[3]) if len(row) > 3 else "",
                        "content": "",
                        "source": "Stock Report Disclosure (akshare)",
                        "type": "disclosure",
                    })
                return results
        except Exception as e3:
            logger.warning("Report disclosure also failed: %s", e3)

        logger.info("Fetched %d announcements for %s", len(results), symbol)
        return results

    except Exception as e:
        logger.warning("Failed to fetch announcements for %s: %s", ticker, e)
        return []


def fetch_financial_summary(ticker: str) -> dict:
    """
    Fetch key financial metrics from akshare.
    Returns a dict with revenue, profit, ROE, etc.
    """
    try:
        import akshare as ak

        symbol = _normalize_ticker(ticker)
        if not symbol:
            return {}

        # Fetch financial abstract from Eastmoney
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
        if df is None or df.empty:
            return {}

        # Get the most recent row
        latest = df.iloc[0]
        return {
            "source": "akshare (THS Financial Abstract)",
            "report_date": str(latest.get("报告期", "")),
            "revenue": str(latest.get("营业总收入", "N/A")),
            "net_profit": str(latest.get("净利润", "N/A")),
            "roe": str(latest.get("净资产收益率", "N/A")),
            "gross_margin": str(latest.get("销售毛利率", "N/A")),
            "debt_ratio": str(latest.get("资产负债率", "N/A")),
        }

    except Exception as e:
        logger.warning("Failed to fetch financial summary for %s: %s", ticker, e)
        return {}


def _normalize_ticker(ticker: str) -> str:
    """
    Normalize ticker format for akshare.
    '600519.SS' -> '600519', '000858.SZ' -> '000858',
    '0700.HK' -> '' (not supported)
    """
    ticker = ticker.strip().upper()

    # Remove exchange suffix
    for suffix in [".SS", ".SZ", ".SH"]:
        if ticker.endswith(suffix):
            return ticker[:-len(suffix)]

    # If it's just digits, return as-is
    if ticker.replace(".", "").isdigit():
        return ticker.split(".")[0]

    # Hong Kong stocks not supported by these akshare functions
    if ".HK" in ticker:
        return ""

    return ticker
