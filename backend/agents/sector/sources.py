"""
Sector / industry data sources via akshare.

Provides:
  - Current sector ranking (which industries are hot / cold today)
  - Concept (主题) ranking (AI, 新能源, 半导体 etc.)
  - A stock's sector classification (best-effort)
"""

import logging

logger = logging.getLogger(__name__)


def _apply_pd_workaround():
    """Return a context-manager-less token to later restore pandas options."""
    import pandas as pd
    saved = {}
    try:
        saved["infer"] = pd.get_option("future.infer_string")
    except Exception:
        pass
    try:
        saved["storage"] = pd.get_option("mode.string_storage")
    except Exception:
        pass
    try:
        pd.set_option("future.infer_string", False)
    except Exception:
        pass
    try:
        pd.set_option("mode.string_storage", "python")
    except Exception:
        pass
    return saved


def _restore_pd(saved: dict):
    import pandas as pd
    for key, opt in (("infer", "future.infer_string"), ("storage", "mode.string_storage")):
        if key in saved:
            try:
                pd.set_option(opt, saved[key])
            except Exception:
                pass


def fetch_sector_ranking(limit: int = 15) -> list[dict]:
    """
    Fetch top-N sectors (申万 / 东方财富 industry boards) by today's performance.
    Returns list of {name, change_pct, volume, leader}.
    """
    import akshare as ak

    saved = _apply_pd_workaround()
    try:
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            return []
        # Columns: 排名 板块名称 板块代码 最新价 涨跌额 涨跌幅 总市值 换手率 上涨家数 下跌家数 领涨股票 领涨股票涨跌幅
        results = []
        for _, row in df.head(limit).iterrows():
            try:
                results.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "turnover": str(row.get("换手率", "")),
                    "advance": int(row.get("上涨家数", 0) or 0),
                    "decline": int(row.get("下跌家数", 0) or 0),
                    "leader": str(row.get("领涨股票", "")),
                })
            except (ValueError, TypeError):
                continue
        return results
    except Exception as e:
        logger.warning("fetch_sector_ranking failed: %s", e)
        return []
    finally:
        _restore_pd(saved)


def fetch_concept_ranking(limit: int = 15) -> list[dict]:
    """Fetch top-N concept boards (AI / 新能源 / 半导体 / ...) by today's performance."""
    import akshare as ak

    saved = _apply_pd_workaround()
    try:
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            return []
        results = []
        for _, row in df.head(limit).iterrows():
            try:
                results.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                    "leader": str(row.get("领涨股票", "")),
                })
            except (ValueError, TypeError):
                continue
        return results
    except Exception as e:
        logger.warning("fetch_concept_ranking failed: %s", e)
        return []
    finally:
        _restore_pd(saved)


def fetch_stock_industry(ticker: str) -> dict:
    """
    Try to identify which industry board contains this stock.
    Returns {industry_name, industry_change_pct, industry_rank} or {}.
    """
    import akshare as ak

    symbol = ticker.split(".")[0] if "." in ticker else ticker
    if not symbol.isdigit():
        return {}

    saved = _apply_pd_workaround()
    try:
        # Get individual stock info which usually includes the industry
        df = ak.stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            return {}

        # Data is a 2-column DataFrame: item / value
        industry = None
        for _, row in df.iterrows():
            item = str(row.iloc[0])
            value = str(row.iloc[1])
            if "行业" in item or "industry" in item.lower():
                industry = value
                break

        if not industry:
            return {}

        return {"industry_name": industry, "source": "akshare individual_info"}
    except Exception as e:
        logger.warning("fetch_stock_industry failed for %s: %s", symbol, e)
        return {}
    finally:
        _restore_pd(saved)
