# MLOps Overview

> **Scope:** End-to-end MLOps practices in the Multi-Agent Investment Research System
> **Reference:** Databricks MLOps best practices, Google SAIF, MLflow conventions
> **Last reviewed:** 2026-04-22

## 1. MLOps maturity map

This project implements the following MLOps practices, mapped to standard frameworks:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  MLOps Practice                  │ Implementation           │ Maturity       │
├──────────────────────────────────┼──────────────────────────┼────────────────┤
│ 1. Experiment Tracking           │ MLflow (params, metrics, │ Implemented    │
│                                  │ artifacts)               │                │
│ 2. Model Registry                │ MLflow local registry    │ Implemented    │
│ 3. Feature Store                 │ Light Feast pattern      │ Implemented    │
│ 4. Data Validation               │ Pydantic + quality tests │ Implemented    │
│ 5. CI/CD for ML                  │ GitHub Actions (10 jobs) │ Implemented    │
│ 6. Model Monitoring              │ Token tracking, audit    │ Implemented    │
│ 7. Containerized Deployment      │ Docker Compose + GHCR    │ Implemented    │
│ 8. Security Scanning             │ Trivy + pip-audit        │ Implemented    │
│ 9. Automated Testing             │ 276 tests, 16 suites     │ Implemented    │
│ 10. Reproducibility              │ Feature schema version   │ Implemented    │
│ 11. Model Governance             │ Model pinning, prompt    │ Implemented    │
│                                  │ integrity contracts      │                │
│ 12. Continuous Training          │ Not yet                  │ Future         │
│ 13. A/B Testing                  │ Not yet                  │ Future         │
│ 14. Shadow Deployment            │ Not yet                  │ Future         │
└──────────────────────────────────┴──────────────────────────┴────────────────┘
```

## 2. MLOps architecture diagram

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │                         DATA LAYER                                    │
  │                                                                       │
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
  │  │ yfinance │  │ akshare  │  │DuckDuckGo│  │ SMTP (notification)  │  │
  │  │ OHLCV    │  │ CN data  │  │ search   │  │ scheduled alerts     │  │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────────┘  │
  │       │              │             │                                   │
  └───────┼──────────────┼─────────────┼───────────────────────────────────┘
          │              │             │
          ▼              ▼             ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    FEATURE LAYER                                      │
  │                                                                       │
  │  ┌──────────────────────────────────────────────────────────────┐    │
  │  │  Feature Store (backend/feature_store/)                       │    │
  │  │  17 features: SMA, RSI, MACD, Bollinger, ATR, Stochastic,    │    │
  │  │  OBV, P/E, 52w high/low                                       │    │
  │  │  Schema version: v1.0.0                                       │    │
  │  └──────────────────────────────────────────────────────────────┘    │
  │                                                                       │
  └──────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    MODEL LAYER (16 Agents)                            │
  │                                                                       │
  │  ┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
  │  │ Data Agents (6) │  │ Analysis (5)     │  │ Decision (3)        │  │
  │  │ market_data     │  │ sentiment        │  │ debate              │  │
  │  │ news            │  │ fundamental      │  │ debate_judge        │  │
  │  │ macro_env       │  │ momentum         │  │ advisory            │  │
  │  │ sector          │  │ quant            │  │                     │  │
  │  │ announcement    │  │ grid_strategy    │  │                     │  │
  │  │ social_sentiment│  │                  │  │                     │  │
  │  └─────────────────┘  └──────────────────┘  └─────────────────────┘  │
  │  ┌─────────────────┐  ┌──────────────────┐                           │
  │  │ Orchestrator    │  │ Support (2)      │                           │
  │  │ sanitizer       │  │ risk             │                           │
  │  │ intent          │  │                  │                           │
  │  │ ticker          │  │                  │                           │
  │  └─────────────────┘  └──────────────────┘                           │
  │                                                                       │
  │  All agents log to MLflow: params, metrics, artifacts                │
  └──────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    OBSERVABILITY LAYER                                │
  │                                                                       │
  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
  │  │ MLflow           │  │ Audit Trail      │  │ Token Tracker      │  │
  │  │ experiment runs  │  │ JSONL log        │  │ per-agent usage    │  │
  │  │ params/metrics   │  │ security events  │  │ cost accounting    │  │
  │  │ artifacts        │  │ override events  │  │ rate limiting      │  │
  │  └──────────────────┘  └──────────────────┘  └────────────────────┘  │
  │                                                                       │
  └──────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                    DEPLOYMENT LAYER                                   │
  │                                                                       │
  │  ┌──────────────────────────────────────────────────────────────┐    │
  │  │  CI/CD Pipeline (GitHub Actions)                              │    │
  │  │                                                               │    │
  │  │  ┌───────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────┐  │    │
  │  │  │ml-contracts│ │data-valid  │ │model-qual  │ │  mlflow     │  │    │
  │  │  │(hard fail) │ │(hard fail) │ │(hard fail) │ │(hard fail)  │  │    │
  │  │  └───────────┘ └────────────┘ └───────────┘ └─────────────┘  │    │
  │  │                                                               │    │
  │  │  ┌───────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────┐  │    │
  │  │  │docker-build│ │dep-audit   │ │agent-bench │ │grid-excel   │  │    │
  │  │  │+ Trivy     │ │(CVE scan)  │ │(real API)  │ │(REQ-002)    │  │    │
  │  │  └───────────┘ └────────────┘ └───────────┘ └─────────────┘  │    │
  │  └──────────────────────────────────────────────────────────────┘    │
  │                                                                       │
  │  ┌──────────────────────────────────────────────────────────────┐    │
  │  │  Production (Docker Compose)                                  │    │
  │  │                                                               │    │
  │  │  app container (ghcr.io/.../app:<sha>)  :8501                 │    │
  │  │  mlflow container (python:3.11-slim)    :5000                 │    │
  │  └──────────────────────────────────────────────────────────────┘    │
  └──────────────────────────────────────────────────────────────────────┘
```

