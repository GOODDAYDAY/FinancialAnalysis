# Feature Store — Lightweight Feast Pattern

> **Scope:** Unified feature computation registry for training/inference consistency
> **Last reviewed:** 2026-04-22

## 1. Why a Feature Store?

In MLOps, **training-serving skew** is one of the most common causes of model degradation. When features are computed differently during training (offline batch) vs. inference (online real-time), the model receives inputs it wasn't trained on.

This project implements a **lightweight Feast pattern** — a versioned feature registry that ensures:
- All quantitative features (SMA, RSI, MACD, etc.) are computed from a **single source of truth**
- The **feature schema version** is logged to MLflow with every run
- New features can be added by defining them in one place (`definitions.py`)

No separate Feast server is needed — the registry is a Python module imported by agents.

## 2. Architecture

```
  ┌────────────────────────────────────────────────────────────────┐
  │                    Feature Store                                │
  │                                                                 │
  │  ┌───────────────────┐    ┌────────────────────────────────┐   │
  │  │  definitions.py   │    │  registry.py                   │   │
  │  │                   │    │                                │   │
  │  │  FEATURES = [     │───►│  FeatureRegistry               │   │
  │  │    Feature(...)   │    │    - register(feature)         │   │
  │  │    Feature(...)   │    │    - compute_features(ticker)  │   │
  │  │    ... 17 total   │    │    - get_feature(name)         │   │
  │  │  ]                │    │    - list_features()           │   │
  │  │                   │    │                                │   │
  │  │  SCHEMA_VERSION   │    │  ┌──────────────────────────┐ │   │
  │  │  = "v1.0.0"       │    │  │ Compute functions:       │ │   │
  │  └───────────────────┘    │  │ _compute_sma()           │ │   │
  │                           │  │ _compute_rsi()           │ │   │
  │                           │  │ _compute_macd()          │ │   │
  │                           │  │ _compute_bollinger()     │ │   │
  │                           │  │ _compute_atr()           │ │   │
  │                           │  │ _compute_stochastic()    │ │   │
  │                           │  │ _compute_obv_slope()     │ │   │
  │                           │  └──────────────────────────┘ │   │
  │                           └────────────────────────────────┘   │
  └────────────────────────────────────────────────────────────────┘
```

## 3. Feature definitions

All 17 features are defined in `backend/feature_store/definitions.py`:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Feature Registry — v1.0.0                                                │
├──────────────────┬───────────────┬───────────────────────────────────────┤
│ Name             │ Type          │ Source / Computation                  │
├──────────────────┼───────────────┼───────────────────────────────────────┤
│ current_price    │ float         │ OHLCV close[-1]                       │
│ volume           │ int           │ OHLCV volume[-1]                      │
│ price_change_pct │ float         │ (close[-1] - close[-2]) / close[-2]   │
│ sma_20           │ float         │ 20-day simple moving average          │
│ sma_50           │ float         │ 50-day simple moving average          │
│ sma_200          │ float         │ 200-day simple moving average         │
│ rsi_14           │ float         │ 14-day Relative Strength Index [0-100]│
│ macd             │ float         │ MACD line (12-26 EMA)                 │
│ macd_signal      │ float         │ MACD signal line (9-day EMA of MACD)  │
│ bollinger_upper  │ float         │ SMA(20) + 2*std(20)                   │
│ bollinger_lower  │ float         │ SMA(20) - 2*std(20)                   │
│ atr_14           │ float         │ 14-day Average True Range             │
│ stochastic_k     │ float         │ %K = (close - low_14) / (high_14 - low_14) * 100 │
│ obv_slope_pct    │ float         │ On-Balance Volume slope (linear regression) │
│ pe_ratio         │ float         │ Trailing P/E (yfinance info)          │
│ fifty_two_week_high │ float      │ 52-week high price                    │
│ fifty_two_week_low  │ float      │ 52-week low price                     │
└──────────────────┴───────────────┴───────────────────────────────────────┘
```

### 3.1 Feature tags

Each feature is tagged for discoverability:

```
Price:     current_price, volume, price_change_pct
Trend:     sma_20, sma_50, sma_200
Momentum:  rsi_14, macd, macd_signal, stochastic_k
Volatility: bollinger_upper, bollinger_lower, atr_14
Volume:    volume, obv_slope_pct
Reference: pe_ratio, fifty_two_week_high, fifty_two_week_low
```

## 4. How agents use the Feature Store

### 4.1 Market Data Agent

```python
from backend.feature_store import compute_features

