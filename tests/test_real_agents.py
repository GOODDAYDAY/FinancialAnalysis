"""
真实 Agent 测试 — 无 mock，直接调用 DeepSeek API + yfinance。
每个 agent 单独测试，预定义输入，验证输出结构和合理性。
针对中国 A 股。
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))


# ═══════════════════════════════════════════════════════════
# Agent 1: Market Data — 真实 yfinance 数据
# ═══════════════════════════════════════════════════════════

def test_market_data_agent(ticker: str, name: str):
    """测试 Market Data Agent 能否获取真实股票数据。"""
    from backend.agents.market_data import market_data_node

    print(f"\n{'='*60}")
    print(f"[Market Data] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = market_data_node({"ticker": ticker})
    elapsed = time.time() - start

    md = result.get("market_data", {})
    print(f"  价格: {md.get('current_price')}")
    print(f"  涨跌幅: {md.get('price_change_pct')}%")
    print(f"  P/E: {md.get('pe_ratio')}")
    print(f"  RSI(14): {md.get('rsi_14')}")
    print(f"  SMA20: {md.get('sma_20')}")
    print(f"  SMA50: {md.get('sma_50')}")
    print(f"  信号: {md.get('technical_signals')}")
    print(f"  Mock: {md.get('is_mock')}")
    print(f"  耗时: {elapsed:.1f}s")

    # 验证
    assert md.get("current_price") is not None, f"{ticker} 价格为空"
    assert md.get("current_price") > 0, f"{ticker} 价格非正数: {md.get('current_price')}"
    errors = result.get("errors", [])
    assert len(errors) == 0, f"Errors: {errors}"
    print(f"  结果: PASS")
    return md


# ═══════════════════════════════════════════════════════════
# Agent 2: News — 真实新闻获取
# ═══════════════════════════════════════════════════════════

def test_news_agent(ticker: str, name: str):
    """测试 News Agent 能否获取新闻。"""
    from backend.agents.news import news_node

    print(f"\n{'='*60}")
    print(f"[News] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = news_node({"ticker": ticker})
    elapsed = time.time() - start

    articles = result.get("news_articles", [])
    print(f"  文章数: {len(articles)}")
    for a in articles[:3]:
        print(f"    - [{a.get('source')}] {a.get('title', '')[:60]}")
    print(f"  耗时: {elapsed:.1f}s")

    assert len(articles) > 0, f"{ticker} 没有获取到任何新闻"
    print(f"  结果: PASS")
    return articles


# ═══════════════════════════════════════════════════════════
# Agent 3: Sentiment — 真实 LLM 情感分析
# ═══════════════════════════════════════════════════════════

def test_sentiment_agent(ticker: str, name: str, articles: list):
    """测试 Sentiment Agent 的真实 LLM 情感分析。"""
    from backend.agents.sentiment import sentiment_node

    print(f"\n{'='*60}")
    print(f"[Sentiment] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = sentiment_node({"ticker": ticker, "news_articles": articles})
    elapsed = time.time() - start

    s = result.get("sentiment", {})
    print(f"  评分: {s.get('overall_score')}")
    print(f"  标签: {s.get('overall_label')}")
    print(f"  置信度: {s.get('confidence')}")
    print(f"  推理: {s.get('reasoning', '')[:150]}")
    print(f"  关键因素: {s.get('key_factors', [])}")
    print(f"  耗时: {elapsed:.1f}s")

    assert s.get("overall_score") is not None, "情感评分为空"
    assert -1.0 <= s.get("overall_score", 0) <= 1.0, f"评分越界: {s.get('overall_score')}"
    assert s.get("overall_label") in ("bullish", "bearish", "neutral"), f"标签异常: {s.get('overall_label')}"
    assert len(s.get("reasoning", "")) > 10, "推理链为空"
    print(f"  结果: PASS")
    return s


# ═══════════════════════════════════════════════════════════
# Agent 4: Fundamental — 真实基本面分析
# ═══════════════════════════════════════════════════════════

def test_fundamental_agent(ticker: str, name: str, market_data: dict):
    """测试 Fundamental Agent 的真实 LLM 分析。"""
    from backend.agents.fundamental import fundamental_node

    print(f"\n{'='*60}")
    print(f"[Fundamental] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = fundamental_node({"ticker": ticker, "market_data": market_data})
    elapsed = time.time() - start

    f = result.get("fundamental", {})
    print(f"  健康分: {f.get('health_score')}/10")
    print(f"  总结: {f.get('summary', '')[:150]}")
    print(f"  红旗: {f.get('red_flags', [])}")
    print(f"  耗时: {elapsed:.1f}s")

    assert f.get("health_score") is not None, "健康分为空"
    assert 1.0 <= f.get("health_score", 0) <= 10.0, f"健康分越界: {f.get('health_score')}"
    print(f"  结果: PASS")
    return f


# ═══════════════════════════════════════════════════════════
# Agent 5: Debate — 真实 Bull vs Bear 对打
# ═══════════════════════════════════════════════════════════

def test_debate_agent(ticker: str, name: str, market_data: dict, sentiment: dict, fundamental: dict):
    """测试 Debate Agent 的真实多轮辩论。"""
    from backend.agents.debate import debate_node

    print(f"\n{'='*60}")
    print(f"[Debate] {name} ({ticker})")
    print(f"{'='*60}")

    state = {
        "ticker": ticker,
        "debate_round": 0,
        "debate_history": [],
        "market_data": market_data,
        "sentiment": sentiment,
        "fundamental": fundamental,
        "reasoning_chain": [],
    }

    # Round 1
    start = time.time()
    r1 = debate_node(state)
    elapsed1 = time.time() - start

    history = r1.get("debate_history", [])
    print(f"  Round 1 ({elapsed1:.1f}s):")
    for h in history:
        print(f"    [{h.get('role','?').upper()}] {h.get('argument','')[:100]}")
        print(f"      要点: {h.get('key_points', [])[:3]}")

    assert len(history) >= 2, f"Round 1 应有 2 条辩论，实际 {len(history)}"

    # Round 2
    state2 = {**state, "debate_round": 1, "debate_history": history, "reasoning_chain": r1.get("reasoning_chain", [])}
    start2 = time.time()
    r2 = debate_node(state2)
    elapsed2 = time.time() - start2

    history2 = r2.get("debate_history", [])
    print(f"  Round 2 ({elapsed2:.1f}s):")
    for h in history2:
        print(f"    [{h.get('role','?').upper()}] {h.get('argument','')[:100]}")
        print(f"      反驳: {h.get('rebuttals', [])[:2]}")

    assert len(history2) >= 2, f"Round 2 应有 2 条辩论，实际 {len(history2)}"
    print(f"  总耗时: {elapsed1+elapsed2:.1f}s")
    print(f"  结果: PASS")
    return history + history2


# ═══════════════════════════════════════════════════════════
# Agent 6: Risk — 真实风险评估
# ═══════════════════════════════════════════════════════════

def test_risk_agent(ticker: str, name: str, market_data: dict, sentiment: dict, fundamental: dict):
    """测试 Risk Agent 的真实风险评估。"""
    from backend.agents.risk import risk_node

    print(f"\n{'='*60}")
    print(f"[Risk] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = risk_node({
        "ticker": ticker,
        "market_data": market_data,
        "sentiment": sentiment,
        "fundamental": fundamental,
    })
    elapsed = time.time() - start

    r = result.get("risk", {})
    print(f"  风险分: {r.get('risk_score')}/10")
    print(f"  等级: {r.get('risk_level')}")
    print(f"  因素: {r.get('risk_factors', [])}")
    print(f"  耗时: {elapsed:.1f}s")

    assert r.get("risk_score") is not None, "风险分为空"
    assert 1.0 <= r.get("risk_score", 0) <= 10.0, f"风险分越界: {r.get('risk_score')}"
    print(f"  结果: PASS")
    return r


# ═══════════════════════════════════════════════════════════
# Agent 7: Advisory — 真实推荐综合
# ═══════════════════════════════════════════════════════════

def test_advisory_agent(ticker: str, name: str, market_data: dict, sentiment: dict,
                        fundamental: dict, risk: dict, debate_history: list):
    """测试 Advisory Agent 的真实推荐综合。"""
    from backend.agents.advisory import advisory_node

    print(f"\n{'='*60}")
    print(f"[Advisory] {name} ({ticker})")
    print(f"{'='*60}")

    start = time.time()
    result = advisory_node({
        "ticker": ticker,
        "market_data": market_data,
        "sentiment": sentiment,
        "fundamental": fundamental,
        "risk": risk,
        "debate_history": debate_history,
        "reasoning_chain": [],
    })
    elapsed = time.time() - start

    rec = result.get("recommendation", {})
    print(f"  推荐: {rec.get('recommendation')}")
    print(f"  置信度: {rec.get('confidence')}")
    print(f"  周期: {rec.get('investment_horizon')}")
    print(f"  看多因素: {rec.get('supporting_factors', [])}")
    print(f"  看空因素: {rec.get('dissenting_factors', [])}")
    print(f"  辩论总结: {rec.get('debate_summary', '')[:150]}")
    print(f"  耗时: {elapsed:.1f}s")

    assert rec.get("recommendation") in ("buy", "hold", "sell"), f"推荐值异常: {rec.get('recommendation')}"
    assert 0.0 <= rec.get("confidence", 0) <= 1.0, f"置信度越界: {rec.get('confidence')}"
    assert rec.get("disclaimer"), "缺少合规声明"
    print(f"  结果: PASS")
    return rec


# ═══════════════════════════════════════════════════════════
# 完整单股测试
# ═══════════════════════════════════════════════════════════

def run_full_stock_test(ticker: str, name: str):
    """对单只股票跑全部 7 个 Agent 的真实测试。"""
    print(f"\n{'#'*60}")
    print(f"  完整测试: {name} ({ticker})")
    print(f"{'#'*60}")

    total_start = time.time()

    md = test_market_data_agent(ticker, name)
    articles = test_news_agent(ticker, name)
    sentiment = test_sentiment_agent(ticker, name, articles)
    fundamental = test_fundamental_agent(ticker, name, md)
    debate_history = test_debate_agent(ticker, name, md, sentiment, fundamental)
    risk = test_risk_agent(ticker, name, md, sentiment, fundamental)
    rec = test_advisory_agent(ticker, name, md, sentiment, fundamental, risk, debate_history)

    total_elapsed = time.time() - total_start

    print(f"\n{'='*60}")
    print(f"  {name} ({ticker}) 完整测试完成")
    print(f"  最终推荐: {rec.get('recommendation')} (置信度 {rec.get('confidence')})")
    print(f"  总耗时: {total_elapsed:.1f}s")
    print(f"  全部 7 个 Agent: PASS")
    print(f"{'='*60}")

    return {
        "ticker": ticker, "name": name,
        "price": md.get("current_price"),
        "sentiment": sentiment.get("overall_label"),
        "health": fundamental.get("health_score"),
        "risk": risk.get("risk_score"),
        "recommendation": rec.get("recommendation"),
        "confidence": rec.get("confidence"),
        "time": round(total_elapsed, 1),
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # 从命令行接收 ticker 和 name
    ticker = sys.argv[1] if len(sys.argv) > 1 else "300565.SZ"
    name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
    result = run_full_stock_test(ticker, name)
    print(f"\nRESULT_JSON: {json.dumps(result, ensure_ascii=False)}")
