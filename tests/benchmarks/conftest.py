"""
Shared fixtures for agent benchmark tests.

Two categories:
  - data agents   : yfinance / akshare calls (no API key, needs network)
  - llm agents    : call_llm_structured is mocked so the agent logic runs
                    without a real DeepSeek call.  The mock returns realistic
                    Pydantic instances that match each agent's response_model.
"""

import pytest
from backend.state import (
    SentimentOutput,
    FundamentalOutput,
    RiskOutput,
    DebateArgument,
    RecommendationOutput,
)
from backend.agents.orchestrator.node import IntentResult
from backend.agents.debate_judge.node import JudgeDecision


# ── Pre-baked LLM mock responses (one per Pydantic model) ─────────────────

MOCK_INTENT = IntentResult(
    intent="stock_query",
    ticker="600519.SS",
    company_name="Kweichow Moutai",
    explanation="User asked to analyze Moutai stock.",
)

MOCK_SENTIMENT = SentimentOutput(
    overall_score=0.45,
    confidence=0.78,
    overall_label="bullish",
    reasoning="Strong earnings and positive regulatory outlook drive bullish sentiment.",
    key_factors=["record revenue", "premium brand moat", "stable dividend"],
    article_scores=[{"title": "Moutai Q4 results beat estimates", "score": 0.7}],
)

MOCK_FUNDAMENTAL = FundamentalOutput(
    health_score=8.0,
    pe_assessment="P/E of 28 is elevated but justified by brand premium.",
    pb_assessment="P/B of 9 reflects dominant market position.",
    roe_assessment="ROE consistently above 30% — exceptional capital efficiency.",
    debt_assessment="Near-zero debt ratio; fortress balance sheet.",
    peer_comparison="Outperforms baijiu peers on every margin metric.",
    red_flags=["valuation premium requires continued growth"],
    summary="Financially strong with premium valuation.",
)

MOCK_BULL = DebateArgument(
    role="bull",
    round_number=1,
    argument=(
        "Moutai's pricing power is unmatched in the luxury spirits sector. "
        "With RSI at 55 (not overbought), a 20-day breakout confirmed by OBV, "
        "and the macro regime showing BULL MARKET conditions, the risk/reward "
        "strongly favors accumulation at current levels."
    ),
    key_points=[
        "Pricing power: 20% wholesale price increase absorbed without demand destruction",
        "Technical breakout: price above 20d high with above-average volume",
        "Macro tailwind: CSI 300 in BULL regime, sector outperforming broad market",
    ],
    evidence=[
        "5d return +6.2% vs CSI 300 +1.1%",
        "OBV confirming price rise",
        "Q3 revenue +18% YoY",
    ],
    rebuttals=[],
)

MOCK_BEAR = DebateArgument(
    role="bear",
    round_number=1,
    argument=(
        "The valuation premium leaves no margin of safety. P/E at 28x "
        "prices in perfection. Any policy shock — gift-giving bans, "
        "consumption tax increases, or trade tensions — could compress "
        "multiples significantly. The Bull ignores tail risks."
    ),
    key_points=[
        "Valuation risk: P/E 28x assumes 15%+ EPS growth; any miss crushes the stock",
        "Regulatory overhang: anti-corruption campaigns historically cut Moutai sales 30%",
        "Concentration risk: 90%+ revenue from single product category",
    ],
    evidence=[
        "2012 anti-corruption clampdown: stock fell 60% in 18 months",
        "DCF fair value ~1800 CNY vs current price 1920 CNY (5% overvalued)",
        "Insider selling in Q3",
    ],
    rebuttals=["Bull's breakout signal doesn't account for low overall market volume"],
)

MOCK_JUDGE = JudgeDecision(
    verdict="concluded",
    quality_score=78,
    reason="Both sides cited concrete data; key trade-offs are clearly articulated.",
    unresolved_points=[],
    bull_strength=65,
    bear_strength=60,
)

MOCK_RISK = RiskOutput(
    risk_score=4.5,
    risk_level="medium",
    risk_factors=[
        "Valuation premium: P/E 28x — earnings miss would be punished",
        "Regulatory risk: government policy sensitivity",
        "Concentration: single core product (Moutai baijiu)",
    ],
    mitigation_notes=[
        "Fortress balance sheet buffers against cyclical downturns",
        "Pricing power provides revenue floor",
    ],
    summary="Medium risk: strong fundamentals offset by valuation and regulatory exposure.",
)

MOCK_RECOMMENDATION = RecommendationOutput(
    recommendation="buy",
    confidence=0.68,
    investment_horizon="medium-term",
    supporting_factors=[
        "Bullish momentum: +6.2% in 5 days, 20-day breakout",
        "Strong fundamentals: health score 8/10",
        "Bull regime macro environment",
    ],
    dissenting_factors=[
        "Elevated P/E (28x) leaves limited margin of safety",
        "Regulatory tail risk",
    ],
    debate_summary="Bull presented stronger data-driven arguments; Bear's concerns are real but known.",
    reasoning="Momentum and fundamental strength outweigh valuation concerns in current macro regime.",
)