## 3. Data flow through the MLOps pipeline

```
  User Query: "What do you think about 600519?"
      │
      ▼  Step 1: Sanitization (security check)
  orchestrator.extract_ticker() → "600519.SS", exchange: "SH"
      │
      ▼  Step 2: Data Collection (fan-out, 6 parallel agents)
  market_data → OHLCV + features (via feature_store)
  news        → news articles
  macro_env   → CSI 300 regime [A-share only]
  sector      → industry rankings [A-share only]
  announcement → company filings [A-share only]
  social_sent → retail sentiment [A-share only]
      │
      ▼  Step 3: Analysis (sequential)
  sentiment   → LLM relevance-weighted sentiment score
  fundamental → LLM + numeric valuation analysis
  momentum    → pure-math multi-horizon momentum score
  quant       → technical analysis (uses feature_store values)
                  → logs to MLflow:
                      params: feature_schema_version="v1.0.0"
                      metrics: quant_score, rsi_14, macd, ...
                      artifacts: quant_report.txt
  grid_strategy → grid trading suitability
      │
      ▼  Step 4: Decision (debate)
  debate      → Bull vs Bear arguments (2-5 rounds)
  debate_judge → LLM judge decides when to stop
      │
      ▼  Step 5: Final Recommendation
  risk        → risk score + compliance disclaimer
  advisory    → final synthesis + numeric override layer
                  → composite_score = 0.4*momentum + 0.35*quant + 0.25*fundamental
                  → override rules fire if conditions met
      │
      ▼  Step 6: Output
  Streamlit UI → formatted report in user's language
      │
      ▼  Step 7: Observability
  MLflow run complete:
    params: ticker, exchange, feature_schema_version, debate_rounds
    metrics: composite_score, momentum_score, quant_score,
             fundamental_score, risk_score, confidence
    artifacts: debate_transcript.txt, advisory_report.txt,
               reasoning_chain.json
  Audit trail: request logged (timestamp, user, outcome)
  Token usage: per-agent token count recorded
```

## 4. MLflow experiment tracking

### 4.1 What's tracked

| Category | Items |
|:---------|:------|
| **Params** | `ticker`, `exchange`, `feature_schema_version`, `debate_rounds`, `debate_concluded` |
| **Metrics** | `composite_score`, `momentum_score`, `quant_score`, `fundamental_score`, `risk_score`, `confidence` |
| **Artifacts** | `quant_report.txt`, `fundamental_report.txt`, `debate_transcript.txt`, `advisory_report.txt`, `reasoning_chain.json` |

### 4.2 MLflow architecture

```
  ┌───────────────────────────────────────────────┐
  │  MLflow Server (Docker :5000)                  │
  │                                                 │
  │  Backend store: sqlite:///mlflow.db            │
  │  Artifact store: /mlruns (Docker volume)       │
  │  Experiment: "investment-research"             │
  │                                                 │
  │  Volumes:                                       │
  │    mlflow-data      → /mlruns (experiment data) │
  │    mlflow-artifacts → /mlartifacts (files)      │
  └───────────────────────────────────────────────┘
        ▲
        │  mlflow.log_param(), log_metric(), log_artifact()
        │
  ┌─────┴──────────────────────────────────────────┐
  │  Quant Agent                                   │
  │                                                 │
  │  mlflow.start_run()                            │
  │    mlflow.log_param("feature_schema_version",  │
  │                     "v1.0.0")                  │
  │    mlflow.log_param("ticker", "600519.SS")     │
  │    mlflow.log_metric("composite_score", 0.75)  │
  │    mlflow.log_artifact("report.txt")           │
  │  mlflow.end_run()                              │
  └────────────────────────────────────────────────┘
```

