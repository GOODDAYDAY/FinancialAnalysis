"""
Shared state contract for all LangGraph agents.

ResearchState is a TypedDict — survives LangGraph serialization.
Pydantic models are used ONLY for validation at agent boundaries.
"""

from typing import TypedDict, Optional, Annotated
from pydantic import BaseModel, Field
import operator


# ─── Pydantic validation models (boundary validation only) ────────

class MarketDataResult(BaseModel):
    ticker: str
    current_price: Optional[float] = None
    price_change: Optional[float] = None
    price_change_pct: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    technical_signals: list[str] = Field(default_factory=list)
    is_mock: bool = False
    data_source: str = "live"
    # Raw OHLCV arrays for Feature Store (avoids duplicate yfinance calls)
    raw_ohlcv: Optional[dict] = None


class NewsArticle(BaseModel):
    title: str
    source: str = "unknown"
    url: str = ""
    published: str = ""
    summary: str = ""
    relevance_score: float = 0.5


class SentimentOutput(BaseModel):
    overall_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="Sentiment score from -1 (bearish) to +1 (bullish)")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    overall_label: str = "neutral"
    reasoning: str = ""
    article_scores: list[dict] = Field(default_factory=list)
    key_factors: list[str] = Field(default_factory=list)


class FundamentalOutput(BaseModel):
    health_score: float = Field(default=5.0, ge=1.0, le=10.0, description="Financial health score 1-10")
    pe_assessment: str = ""
    pb_assessment: str = ""
    roe_assessment: str = ""
    debt_assessment: str = ""
    peer_comparison: str = ""
    red_flags: list[str] = Field(default_factory=list)
    summary: str = ""


class RiskOutput(BaseModel):
    risk_score: float = Field(default=5.0, ge=1.0, le=10.0, description="Risk score 1-10, 10 = highest risk")
    risk_level: str = "medium"
    risk_factors: list[str] = Field(default_factory=list)
    mitigation_notes: list[str] = Field(default_factory=list)
    summary: str = ""


class DebateArgument(BaseModel):
    role: str  # "bull" or "bear"
    round_number: int
    argument: str
    key_points: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    rebuttals: list[str] = Field(default_factory=list)


class RecommendationOutput(BaseModel):
    recommendation: str = "hold"  # buy / hold / sell
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    investment_horizon: str = "medium-term"
    supporting_factors: list[str] = Field(default_factory=list)
    dissenting_factors: list[str] = Field(default_factory=list)
    debate_summary: str = ""
    reasoning: str = ""
    disclaimer: str = (
        "This analysis is for educational and informational purposes only. "
        "It does not constitute financial advice. Past performance does not guarantee future results. "
        "Please consult a qualified financial advisor before making investment decisions."
    )


# ─── LangGraph State (TypedDict for serialization safety) ─────────

def merge_lists(left: list, right: list) -> list:
    """Reducer for list fields — append new items."""
    return left + right


class ResearchState(TypedDict, total=False):
    # Input
    user_query: str
    ticker: str
    intent: str  # "stock_query" | "chitchat" | "out_of_scope"
    language: str  # "zh" | "en" — auto-detected from user_query
    exchange: str  # "SH" | "SZ" | "BJ" | "HK" | "US" | "UNKNOWN" — auto-classified from ticker

    # Agent outputs (stored as plain dicts)
    market_data: dict
    news_articles: list[dict]
    sentiment: dict
    fundamental: dict
    risk: dict

    # Information collection (akshare)
    announcements: list[dict]
    financial_summary: dict
    social_sentiment: dict

    # Macro / sector / momentum context
    macro_env: dict
    sector: dict
    momentum: dict

    # Debate judge verdict (updated each judge round)
    debate_judge: dict

    # Quant
    quant: dict

    # Grid Strategy
    grid_strategy: dict

    # Feature Store — pre-computed features from market_data, consumed by quant
    features: dict

    # Debate
    debate_history: Annotated[list[dict], operator.add]
    debate_round: int

    # Advisory
    recommendation: dict

    # Metadata
    reasoning_chain: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]
