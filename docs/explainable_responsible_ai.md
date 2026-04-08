# Explainable & Responsible AI

> **Scope:** Multi-Agent Investment Research System (REQ-001)
> **Frameworks:** Singapore IMDA Model AI Governance Framework v2, NIST AI RMF (GOVERN/MAP/MEASURE/MANAGE), EU AI Act Art. 13 (transparency)
> **Last reviewed:** 2026-04-07

## 1. Design principles

| Principle              | How the system implements it                                                                                              |
|------------------------|---------------------------------------------------------------------------------------------------------------------------|
| **Human-centricity**   | All output is advisory; the disclaimer on every recommendation reminds users the tool is not a licensed financial advisor. |
| **Explainability**     | Every agent writes to `reasoning_chain`; the UI renders the full chain so the user can trace *why* a verdict was reached.  |
| **Fairness**           | No demographic inputs are used. Analysis is ticker-scoped; no user profiling.                                              |
| **Safety / robustness**| Numeric agents (Quant, Momentum, Valuation) supply ground-truth anchors; advisory overrides LLM when math disagrees.       |
| **Accountability**     | Append-only audit trail; git-tracked prompts; deterministic LangGraph topology.                                            |

## 2. Explainability implementation

### 2.1 Reasoning chain as first-class state

`ResearchState.reasoning_chain` is an `Annotated[list[dict], operator.add]` — every agent appends a dict describing the inputs it used, the score it produced, and (where applicable) the rule it fired. The front end renders this chain so the user sees a step-by-step trace.

Example entry (Advisory agent):
```json
{
  "agent": "advisory",
  "recommendation": "buy",
  "confidence": 0.72,
  "composite_score": 41.5,
  "override_applied": true,
  "override_rule": "strong_short_term_rally",
  "supporting": ["5-day +8.3%", "breakout above 20d high", "OBV confirms"],
  "dissenting": ["RSI near 70"]
}
```

### 2.2 Numeric anchors behind every qualitative claim

- **Fundamental** — now carries `fundamental.valuation` with PEG, DCF-per-share, margin of safety, earnings yield (see `backend/agents/fundamental/valuation_calc.py`).
- **Quant** — classical + advanced signals (Bollinger, ATR, Stochastic, OBV) all emit `{name, type, detail, weight}`.
- **Momentum** — per-horizon returns (3d/5d/10d/20d/60d), range position, breakout flag, relative strength vs CSI 300.
- **Debate judge** — bull/bear strength scores (0-100) and `unresolved_points`.

This makes the LLM's qualitative summary falsifiable: the reviewer can recompute the numbers from the raw series.

### 2.3 Advisory override transparency

When the numeric composite score disagrees with the LLM's verdict, `advisory_node` rewrites the recommendation and prepends an `[AUTO-OVERRIDE]` block to `reasoning.reasoning`. `reasoning_chain` records `override_applied=True` plus `override_rule`, so an auditor can replay the decision offline.

## 3. Responsible-AI controls

### 3.1 Mandatory disclaimer

`RecommendationOutput.disclaimer` carries a fixed-text disclaimer that is serialized with every recommendation. The UI renders it as a callout. The LLM is not allowed to rewrite it — it's a Pydantic default.

### 3.2 No tool with real-world side effects in the user path

The agent graph does not place orders, move funds, or send email. The only outbound I/O is read-only market data + LLM calls. The scheduler-email path is a separate script that runs outside the graph and only emails pre-filtered text reports.

### 3.3 Input / output safety (cross-ref security module)

- `backend/security/sanitizer.py` runs at the trust boundary.
- `backend/security/output_filter.py` runs before any LLM text reaches the user or the audit log.
- See `docs/ai_security_risk_register.md` for the full control matrix.

### 3.4 Bias considerations

The system does *not* use any demographic, protected-class, or user-profile features. The only inputs are a user query and a stock ticker. Recommendation bias, if any, comes from the underlying LLM; the numeric override layer is the primary mitigation — it de-weights the LLM when math disagrees.

## 4. IMDA Model AI Governance Framework mapping

| IMDA pillar                           | Our implementation                                                                   |
|---------------------------------------|--------------------------------------------------------------------------------------|
| Internal governance structures        | REQ-001 workflow + Stage-6 review + risk register                                    |
| Determining the level of human oversight | All recommendations are advisory; disclaimer + UI callout                          |
| Operations management — data          | No PII stored; market data is public                                                 |
| Operations management — model         | Single vetted LLM (DeepSeek); model ID pinned                                        |
| Stakeholder interaction — transparency | Full reasoning chain rendered in UI; audit trail persisted                          |
| Stakeholder interaction — feedback     | Users can retry a query; follow-up questions preserve full context                   |

## 5. Limitations acknowledged

1. The DeepSeek LLM is a third-party model with unknown training data. We do not control its biases.
2. The 8% growth assumption in `valuation_calc.compute_simple_dcf` is a placeholder; real use should override per-ticker.
3. News sentiment depends on the quality of the news providers (akshare, Eastmoney). Garbage in, garbage out.
4. The system is Chinese A-share first; US and HK ticker coverage is correct but thinner.

Each of the above is disclosed to the user via the reasoning chain and the disclaimer.
