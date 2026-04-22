# Financial Analysis — Multi-Agent Investment Research System

> An explainable, multi-agent AI system for stock investment research, built with **LangGraph** and **DeepSeek**. Sixteen specialized agents — including a parallel data-collection fan-out, a Bull-vs-Bear debate engine with LLM judge, a pure-algorithmic Quant referee, and a Grid Trading Strategy planner — collaborate to produce transparent buy/hold/sell recommendations for Chinese A-shares, Hong Kong, and global stocks.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.3+-green.svg)](https://github.com/langchain-ai/langgraph)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple.svg)](https://platform.deepseek.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io)

---

## Highlights

- **16 specialized agents** wired in a LangGraph state machine (+ 1 standalone follow-up agent), each living in its own sub-package for clean ownership
- **Parallel data fan-out** — market data, macro environment, sector rankings, news, announcements, and social sentiment fetched concurrently (~3× wall-clock speedup)
- **Bull vs Bear debate with LLM judge** — debate agent argues 2–5 rounds; a separate judge agent decides whether the debate is deep enough to conclude
- **Pure-algorithmic Quant Agent** — no LLM, computes MA/RSI/MACD signals as a "data referee" alongside the AI debaters
- **Grid Trading Strategy Agent** — proposes 4 strategy variants (short / medium / long-term / accumulation) with fee-aware profit math, A-share lot sizing, and monthly return estimates
- **Free China-accessible data sources** — yfinance, akshare (东方财富/同花顺/财新), DuckDuckGo News. No paid APIs required.
- **Conversational follow-up** — ask detail questions about a previous analysis; full context from all agents is preserved across turns
- **Scheduled email reports** — QQ Mail SMTP integration with HTML templates, runs on cron / systemd timer / Windows Task Scheduler
- **Zero-dependency launcher** — `scripts/run.bat` auto-installs `uv`, creates venv, installs deps, prompts for API key, and starts the app on a clean Windows machine
- **One-click Linux deployment** — `deploy/install_linux.sh` sets up systemd units for the web app and the scheduled task on a fresh Singapore Linux server
- **All real tests** — every test makes real DeepSeek + yfinance + akshare calls, no mocks

---

## Architecture

### Pipeline (17 nodes, 16 agents + 1 standalone follow-up)

```
User Query
    │
    ▼
┌─────────────────┐
│  Orchestrator   │  Intent classification, ticker extraction, prompt-injection defense
└────────┬────────┘
         ▼ (fan-out — 6 nodes run in parallel)
┌──────────────────────────────────────────────────────┐
│  Market Data   │  Macro Env    │  Sector              │
│  (yfinance)    │  (akshare     │  (akshare industry   │
│                │   indices)    │   / concept ranks)   │
├──────────────────────────────────────────────────────┤
│  News          │  Announcement │  Social Sentiment    │
│  (yfinance +   │  (akshare     │  (akshare Eastmoney  │
│   DuckDuckGo)  │   filings)    │   股吧)              │
└──────────────────────────────────────────────────────┘
         ▼ (fan-in)
┌─────────────────┐
│   Sentiment     │  DeepSeek LLM: per-article relevance-weighted sentiment
└────────┬────────┘
         ▼
┌─────────────────┐
│   Fundamental   │  DeepSeek LLM: health score 1-10, DCF/PEG anchors, red flags
└────────┬────────┘
         ▼
┌─────────────────┐
│    Momentum     │  Pure algorithms: multi-horizon returns, breakout, volume surge
└────────┬────────┘
         ▼
┌─────────────────┐
│      Quant      │  Pure algorithms: MA/RSI/MACD/Bollinger/ATR/OBV composite score
└────────┬────────┘
         ▼
┌─────────────────┐
│  Grid Strategy  │  Pure algorithms: 4 grid variants with fee-aware profit math
└────────┬────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│     Debate      │◄───►│  Debate Judge   │  LLM judge: 2–5 rounds, decides depth
│  (Bull ↔ Bear)  │     │  (LLM)          │
└────────┬────────┘     └─────────────────┘
         ▼
┌─────────────────┐
│      Risk       │  DeepSeek LLM: risk score 1-10, enumerated risk factors
└────────┬────────┘
         ▼
┌─────────────────┐
│    Advisory     │  DeepSeek LLM: numeric override + weighted synthesis
└────────┬────────┘
         ▼
   buy / hold / sell + confidence + full reasoning chain

   [Follow-up]  Standalone agent called from UI; not in main graph.
                Answers detail questions with full prior-run context.
```

### Agent details

| # | Agent | LLM | Free Data Source | What it does |
|:---|:---|:---|:---|:---|
| 1 | **Orchestrator** | Yes | — | Intent (stock_query / chitchat / out_of_scope), ticker extraction, prompt injection block |
| 2 | **Market Data** | No | yfinance | Real-time price, OHLCV, SMA(20/50/200), RSI(14), MACD; mock fallback |
| 3 | **Macro Env** | No | akshare (CSI 300, SSE, etc.) | Index snapshot, regime detection (BULL / BEAR / SIDEWAYS), north-bound flow |
| 4 | **Sector** | No | akshare (industry / concept) | Sector & concept rankings; maps this stock to its industry and relative performance |
| 5 | **News** | No | yfinance + DuckDuckGo | Multi-source news, title-hash dedup |
| 6 | **Announcement** | No | akshare (Caixin / Eastmoney) | Company filings, financial abstract (ROE, revenue, net profit, debt ratio) |
| 7 | **Social Sentiment** | No | akshare (Eastmoney 股吧) | Retail investor comment score, hot stock rankings |
| 8 | **Sentiment** | Yes | — | Per-article relevance-weighted sentiment, key factors, explainable reasoning |
| 9 | **Fundamental** | Yes | — | Health score 1-10, DCF/PEG numeric anchors, peer comparison, red flag detection |
| 10 | **Momentum** | No | — | Pure-math multi-horizon returns (3d/5d/10d/20d/60d), breakout, volume surge, RS vs CSI 300 |
| 11 | **Quant** | No | — | Classical + advanced signals (MA/RSI/MACD/Bollinger/ATR/Stochastic/OBV), composite -100..+100 |
| 12 | **Grid Strategy** | No | — | 4 grid trading proposals: range, grids, shares, profit per cycle, monthly return |
| 13 | **Debate** | Yes | — | Bull vs Bear structured arguments + rebuttals, dynamic 2–5 rounds |
| 14 | **Debate Judge** | Yes | — | Evaluates debate depth each round; decides continue or conclude |
| 15 | **Risk** | Yes | — | Risk score 1-10, enumerated risk factors, level label |
| 16 | **Advisory** | Yes | — | Numeric override + weighted synthesis: buy/hold/sell + confidence + horizon |
| + | **Follow-up** | Yes | — | Standalone (not in main graph); answers detail questions with full prior-run context |

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| Language | Python 3.11+ |
| Agent Orchestration | LangGraph 0.3+ (StateGraph, conditional edges, self-loops) |
| LLM | DeepSeek (deepseek-chat) via OpenAI-compatible API |
| Market Data | [yfinance](https://github.com/ranaroussi/yfinance) |
| Chinese Data | [akshare](https://github.com/akfamily/akshare) (Eastmoney, Sina, THS, Caixin) |
| News | yfinance + duckduckgo-search |
| Validation | Pydantic v2 |
| UI | Streamlit |
| Email | smtplib (QQ Mail SMTP_SSL on port 465) |
| Package Manager | [uv](https://github.com/astral-sh/uv) |
| Testing | pytest |

---

## Quick Start

### Windows (zero dependencies)

```bat
git clone git@github.com:GOODDAYDAY/FinancialAnalysis.git
cd FinancialAnalysis
scripts\run.bat
```

The launcher will:
1. Install `uv` automatically (via PowerShell, if missing)
2. Create a Python 3.11 venv
3. Install all dependencies
4. Prompt you for a DeepSeek API key (saved to `.env`)
5. Launch Streamlit at http://localhost:8501

### Linux / macOS

```bash
git clone git@github.com:GOODDAYDAY/FinancialAnalysis.git
cd FinancialAnalysis
bash scripts/run.sh
```

Same auto-install behavior using `curl | sh` for `uv`.

### Get a DeepSeek API key

1. Sign up at https://platform.deepseek.com
2. Generate an API key (starts with `sk-...`)
3. Paste it into the prompt when the launcher asks, or edit `.env` manually

---

## Usage

### Web UI

Open http://localhost:8501 and chat with the system:

```
Analyze 600519.SS
What do you think about Tesla?
分析一下贵州茅台
```

After analysis completes, you can ask **follow-up questions** with full agent context preserved:

```
Why did the Bear say it's risky?
What signals drove the quant score?
Explain the long-term grid strategy in detail
What risk factors should I watch for?
```

The system automatically detects whether your message is a new analysis request or a follow-up about the previous analysis.

### Command line: scheduled analysis

```bash
# Analyze the watchlist defined in .env, send email
uv run python scripts/scheduled_analysis.py

# Override watchlist
uv run python scripts/scheduled_analysis.py --tickers 600519.SS,000858.SZ

# Test without sending email
uv run python scripts/scheduled_analysis.py --dry-run

# Single batch summary email instead of one per stock
uv run python scripts/scheduled_analysis.py --summary-only
```

---

## Project Structure

```
FinancialAnalysis/
├── backend/
│   ├── config.py                   # Pydantic settings, .env loading
│   ├── state.py                    # ResearchState TypedDict + Pydantic models
│   ├── llm_client.py               # DeepSeek wrapper with retry-with-reprompt
│   ├── graph.py                    # LangGraph StateGraph builder (16 agents + followup standalone)
│   ├── agents/                     # Each agent in its own sub-package
│   │   ├── orchestrator/
│   │   ├── market_data/
│   │   │   ├── node.py
│   │   │   ├── providers.py        # yfinance live data
│   │   │   └── mock.py             # Demo fallback data
│   │   ├── macro_env/
│   │   │   ├── node.py
│   │   │   └── sources.py          # akshare index snapshots + north-bound flow
│   │   ├── sector/
│   │   │   ├── node.py
│   │   │   └── sources.py          # akshare sector / concept rankings
│   │   ├── news/
│   │   │   ├── node.py
│   │   │   └── sources.py          # yfinance + DuckDuckGo + dedup
│   │   ├── announcement/
│   │   │   ├── node.py
│   │   │   └── sources.py          # akshare Caixin / Eastmoney
│   │   ├── social_sentiment/
│   │   │   ├── node.py
│   │   │   └── sources.py          # akshare Eastmoney 股吧
│   │   ├── sentiment/
│   │   ├── fundamental/
│   │   │   ├── node.py
│   │   │   └── valuation_calc.py   # DCF / PEG / margin-of-safety numeric anchors
│   │   ├── momentum/               # Pure-math multi-horizon momentum, no LLM
│   │   ├── quant/
│   │   │   ├── node.py
│   │   │   └── signals.py          # MA / RSI / MACD / Bollinger / ATR / OBV
│   │   ├── grid_strategy/
│   │   │   ├── node.py
│   │   │   └── calculator.py       # Grid math, fee model, A-share lot sizing
│   │   ├── debate/
│   │   ├── debate_judge/           # LLM judge: decides when debate reaches sufficient depth
│   │   ├── risk/
│   │   ├── advisory/
│   │   └── followup/               # Standalone — called from UI, not in main graph
│   └── notification/
│       ├── email_sender.py         # QQ SMTP_SSL on port 465
│       └── templates.py            # HTML email templates
│
├── frontend/
│   └── app.py                      # Streamlit chat UI
│
├── scripts/
│   ├── run.bat / run.sh            # Zero-dependency launchers
│   ├── scheduled_analysis.py       # Standalone scheduled task entry point
│   ├── scheduled_analysis.bat/.sh  # Wrappers with timestamped logging
│   └── register_schedule.bat       # Windows Task Scheduler registration
│
├── deploy/
│   ├── install_linux.sh            # One-click Linux server installer
│   └── README.md                   # Linux deployment guide
│
├── tests/
│   ├── agents/                     # One test sub-package per agent
│   │   ├── orchestrator/
│   │   ├── market_data/
│   │   ├── macro_env/
│   │   ├── sector/
│   │   ├── news/
│   │   ├── announcement/
│   │   ├── social_sentiment/
│   │   ├── sentiment/
│   │   ├── fundamental/
│   │   ├── momentum/
│   │   ├── quant/
│   │   ├── grid_strategy/
│   │   ├── debate/
│   │   ├── debate_judge/
│   │   ├── risk/
│   │   ├── advisory/
│   │   └── followup/
│   ├── notification/
│   └── e2e/
│       └── test_full_pipeline.py
│
├── requirements/                   # Requirement-driven dev artifacts
│   └── REQ-001-multi-agent-investment-research/
│       ├── requirement.md
│       ├── technical.md
│       └── *.puml
│
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Configuration

All configuration is loaded from `.env` (auto-loaded by `backend/config.py`).

```env
# DeepSeek API
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# LLM tuning
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=4096

# Bull vs Bear debate
DEBATE_MAX_ROUNDS=2
DEBATE_TEMPERATURE=0.7

# Scheduled email watchlist
WATCHLIST=600519.SS,000858.SZ,300750.SZ

# QQ Mail SMTP (use authorization code, NOT QQ password)
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
QQ_EMAIL=your_account@qq.com
QQ_EMAIL_PASSWORD=your_16char_authorization_code
QQ_EMAIL_SENDER_NAME=AI Investment Research
QQ_EMAIL_RECIPIENTS=recipient1@qq.com,recipient2@qq.com
```

### Getting a QQ Mail authorization code

1. Open https://mail.qq.com
2. **Settings** → **Account** → **POP3/IMAP/SMTP service**
3. Enable **IMAP/SMTP service**
4. Click **Generate authorization code** — you'll get a 16-character string
5. Use that string as `QQ_EMAIL_PASSWORD` (your normal QQ password will NOT work)

---

## Testing

Each agent has its own test sub-package under `tests/agents/`. Tests make **real API calls** (no mocks) — they hit DeepSeek, yfinance, and akshare for live data.

```bash
# Run all tests
uv run python -m pytest tests/ -v

# Run only one agent's tests
uv run python -m pytest tests/agents/quant/ -v
uv run python -m pytest tests/agents/grid_strategy/ -v

# Run the full end-to-end pipeline test
uv run python -m pytest tests/e2e/ -v

# Run only fast tests (no LLM calls)
uv run python -m pytest tests/agents/quant/ tests/agents/market_data/ \
  tests/agents/news/ tests/agents/grid_strategy/ tests/notification/ -v
```

---

## Linux Deployment (Singapore or any Linux server)

```bash
# On a fresh Ubuntu/Debian server
git clone git@github.com:GOODDAYDAY/FinancialAnalysis.git /opt/ai-investment
cd /opt/ai-investment
bash deploy/install_linux.sh

# Edit credentials
nano .env

# Start the web app
sudo systemctl start ai-investment-web
sudo systemctl status ai-investment-web

# Start the daily scheduled task (Mon-Fri 17:30 SGT, after A-share market close)
sudo systemctl start ai-investment-scheduled.timer
sudo systemctl list-timers | grep ai-investment
```

The installer:
1. Installs `uv`, creates venv, installs all dependencies
2. Creates `ai-investment-web.service` — Streamlit on `0.0.0.0:8501`, auto-restart
3. Creates `ai-investment-scheduled.service` + `.timer` — daily analysis email at 09:30 UTC (= 17:30 Singapore Time)
4. Configures `ufw` firewall to open port 8501

See [`deploy/README.md`](deploy/README.md) for the full deployment guide, including nginx + HTTPS reverse proxy and systemd timer customization.

---

## Example Output

```
Ticker: 600519.SS (Kweichow Moutai)
Price: $1460.0 (+0.01%)
P/E: 20.37 | RSI: 50.0 | SMA20: 1430

Sentiment: bearish (-0.20, confidence 0.7)
  Key factors: Lost "costliest stock" status to Cambricon, broader China sell-off

Fundamental: 8.5/10
  Red flags: China market concentration, regulatory risk on luxury

Quant: 35/100 (STRONG BUY SIGNAL)
  [+] Above MA200, Price > SMA20, MACD Strong Bullish, Mid 52W Range

Grid Strategy: 45/100 (MARGINAL, 11.15% annual vol)
  Best: Long-term Wide Grid (~4.12%/month)
    Range: 1080 - 1800, 10 grids, 100 shares/grid
    Profit per cycle: 7048 CNY (after 152 fees)

Bull vs Bear Debate (2 rounds, 4 arguments):
  Bull: Fortress fundamentals, MACD bullish, healthy ROE
  Bear: P/E premium leaves no room for error, regulatory risks
  Bear made stronger arguments on valuation...

Risk: 6.5/10 (high)

Recommendation: HOLD (confidence 0.55, long-term)
  Supporting: Strong brand moat, healthy fundamentals
  Dissenting: Premium valuation, regulatory headwinds
```

---

## How the Bull-vs-Bear Debate Works

The debate is implemented as a **LangGraph self-loop with conditional edges** — not a subgraph:

1. After all data collection and analysis agents complete, the debate node is invoked
2. **Round 1**: Bull LLM presents 3 arguments with evidence; Bear LLM responds, citing the Bull's specific points
3. The conditional edge checks `debate_round`:
   - If `< max_rounds` (default 2) → loop back to debate node
   - If `>= max_rounds` → proceed to risk → advisory
4. **Round 2**: Bull and Bear see Round 1 history, attempt rebuttals
5. Final 4 arguments are stored in `debate_history` and fed to the Advisory Agent for synthesis

Both debaters have access to the **Quant Agent's algorithmic signals**, the **Grid Strategy Agent's suitability scoring**, the **akshare financial summary**, and **Eastmoney social sentiment** — preventing AI hallucination since both sides must cite real data points.

---

## Disclaimer

This system is designed for **educational and research purposes only**. It does not constitute financial advice. AI-generated analysis can be wrong, biased, or incomplete. Past performance does not guarantee future results. Always consult a qualified financial advisor before making investment decisions.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) — stateful multi-agent orchestration
- [DeepSeek](https://platform.deepseek.com) — cost-effective LLM API
- [yfinance](https://github.com/ranaroussi/yfinance) — global market data
- [akshare](https://github.com/akfamily/akshare) — comprehensive Chinese financial data
- [Streamlit](https://streamlit.io) — rapid UI prototyping
- [uv](https://github.com/astral-sh/uv) — fast Python package management
