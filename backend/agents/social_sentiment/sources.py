"""
Social sentiment data sources using akshare (Eastmoney backend).

Fetches stock comment sentiment, popularity rankings, and
institutional attention data from Chinese financial platforms.
All free, no API key required.
"""

import logging

logger = logging.getLogger(__name__)


def fetch_stock_comments(ticker: str) -> dict:
    """
    Fetch stock comment sentiment data from Eastmoney via akshare.
    Returns sentiment distribution (bullish/bearish/neutral percentages).
    """
    try:
        import akshare as ak

        # akshare stock comment function uses raw code like "600519"
        symbol = _normalize_ticker(ticker)
        if not symbol:
            return {}

        # Eastmoney stock comment sentiment
        df = ak.stock_comment_em()
        if df is None or df.empty:
            return {}

        # Find the row matching our stock
        match = df[df["代码"].astype(str).str.contains(symbol)]
        if match.empty:
            logger.info("No comment data found for %s in Eastmoney", symbol)
            return {}

        row = match.iloc[0]
        return {
            "source": "Eastmoney Stock Comments",
            "stock_name": str(row.get("名称", "")),
            "overall_score": float(row.get("综合得分", 0)) if row.get("综合得分") else 0,
            "attention_rank": str(row.get("关注指数", "N/A")),
            "raw_data": {k: str(v) for k, v in row.to_dict().items()},
        }

    except Exception as e:
        logger.warning("Failed to fetch stock comments for %s: %s", ticker, e)
        return {}


def fetch_hot_stocks() -> list[dict]:
    """
    Fetch current hot/trending stocks from Eastmoney.
    Returns a list of trending stock entries.
    """
    try:
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(20).iterrows():
            results.append({
                "rank": int(row.get("当前排名", 0)) if row.get("当前排名") else 0,
                "code": str(row.get("代码", "")),
                "name": str(row.get("股票名称", "")),
            })
        return results

    except Exception as e:
        logger.warning("Failed to fetch hot stocks: %s", e)
        return []


def fetch_individual_stock_hotrank(ticker: str) -> dict:
    """
    Fetch individual stock hotness/attention ranking from Eastmoney.
    """
    try:
        import akshare as ak

        symbol = _normalize_ticker(ticker)
        if not symbol:
            return {}

        df = ak.stock_hot_rank_detail_em(symbol=symbol)
        if df is None or df.empty:
            return {}

        # Get latest data point
        latest = df.iloc[-1]
        return {
            "source": "Eastmoney Hot Rank",
            "rank": str(latest.get("当前排名", "N/A") if "当前排名" in df.columns else "N/A"),
            "new_rank": str(latest.get("新晋粉丝", "N/A") if "新晋粉丝" in df.columns else "N/A"),
            "data_points": len(df),
        }

    except Exception as e:
        logger.warning("Failed to fetch hot rank for %s: %s", ticker, e)
        return {}


def _normalize_ticker(ticker: str) -> str:
    """Normalize ticker format for akshare. '600519.SS' -> '600519'."""
    ticker = ticker.strip().upper()
    for suffix in [".SS", ".SZ", ".SH"]:
        if ticker.endswith(suffix):
            return ticker[:-len(suffix)]
    if ticker.replace(".", "").isdigit():
        return ticker.split(".")[0]
    if ".HK" in ticker:
        return ""
    return ticker