# Old: manually assembled dict from yfinance
# New: unified feature computation
features = compute_features(ticker)  # → dict with all 17 features
market_data["features"] = features
market_data["feature_schema_version"] = features["feature_schema_version"]
```

### 4.2 Quant Agent

```python
from backend.feature_store import compute_features

features = compute_features(ticker)
# Uses features["rsi_14"], features["macd"], etc. directly
# Logs feature_schema_version to MLflow
```

### 4.3 MLflow integration

Every quant agent run logs the feature schema version:

```
MLflow Run:
  params:
    feature_schema_version: "v1.0.0"
    ticker: "600519.SS"
    exchange: "SH"
  metrics:
    composite_score: 0.75
    quant_score: 0.62
    rsi_14: 55.3
    ...
  artifacts:
    quant_report.txt
```

## 5. Versioning strategy

```
  FEATURE_SCHEMA_VERSION = "v1.0.0"
        │
        │  When a feature is added, removed, or its computation changes:
        ▼
  v1.1.0 (minor) or v2.0.0 (breaking)
        │
        │  MLflow records which version was used for each run
        ▼
  Ensures: training data and inference use the same feature set
```

### 5.1 Version bump rules

| Change type | Version bump | Example |
|:------------|:------------|:--------|
| New feature | Minor (v1.0.0 → v1.1.0) | Add `ema_12` |
| Removed feature | Major (v1.0.0 → v2.0.0) | Remove `stochastic_k` |
| Computation change | Major (v1.0.0 → v2.0.0) | RSI formula change |
| Bug fix (no behavior change) | Patch (v1.0.0 → v1.0.1) | Fix edge case in ATR |

## 6. Feature computation flow

```
  compute_features("600519.SS")
        │
        │  1. Fetch OHLCV data (yfinance)
        ▼
  ┌───────────────────────────────────────┐
  │  OHLCV DataFrame                        │
  │  Open  High   Low   Close  Volume       │
  │  150   152    149    151    1000000     │
  │  ...   ...    ...    ...    ...         │
  └──────────────────┬─────────────────────┘
                     │  (fan-out, parallel computation)
       ┌─────────────┼─────────────┬─────────────┐
       ▼             ▼             ▼             ▼
  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
  │  SMA    │  │  RSI     │  │  MACD   │  │  Bollinger│
  │  20/50  │  │  14      │  │  12/26  │  │  20/2     │
  │  200    │  │          │  │  /9     │  │           │
  └────┬────┘  └────┬─────┘  └────┬────┘  └─────┬────┘
       │             │             │              │
       ▼             ▼             ▼              ▼
  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
  │  ATR    │  │Stochastic│  │  OBV    │  │  PE/52w  │
  │  14     │  │  %K      │  │  slope  │  │  high/low│
  └─────────┘  └──────────┘  └─────────┘  └──────────┘
       │             │             │              │
       └─────────────┴─────────────┴──────────────┘
                     │
                     ▼
            { all features as dict }
            + feature_schema_version
```

## 7. Comparison: Feast vs. Light Pattern

| Aspect | Full Feast | Light Pattern (this project) |
|:-------|:----------|:---------------------------|
| Server | Required (gRPC + Redis/PostgreSQL) | None — pure Python module |
| Feature serving | Online + offline | Offline only (on-demand computation) |
| Versioning | Built-in | Manual `FEATURE_SCHEMA_VERSION` |
| MLflow integration | Custom | Direct (params logging) |
| Deployment complexity | High (2+ services) | Zero (just import) |
| Suitable for | Production ML at scale | Investment research system |
| Training/inference consistency | Guaranteed by Feast SDK | Guaranteed by shared `compute_features()` |
