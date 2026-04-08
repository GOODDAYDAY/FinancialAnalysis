# AI Security Risk Register

> **Scope:** Multi-Agent Investment Research System (REQ-001)
> **Frameworks referenced:** OWASP Top 10 for LLM Applications v1.1, NIST AI 600-1 (GenAI Profile), MITRE ATLAS
> **Owner:** Platform team
> **Last reviewed:** 2026-04-07

## 1. Purpose

This register inventories the AI-specific security risks facing the system, maps each to an OWASP LLM category, documents the mitigation that currently lives in code, and points at the test that proves the mitigation works. It is the single source of truth for the MLSecOps audit and for the assignment's "AI Security" pillar.

## 2. Threat Model Summary

The system accepts natural-language investment queries from authenticated web users, forwards them to a LangGraph pipeline of 16 agents, and returns a BUY/HOLD/SELL recommendation. The **trust boundary** sits between the Streamlit front end and `backend/agents/orchestrator/node.py`.

External surfaces:
- DeepSeek LLM API (outbound)
- yfinance / akshare market data (outbound)
- SMTP to QQ Mail (outbound, scheduler only)
- Streamlit WebSocket (inbound, from user)

Assets to protect: user queries (may contain PII), the DeepSeek API key, the system-prompt templates (IP), the audit trail (integrity), and the final recommendation (must not be manipulated).

## 3. Risk Entries

| ID   | Risk                                              | OWASP / ATLAS       | Likelihood | Impact  | Mitigation (code)                                                                                          | Test evidence                                         |
|------|---------------------------------------------------|---------------------|-----------|---------|-------------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| R-01 | Direct prompt injection (ignore-previous, DAN)    | LLM01               | High      | High    | `backend/security/sanitizer.py` + `injection_patterns.py`; critical hits block at orchestrator entry       | `tests/security/test_injection_patterns.py`           |
| R-02 | Indirect prompt injection via news article body   | LLM01               | Medium    | High    | News articles are summarized, not passed verbatim; output filter scrubs LLM responses                      | `tests/security/test_output_filter.py` (leak detect)  |
| R-03 | Sensitive information disclosure (PII in prompts) | LLM06               | Medium    | High    | `backend/security/pii_detector.py` redacts emails / phones / ID cards / keys before the LLM sees them      | `tests/security/test_pii_detector.py`                  |
| R-04 | System-prompt regurgitation                       | LLM06               | Medium    | Medium  | `backend/security/output_filter.py` matches known leak markers and replaces with `[LEAK-REDACTED]`         | `tests/security/test_output_filter.py`                 |
| R-05 | Outbound data exfiltration via generated URL      | LLM06 / ATLAS T0040 | Low       | High    | Output filter blocks long-query-string URLs with `[BLOCKED-URL]`                                           | `tests/security/test_output_filter.py`                 |
| R-06 | Investment-manipulation instruction               | LLM09               | Medium    | High    | `investment_manipulation` regex in pattern library; advisory post-processor overrides LLM if math disagrees | `tests/security/test_injection_patterns.py`; Stage 6 review |
| R-07 | Overreliance on LLM verdict (always-HOLD bias)    | LLM09               | High      | Medium  | Numeric composite-score override in `backend/agents/advisory/node.py:_compute_decision_override`            | Stage 6 review (traced via `reasoning_chain.override_applied`) |
| R-08 | DoS via oversized input                           | LLM04               | Low       | Medium  | `MAX_INPUT_LENGTH=2000` in sanitizer; `SOFT_BUDGET_TOKENS=200_000` in token_tracker                        | `tests/security/test_sanitizer.py::test_length_cap_applied` |
| R-09 | API-key leakage (DeepSeek / akshare)              | LLM06               | Low       | High    | `.env` in `.gitignore`; PII detector flags `sk-` and long-hex secrets if they ever appear in text          | `tests/security/test_pii_detector.py`                 |
| R-10 | Insecure output handling (XSS in Streamlit)       | LLM02               | Low       | Medium  | Streamlit auto-escapes markdown; output filter strips control chars                                         | Manual review (Stage 4)                                |
| R-11 | Model supply-chain compromise                     | LLM05               | Low       | Critical| Single vetted vendor (DeepSeek); model ID pinned in `backend/config.py`; CI pins dependency hashes         | `.github/workflows/ci.yml` pip audit step             |
| R-12 | Training-data poisoning of downstream embedding   | LLM03               | Very Low  | Low     | System does not fine-tune; embeddings are not used                                                          | N/A (out of scope)                                    |
| R-13 | Excessive agency (tool misuse)                    | LLM08               | Medium    | High    | Agents have zero real-world side effects — no order placement, no email from analysis path. Scheduler email path runs outside the agent graph | Code review                                           |
| R-14 | Audit trail tampering                             | Compliance          | Low       | High    | Append-only JSONL in `backend/observability/audit_trail.py`; file is written under lock                    | Manual: inspect `logs/audit_trail.jsonl`              |
| R-15 | Hallucinated financial claims                     | LLM09               | High      | High    | Quant + Momentum + Valuation agents supply numeric anchors; Disclaimer injected by `RecommendationOutput`  | Stage 6 review                                        |

## 4. Residual Risk

After the mitigations above, the highest residual risks are **R-02 (indirect injection via news)** and **R-15 (hallucinated claims)**. Both are accepted because:
- The advisory node requires quantitative agreement before overriding HOLD; this makes it expensive for an attacker to move the verdict with a single planted news article.
- Every recommendation carries a disclaimer under `RecommendationOutput.disclaimer`, and the UI renders it prominently.

## 5. Review Cadence

- **Weekly:** Re-run `pytest tests/security/`
- **Per release:** Update this register; add rows for any new agent/tool; re-run Stage-4 security review (`/req-4-security`)
- **Quarterly:** Cross-check against the latest OWASP LLM Top 10 revision
