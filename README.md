# Financial Analysis — Multi-Agent Investment Research System

> An explainable, multi-agent AI system for stock investment research, built with **LangGraph** and **DeepSeek**. Eleven specialized agents — including a Bull-vs-Bear debate engine, a pure-algorithmic Quant referee, and a Grid Trading Strategy planner — collaborate to produce transparent buy/hold/sell recommendations for Chinese A-shares, Hong Kong, and global stocks.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.3+-green.svg)](https://github.com/langchain-ai/langgraph)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek-purple.svg)](https://platform.deepseek.com)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io)

---

## Highlights

- **11 specialized agents** organized in a LangGraph state machine, each living in its own sub-package for clean ownership
- **Bull vs Bear debate** — two LLM agents argue 2 rounds with rebuttals, citing real data points from upstream agents
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

### Pipeline (13 steps, 11 agents)

```
User Query
    │
    ▼
┌─────────────────┐
│  Orchestrator   │  Intent classification, ticker extraction, prompt-injection defense
└────────┬────────┘
         ▼
┌─────────────────┐
│  Market Data    │  yfinance: price, OHLCV, SMA/RSI/MACD computation
└────────┬────────┘
         ▼
┌─────────────────┐
│      News       │  yfinance + DuckDuckGo, dedup by title hash
└────────┬────────┘
         ▼
┌─────────────────┐
│  Announcement   │  akshare: company filings, financial summary (ROE, revenue)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Social Sentiment│  akshare: Eastmoney 股吧 comment scores, hot rankings
└────────┬────────┘
         ▼
┌─────────────────┐
│   Sentiment     │  DeepSeek LLM: explainable sentiment with key factors
└────────┬────────┘
         ▼
┌─────────────────┐
│   Fundamental   │  DeepSeek LLM: financial health score, red flags
└────────┬────────┘
         ▼
┌─────────────────┐
│      Quant      │  Pure algorithms: composite -100..+100 score, no LLM
└────────┬────────┘
         ▼
┌─────────────────┐
│  Grid Strategy  │  Pure algorithms: 4 grid variants with fee-aware profit
└────────┬────────┘
         ▼
┌─────────────────┐
│     Debate      │  Bull LLM ↔ Bear LLM, 2 rounds with rebuttals (self-loop)
└────────┬────────┘
         ▼
┌─────────────────┐
│      Risk       │  DeepSeek LLM: risk scoring, factor enumeration
└────────┬────────┘
         ▼
┌─────────────────┐
│    Advisory     │  DeepSeek LLM: weighted synthesis, final recommendation
└────────┬────────┘
         ▼
   buy / hold / sell + confidence + reasoning chain
```

### Agent details

| # | Agent | LLM | Free Data Source | What it does |
|:---|:---|:---|:---|:---|
| 1 | **Orchestrator** | Yes | — | Intent (stock_query / chitchat / out_of_scope), ticker extraction, prompt injection block |
| 2 | **Market Data** | No | yfinance | Real-time price, OHLCV, SMA(20/50/200), RSI(14), MACD; mock fallback |
| 3 | **News** | No | yfinance + DuckDuckGo | Multi-source news, title-hash dedup |
| 4 | **Announcement** | No | akshare (Caixin / Eastmoney) | Company news, financial abstract (ROE, revenue, net profit, debt ratio) |
| 5 | **Social Sentiment** | No | akshare (Eastmoney 股吧) | Retail investor comment score, hot stock rankings |
| 6 | **Sentiment** | Yes | — | Per-article sentiment, key factors, explainable reasoning |
| 7 | **Fundamental** | Yes | — | Health score 1-10, peer comparison, red flag detection |
| 8 | **Quant** | No | — | Pure-math composite score from MA / RSI / MACD / 52W range / P/E |
| 9 | **Grid Strategy** | No | — | 4 grid trading proposals: range, grids, shares, profit per cycle, monthly return |
| 10 | **Debate** | Yes | — | Bull vs Bear, 2 rounds, structured arguments + rebuttals |
| 11 | **Risk** | Yes | — | Risk score 1-10, enumerated risk factors, level label |
| 12 | **Advisory** | Yes | — | Weighted synthesis: buy/hold/sell + confidence + horizon |
| + | **Follow-up** | Yes | — | Answers detail questions using preserved context from all agents |

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
│   ├── graph.py                    # LangGraph StateGraph builder (11 agents)
│   ├── agents/                     # Each agent in its own sub-package
│   │   ├── orchestrator/
│   │   ├── market_data/
│   │   │   ├── node.py
│   │   │   ├── providers.py        # yfinance live data
│   │   │   └── mock.py             # Demo fallback data
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
│   │   ├── quant/
│   │   │   ├── node.py
│   │   │   └── signals.py          # MA / RSI / MACD / range / P/E signal computation
│   │   ├── grid_strategy/
│   │   │   ├── node.py
│   │   │   └── calculator.py       # Grid math, fee model, A-share lot sizing
│   │   ├── debate/
│   │   ├── risk/
│   │   ├── advisory/
│   │   └── followup/               # Follow-up Q&A with full context
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
│   │   ├── news/
│   │   ├── announcement/
│   │   ├── social_sentiment/
│   │   ├── sentiment/
│   │   ├── fundamental/
│   │   ├── quant/
│   │   ├── grid_strategy/
│   │   ├── debate/
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
