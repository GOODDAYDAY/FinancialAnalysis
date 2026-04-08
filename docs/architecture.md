# System Architecture

> **Scope:** Multi-Agent Investment Research System (REQ-001)
> **Last reviewed:** 2026-04-07

## 1. High-level topology

```
  ┌──────────────┐     ┌────────────────────────┐     ┌─────────────┐
  │   Streamlit  │ ◄──►│  LangGraph StateGraph  │ ◄──►│ DeepSeek LLM│
  │  frontend/   │     │      backend/          │     │    API      │
  └──────────────┘     └────────┬───────────────┘     └─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
      ┌──────────┐        ┌──────────┐       ┌───────────┐
      │ yfinance │        │ akshare  │       │ SMTP/QQ   │
      │ (US/HK)  │        │ (CN A-sh)│       │  mail     │
      └──────────┘        └──────────┘       └───────────┘
```

## 2. Package layout

```
backend/
  ├── agents/                # 16 agents, one sub-package each
  │   ├── orchestrator/      # intent + ticker + sanitizer
  │   ├── market_data/       # yfinance OHLCV + SMA/RSI/MACD
  │   ├── macro_env/         # CSI 300 / SSE regime detection
  │   ├── sector/            # industry / concept rankings
  │   ├── news/              # akshare news collector
  │   ├── announcement/      # official company announcements
  │   ├── social_sentiment/  # retail chatter
  │   ├── sentiment/         # LLM per-article relevance-weighted
  │   ├── fundamental/       # LLM + valuation_calc numeric anchors
  │   ├── momentum/          # pure-math multi-horizon score
  │   ├── quant/             # classical + Bollinger/ATR/Stoch/OBV
  │   ├── grid_strategy/     # volatility-based grid suitability
  │   ├── debate/            # Bull vs Bear LLM arguments
  │   ├── debate_judge/      # LLM judge, dynamic round control
  │   ├── risk/              # risk score + compliance disclaimer
  │   └── advisory/          # final synthesis + numeric override
  │
  ├── security/              # sanitizer / pii / output_filter / injection_patterns
  ├── observability/         # token_tracker / audit_trail
  ├── utils/                 # ticker / language helpers
  ├── graph.py               # LangGraph wiring
  ├── state.py               # ResearchState (TypedDict) + Pydantic validators
  ├── llm_client.py          # DeepSeek client + retry + output filter + token track
  └── config.py              # env-var loader (pydantic-settings)

frontend/
  └── app.py                 # Streamlit chat UI with follow-up context

scripts/
  ├── install_linux.sh
  ├── install_windows.bat
  ├── scheduler_daemon.py
  ├── test_email_smtp.py
  └── smoke_test.sh

tests/
  ├── agents/                # per-agent smoke tests (real APIs, no mocks)
  ├── e2e/                   # full-pipeline tests
  └── security/              # injection / PII / sanitizer / output filter

docs/
  ├── ai_security_risk_register.md
  ├── explainable_responsible_ai.md
  ├── mlsecops_pipeline.md
  └── architecture.md        (← this file)

requirements/REQ-001-*/      # requirement + technical documents
.github/workflows/           # CI + deploy pipelines
```

## 3. Execution flow

```
User query
  │
  ▼
orchestrator  ── sanitizer ──► [blocked → END]
  │
  ▼  (fan-out, parallel)
┌────────────────────────────────────────────────┐
│ market_data  macro_env  sector                 │
│ news         announcement  social_sentiment    │
└────────────────────────────────────────────────┘
  │  (fan-in)
  ▼
sentiment → fundamental → momentum → quant → grid_strategy
  │
  ▼
debate ⇄ debate_judge   (2–5 rounds, judge decides when to stop)
  │
  ▼
risk → advisory → END
```

## 4. State model

`ResearchState` (TypedDict, serializable) carries all agent outputs. Two reducer-annotated fields accumulate across nodes:

- `reasoning_chain: Annotated[list[dict], operator.add]` — every agent appends one entry
- `errors: Annotated[list[dict], operator.add]` — captured by `_safe()` wrapper in `graph.py`
- `debate_history: Annotated[list[dict], operator.add]` — accumulates across debate rounds

All other fields are plain dicts; LangGraph's default "last writer wins" reducer is safe because each agent writes a disjoint key.

## 5. Key design decisions

| Decision                                    | Rationale                                                                     |
|---------------------------------------------|-------------------------------------------------------------------------------|
| TypedDict state, not Pydantic               | LangGraph checkpointer serialization works with TypedDict + JSON-safe dicts   |
| Pydantic at agent boundaries only           | Validates LLM structured output; rejects malformed responses                  |
| Numeric composite override in advisory      | Kills LLM's HOLD bias; makes recommendations traceable to math                |
| Debate judge with min/max rounds            | Dynamic depth; prevents endless loops and pointless short debates             |
| Sanitizer as single entry point             | One place to audit; orchestrator is the only trust boundary                   |
| Output filter inside `llm_client.call_llm`  | All agents get the filter for free; no agent can forget to call it            |
| Parallel data collection via fan-out        | 6 I/O-bound nodes run concurrently → ~3× wall-clock improvement               |
| Language auto-detection                     | ≥2 CJK chars → `zh`, else `en`; propagated via `state["language"]`            |
| Ticker normalization as shared util         | `backend/utils/ticker.py` is the single source of exchange-suffix rules       |

## 6. Scalability & deployment

- **Single-user mode**: launch via `run.bat` / `run.sh`; Streamlit + LangGraph in one process.
- **Multi-user mode**: deploy behind nginx + TLS; Streamlit worker pool. Audit trail is thread-safe.
- **Scheduled jobs**: `scripts/scheduler_daemon.py` runs under systemd; reads `config/schedule.json`.
- **CI/CD**: GitHub Actions → SSH to self-hosted server. See `docs/mlsecops_pipeline.md`.
