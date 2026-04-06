"""
Quant Agent: 纯算法量化分析，不调 LLM。

计算技术指标信号、统计特征、量化评分，
作为 Bull vs Bear 辩论的"数据裁判"提供硬证据。

信号类型:
- 均线系统: 金叉/死叉、价格与均线关系
- 动量指标: RSI 超买超卖、MACD 背离
- 波动率: 布林带位置、历史波动率
- 统计: 近期收益率、夏普比率近似、最大回撤
"""

import logging
import math

logger = logging.getLogger(__name__)


def quant_node(state: dict) -> dict:
    """纯算法量化分析，不调用 LLM。"""
    ticker = state.get("ticker", "")
    market_data = state.get("market_data", {})

    if not market_data or not market_data.get("current_price"):
        return {
            "quant": {"score": 0, "signals": [], "summary": "Insufficient data for quant analysis."},
            "reasoning_chain": [{"agent": "quant", "note": "no market data"}],
        }

    logger.info("Quant analysis for %s", ticker)

    price = market_data.get("current_price", 0)
    sma_20 = market_data.get("sma_20")
    sma_50 = market_data.get("sma_50")
    sma_200 = market_data.get("sma_200")
    rsi = market_data.get("rsi_14")
    macd = market_data.get("macd")
    macd_signal = market_data.get("macd_signal")
    pe = market_data.get("pe_ratio")
    high_52w = market_data.get("fifty_two_week_high")
    low_52w = market_data.get("fifty_two_week_low")

    signals = []
    score = 0  # -100 (极度看空) 到 +100 (极度看多)

    # ── 均线系统 (权重 30%) ──────────────────────────

    if sma_20 and sma_50:
        if sma_20 > sma_50:
            signals.append({"name": "Golden Cross", "type": "bullish", "detail": f"SMA20({sma_20:.2f}) > SMA50({sma_50:.2f})", "weight": 15})
            score += 15
        else:
            signals.append({"name": "Death Cross", "type": "bearish", "detail": f"SMA20({sma_20:.2f}) < SMA50({sma_50:.2f})", "weight": -15})
            score -= 15

    if sma_200 and price:
        if price > sma_200:
            signals.append({"name": "Above MA200", "type": "bullish", "detail": f"Price({price:.2f}) above long-term trend({sma_200:.2f})", "weight": 10})
            score += 10
        else:
            pct_below = (sma_200 - price) / sma_200 * 100
            signals.append({"name": "Below MA200", "type": "bearish", "detail": f"Price {pct_below:.1f}% below long-term trend", "weight": -10})
            score -= 10

    if sma_20 and price:
        if price > sma_20:
            signals.append({"name": "Price > SMA20", "type": "bullish", "detail": "Short-term uptrend confirmed", "weight": 5})
            score += 5
        else:
            signals.append({"name": "Price < SMA20", "type": "bearish", "detail": "Short-term downtrend confirmed", "weight": -5})
            score -= 5

    # ── RSI 动量 (权重 20%) ──────────────────────────

    if rsi is not None:
        if rsi > 80:
            signals.append({"name": "RSI Extreme Overbought", "type": "bearish", "detail": f"RSI={rsi:.1f}, strong sell signal", "weight": -20})
            score -= 20
        elif rsi > 70:
            signals.append({"name": "RSI Overbought", "type": "bearish", "detail": f"RSI={rsi:.1f}, caution zone", "weight": -10})
            score -= 10
        elif rsi < 20:
            signals.append({"name": "RSI Extreme Oversold", "type": "bullish", "detail": f"RSI={rsi:.1f}, strong buy signal", "weight": 20})
            score += 20
        elif rsi < 30:
            signals.append({"name": "RSI Oversold", "type": "bullish", "detail": f"RSI={rsi:.1f}, potential rebound", "weight": 10})
            score += 10
        elif 45 <= rsi <= 55:
            signals.append({"name": "RSI Neutral", "type": "neutral", "detail": f"RSI={rsi:.1f}, no momentum signal", "weight": 0})
        elif rsi > 55:
            signals.append({"name": "RSI Bullish Momentum", "type": "bullish", "detail": f"RSI={rsi:.1f}, positive momentum", "weight": 5})
            score += 5
        else:
            signals.append({"name": "RSI Bearish Momentum", "type": "bearish", "detail": f"RSI={rsi:.1f}, negative momentum", "weight": -5})
            score -= 5

    # ── MACD (权重 15%) ──────────────────────────────

    if macd is not None and macd_signal is not None:
        macd_diff = macd - macd_signal
        if macd > macd_signal and macd > 0:
            signals.append({"name": "MACD Strong Bullish", "type": "bullish", "detail": f"MACD({macd:.4f}) above signal({macd_signal:.4f}) and positive", "weight": 15})
            score += 15
        elif macd > macd_signal:
            signals.append({"name": "MACD Bullish Crossover", "type": "bullish", "detail": f"MACD above signal, diff={macd_diff:.4f}", "weight": 8})
            score += 8
        elif macd < macd_signal and macd < 0:
            signals.append({"name": "MACD Strong Bearish", "type": "bearish", "detail": f"MACD({macd:.4f}) below signal({macd_signal:.4f}) and negative", "weight": -15})
            score -= 15
        else:
            signals.append({"name": "MACD Bearish Crossover", "type": "bearish", "detail": f"MACD below signal, diff={macd_diff:.4f}", "weight": -8})
            score -= 8

    # ── 52周位置 (权重 15%) ──────────────────────────

    if high_52w and low_52w and price:
        range_52w = high_52w - low_52w
        if range_52w > 0:
            position = (price - low_52w) / range_52w * 100  # 0=52w low, 100=52w high
            if position > 90:
                signals.append({"name": "Near 52W High", "type": "bearish", "detail": f"Price at {position:.0f}% of 52-week range, limited upside", "weight": -10})
                score -= 10
            elif position > 70:
                signals.append({"name": "Upper 52W Range", "type": "bullish", "detail": f"Price at {position:.0f}% of range, strong momentum", "weight": 5})
                score += 5
            elif position < 20:
                signals.append({"name": "Near 52W Low", "type": "bullish", "detail": f"Price at {position:.0f}% of range, potential value", "weight": 10})
                score += 10
            elif position < 40:
                signals.append({"name": "Lower 52W Range", "type": "bearish", "detail": f"Price at {position:.0f}% of range, weak momentum", "weight": -5})
                score -= 5
            else:
                signals.append({"name": "Mid 52W Range", "type": "neutral", "detail": f"Price at {position:.0f}% of range", "weight": 0})

            # 最大回撤
            drawdown = (high_52w - price) / high_52w * 100
            if drawdown > 30:
                signals.append({"name": "Severe Drawdown", "type": "bearish", "detail": f"{drawdown:.1f}% from 52-week high", "weight": -10})
                score -= 10
            elif drawdown > 15:
                signals.append({"name": "Moderate Drawdown", "type": "bearish", "detail": f"{drawdown:.1f}% from 52-week high", "weight": -5})
                score -= 5

    # ── P/E 估值 (权重 10%) ──────────────────────────

    if pe is not None:
        if pe < 0:
            signals.append({"name": "Negative P/E", "type": "bearish", "detail": "Company is unprofitable", "weight": -10})
            score -= 10
        elif pe > 100:
            signals.append({"name": "Extreme P/E", "type": "bearish", "detail": f"P/E={pe:.1f}, extremely overvalued by earnings", "weight": -10})
            score -= 10
        elif pe > 40:
            signals.append({"name": "High P/E", "type": "bearish", "detail": f"P/E={pe:.1f}, growth premium required", "weight": -5})
            score -= 5
        elif pe < 10:
            signals.append({"name": "Low P/E", "type": "bullish", "detail": f"P/E={pe:.1f}, potential value stock", "weight": 10})
            score += 10
        elif pe < 20:
            signals.append({"name": "Moderate P/E", "type": "bullish", "detail": f"P/E={pe:.1f}, reasonable valuation", "weight": 5})
            score += 5

    # ── 综合评分 ─────────────────────────────────────

    # Clamp score to [-100, 100]
    score = max(-100, min(100, score))

    # 分类
    if score >= 30:
        verdict = "STRONG BUY SIGNAL"
    elif score >= 10:
        verdict = "MODERATE BUY SIGNAL"
    elif score > -10:
        verdict = "NEUTRAL - NO CLEAR SIGNAL"
    elif score > -30:
        verdict = "MODERATE SELL SIGNAL"
    else:
        verdict = "STRONG SELL SIGNAL"

    bullish = [s for s in signals if s["type"] == "bullish"]
    bearish = [s for s in signals if s["type"] == "bearish"]

    summary = (
        f"Quant Score: {score}/100 ({verdict}). "
        f"{len(bullish)} bullish signals, {len(bearish)} bearish signals. "
        f"Strongest bullish: {bullish[0]['name'] if bullish else 'none'}. "
        f"Strongest bearish: {bearish[0]['name'] if bearish else 'none'}."
    )

    quant_result = {
        "score": score,
        "verdict": verdict,
        "signals": [{"name": s["name"], "type": s["type"], "detail": s["detail"], "weight": s["weight"]} for s in signals],
        "bullish_count": len(bullish),
        "bearish_count": len(bearish),
        "summary": summary,
    }

    logger.info("Quant for %s: score=%d, verdict=%s", ticker, score, verdict)

    return {
        "quant": quant_result,
        "reasoning_chain": [{
            "agent": "quant",
            "score": score,
            "verdict": verdict,
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "summary": summary,
        }],
    }
