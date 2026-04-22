"""
Feature definitions for the quantitative analysis pipeline.

Each Feature describes a named value: how it's computed, where the raw
data comes from, and what dtype the downstream agents expect. This is
the lightweight alternative to a full Feast server — the registry acts
as the single source of truth for feature semantics, ensuring training
and inference use the same definitions.
"""

from dataclasses import dataclass
from typing import Callable, Any

FEATURE_SCHEMA_VERSION = "v1.0.0"


@dataclass(frozen=True)
class Feature:
    name: str
    dtype: str  # "float" | "int" | "str" | "bool"
    source: str  # e.g. "yfinance", "akshare", "computed"
    description: str
    tags: list[str] = None  # e.g. ["technical", "momentum", "valuation"]

    def __post_init__(self):
        if self.tags is None:
            object.__setattr__(self, "tags", [])


# ── Price & Volume ──────────────────────────────────────────────────────
FEATURES = {
    "current_price": Feature(
        name="current_price", dtype="float", source="yfinance",
        description="Latest closing price",
        tags=["price"],
    ),
    "volume": Feature(
        name="volume", dtype="int", source="yfinance",
        description="Latest trading volume",
        tags=["volume"],
    ),
    "price_change_pct": Feature(
        name="price_change_pct", dtype="float", source="computed",
        description="Daily price change percentage",
        tags=["price", "momentum"],
    ),

    # ── Moving Averages ─────────────────────────────────────────────────
    "sma_20": Feature(
        name="sma_20", dtype="float", source="computed",
        description="20-day Simple Moving Average",
        tags=["technical", "trend"],
    ),
    "sma_50": Feature(
        name="sma_50", dtype="float", source="computed",
        description="50-day Simple Moving Average",
        tags=["technical", "trend"],
    ),
    "sma_200": Feature(
        name="sma_200", dtype="float", source="computed",
        description="200-day Simple Moving Average",
        tags=["technical", "trend"],
    ),

    # ── Momentum ────────────────────────────────────────────────────────
    "rsi_14": Feature(
        name="rsi_14", dtype="float", source="computed",
        description="14-day Relative Strength Index",
        tags=["technical", "momentum"],
    ),
    "macd": Feature(
        name="macd", dtype="float", source="computed",
        description="MACD line (12,26,9)",
        tags=["technical", "momentum"],
    ),
    "macd_signal": Feature(
        name="macd_signal", dtype="float", source="computed",
        description="MACD signal line",
        tags=["technical", "momentum"],
    ),

    # ── Volatility ──────────────────────────────────────────────────────
    "bollinger_upper": Feature(
        name="bollinger_upper", dtype="float", source="computed",
        description="Bollinger Band upper band (20,2.0)",
        tags=["technical", "volatility"],
    ),
    "bollinger_lower": Feature(
        name="bollinger_lower", dtype="float", source="computed",
        description="Bollinger Band lower band (20,2.0)",
        tags=["technical", "volatility"],
    ),
    "atr_14": Feature(
        name="atr_14", dtype="float", source="computed",
        description="14-day Average True Range",
        tags=["technical", "volatility"],
    ),
    "stochastic_k": Feature(
        name="stochastic_k", dtype="float", source="computed",
        description="Stochastic Oscillator %K (14)",
        tags=["technical", "momentum"],
    ),

    # ── Volume-based ────────────────────────────────────────────────────
    "obv_slope_pct": Feature(
        name="obv_slope_pct", dtype="float", source="computed",
        description="On-Balance Volume 10-day slope as percentage",
        tags=["technical", "volume"],
    ),

    # ── Range & Valuation ───────────────────────────────────────────────
    "fifty_two_week_high": Feature(
        name="fifty_two_week_high", dtype="float", source="yfinance",
        description="52-week high price",
        tags=["price", "range"],
    ),
    "fifty_two_week_low": Feature(
        name="fifty_two_week_low", dtype="float", source="yfinance",
        description="52-week low price",
        tags=["price", "range"],
    ),
    "pe_ratio": Feature(
        name="pe_ratio", dtype="float", source="yfinance",
        description="Trailing P/E ratio",
        tags=["valuation"],
    ),
}


def list_features(tags: list[str] | None = None) -> dict[str, Feature]:
    """Return all registered features, optionally filtered by tags."""
    if tags is None:
        return dict(FEATURES)
    return {
        name: f for name, f in FEATURES.items()
        if any(t in f.tags for t in tags)
    }


def get_feature(name: str) -> Feature | None:
    """Look up a single feature by name."""
    return FEATURES.get(name)