def _llm_mock(responses: dict):
    """
    Return a mock callable for call_llm_structured.
    Dispatches by response_model type; falls back to default construction.
    """
    def _call(user_prompt, response_model, system_prompt="", **kwargs):
        return responses.get(response_model, response_model())
    return _call


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def llm_responses():
    """Dict mapping response_model type → pre-baked Pydantic instance."""
    return {
        IntentResult:      MOCK_INTENT,
        SentimentOutput:   MOCK_SENTIMENT,
        FundamentalOutput: MOCK_FUNDAMENTAL,
        DebateArgument:    MOCK_BULL,   # first call (bull); debate tests override with side_effect
        JudgeDecision:     MOCK_JUDGE,
        RiskOutput:        MOCK_RISK,
        RecommendationOutput: MOCK_RECOMMENDATION,
    }


@pytest.fixture
def mock_llm(llm_responses):
    """Callable that mimics call_llm_structured using pre-baked responses."""
    return _llm_mock(llm_responses)


@pytest.fixture
def synth_state():
    """
    Minimal but realistic ResearchState for benchmarking LLM agents.
    All numeric values are within documented valid ranges.
    """
    return {
        "ticker": "600519.SS",
        "language": "zh",
        "user_query": "分析贵州茅台",
        "market_data": {
            "current_price": 1920.0,
            "price_change_pct": 1.8,
            "pe_ratio": 28.0,
            "rsi_14": 55.0,
            "sma_20": 1880.0,
            "sma_50": 1820.0,
            "volume": 8_500_000,
            "market_cap": 2.4e12,
            "fifty_two_week_high": 1980.0,
            "fifty_two_week_low": 1450.0,
            "technical_signals": ["Price above SMA20", "RSI neutral"],
        },
        "macro_env": {
            "overall_regime": "BULL MARKET",
            "primary_regime": "STRONG BULL",
            "bull_count": 3,
            "bear_count": 0,
            "sideways_count": 1,
            "indices": {
                "sh000300": {
                    "name": "CSI 300",
                    "price": 4200.0,
                    "change_pct": 0.8,
                    "return_5d_pct": 2.1,
                    "return_20d_pct": 5.4,
                    "regime": "STRONG BULL",
                }
            },
            "summary": "Overall regime: BULL MARKET. CSI 300: 4200 (+0.8% today)",
        },
        "sector": {
            "stock_industry": {"industry_name": "白酒"},
            "stock_sector_row": {"name": "白酒", "rank": 2, "change_pct": 1.5, "advance": 8, "decline": 2},
            "top_sectors": [{"name": "白酒", "change_pct": 1.5}, {"name": "半导体", "change_pct": 2.1}],
            "top_concepts": [{"name": "消费升级", "change_pct": 1.2}],
            "bottom_sectors": [{"name": "房地产", "change_pct": -0.8}],
            "summary": "Stock in 白酒 (rank 2, +1.5% today)",
        },
        "momentum": {
            "score": 45,
            "regime": "BULLISH MOMENTUM",
            "returns": {"3d": 2.1, "5d": 6.2, "10d": 4.8, "20d": 9.1, "60d": 15.3},
            "range_position_pct": 87.0,
            "breakout_20": True,
            "volume_surge_ratio": 1.4,
            "trend_consistency_pct": 65.0,
            "relative_strength_vs_csi300_20d": 3.7,
            "signals": [
                {"name": "5-day Uptrend", "type": "bullish", "detail": "+6.2% in 5 days", "weight": 20},
                {"name": "20-day Breakout", "type": "bullish", "detail": "Price at 20d high", "weight": 15},
            ],
            "summary": "Momentum score 45/100 (BULLISH MOMENTUM).",
        },
        "sentiment": {
            "overall_score": 0.45,
            "overall_label": "bullish",
            "confidence": 0.78,
            "key_factors": ["record revenue", "premium brand moat"],
            "reasoning": "Positive news flow drives bullish sentiment.",
        },
        "fundamental": {
            "health_score": 8.0,
            "pe_assessment": "P/E 28x elevated but justified",
            "red_flags": ["valuation premium"],
            "summary": "Financially strong with premium valuation.",
        },
        "quant": {
            "score": 30,
            "verdict": "MODERATE BUY",
            "signals": [
                {"name": "Price above SMA20", "type": "bullish", "detail": "+2.1%", "weight": 15},
                {"name": "RSI neutral", "type": "neutral", "detail": "RSI=55", "weight": 0},
            ],
            "bullish_count": 3,
            "bearish_count": 1,
            "summary": "Moderate buy based on technical signals.",
        },
        "grid_strategy": {
            "score": 55,
            "verdict": "MARGINAL",
            "annual_volatility_pct": 22.5,
            "best_strategy_name": "medium_term_grid",
            "best_monthly_return_pct": 2.8,
            "strategies": [{"name": "medium_term_grid", "monthly_return_pct": 2.8}],
        },
        "risk": {
            "risk_score": 4.5,
            "risk_level": "medium",
            "risk_factors": ["valuation premium", "regulatory risk"],
            "summary": "Medium risk.",
        },
        "announcements": [
            {"date": "2026-03-15", "title": "Q4 2025 Annual Report", "content": "Revenue +18% YoY"},
        ],
        "financial_summary": {"roe": 32.5, "revenue_growth": 18.0},
        "social_sentiment": {"summary": "Bullish retail chatter", "is_trending": True, "trending_rank": 3},
        "news_articles": [
            {"title": "Moutai Q4 results beat estimates", "source": "Reuters", "url": "", "published": "2026-03-10", "summary": "Strong earnings", "relevance_score": 0.8},
        ],
        "debate_history": [],
        "debate_round": 0,
        "debate_judge": {},
        "reasoning_chain": [],
        "errors": [],
    }