### 4.3 Querying experiments

```python
import mlflow

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("investment-research")

# Get all runs
runs = mlflow.search_runs()

# Filter by ticker
runs = mlflow.search_runs(
    filter_string="params.ticker = '600519.SS'"
)

# Compare feature schema versions
versions = runs["params.feature_schema_version"].unique()
```

## 5. Feature Store (training/inference consistency)

The Feature Store ensures that the same quantitative features are computed identically across all runs:

```
  Feature: rsi_14
  ┌─────────────────────────────────────────────────┐
  │ Definition (definitions.py)                      │
  │  name: "rsi_14"                                  │
  │  dtype: float                                    │
  │  source: "ohlcv"                                 │
  │  description: "14-day RSI"                       │
  │  tags: ["momentum", "technical"]                 │
  └──────────────────────┬──────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────┐
  │ Computation (registry.py)                        │
  │  _compute_rsi(ohlcv) → float [0-100]             │
  │  Uses: EMA of gains/losses over 14 periods       │
  └──────────────────────┬──────────────────────────┘
                         │
  ┌──────────────────────▼──────────────────────────┐
  │ Usage                                            │
  │  market_data agent: attaches to market_data dict │
  │  quant agent: reads for analysis                 │
  │  MLflow: logs as metric + schema version         │
  └──────────────────────────────────────────────────┘
```

**Key benefit:** If the RSI computation formula changes in the future, the `FEATURE_SCHEMA_VERSION` bumps, and MLflow records which version was used for each run. This makes it possible to:
- Reproduce any past analysis
- Compare results across feature versions
- Detect training/inference skew

## 6. CI/CD for ML

### 6.1 Gate hierarchy

```
  ┌─────────────────────────────────────────────────────────────┐
  │  Gate 1: Code Quality (ml-contracts)                        │
  │  Lint + schema contracts + behavioral tests + security       │
  │  ⏱ ~2 min, no API required                                   │
  │  Policy: HARD FAIL                                           │
  ├─────────────────────────────────────────────────────────────┤
  │  Gate 2: Data Quality (data-validation)                      │
  │  Pydantic schema + data quality tests                        │
  │  ⏱ ~1 min, no API required                                   │
  │  Policy: HARD FAIL                                           │
  ├─────────────────────────────────────────────────────────────┤
  │  Gate 3: Model Quality (model-quality)                       │
  │  Bias + hallucination + output compliance                    │
  │  ⏱ ~1 min, no API required                                   │
  │  Policy: HARD FAIL                                           │
  ├─────────────────────────────────────────────────────────────┤
  │  Gate 4: MLflow Integration (mlflow)                         │
  │  Experiment tracking tests                                   │
  │  ⏱ ~1 min, no API required                                   │
  │  Policy: HARD FAIL                                           │
  ├─────────────────────────────────────────────────────────────┤
  │  Gate 5: Container Security (docker-build)                   │
  │  Docker build + Trivy scan                                   │
  │  ⏱ ~5 min                                                    │
  │  Policy: HARD FAIL (CRITICAL/HIGH CVEs block)                │
  ├─────────────────────────────────────────────────────────────┤
  │  Gate 6: Supply Chain (dependency-audit)                     │
  │  pip-audit + secret scan                                     │
  │  ⏱ ~1 min                                                    │
  │  Policy: HARD FAIL (secrets), WARN (CVEs)                    │
  └─────────────────────────────────────────────────────────────┘
```

### 6.2 Deployment flow

```
  All gates pass
      │
      ▼
  Build Docker image → Push to ghcr.io
      │
      │  Image: ghcr.io/owner/repo/app:a1b2c3d
      ▼
  SSH to server → docker compose pull → docker compose up -d
      │
      ▼
  Health check: curl :8501/_stcore/health (15 retries)
      │
      ▼
  Deploy complete
```

## 7. Future improvements

| Practice | Current State | Planned |
|:---------|:-------------|:--------|
| Continuous Training | Manual trigger only | Automated retraining on schedule |
| A/B Testing | Not implemented | Split traffic between model versions |
| Shadow Deployment | Not implemented | Run new model in parallel, compare outputs |
| Feature Store Server | Light pattern (Python module) | Consider Feast server if team scales |
| Model Registry | MLflow local | Promote best models to production |
| Alerting | Email notifications | Slack/PagerDuty integration |
| Monitoring Dashboard | MLflow UI | Grafana + Prometheus for production metrics |
