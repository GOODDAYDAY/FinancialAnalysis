"""Orchestrator agent: intent classification, ticker extraction, prompt injection check."""

import logging
from backend.llm_client import call_llm_structured
from backend.utils.language import detect_language
from backend.security import sanitize_user_input
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """Structured output for intent classification."""
    intent: str = Field(description="One of: stock_query, stock_comparison, chitchat, out_of_scope")
    ticker: str = Field(default="", description="Extracted stock ticker symbol, e.g. AAPL")
    company_name: str = Field(default="", description="Company name if mentioned")
    explanation: str = Field(default="", description="Brief explanation of intent classification")


def orchestrator_node(state: dict) -> dict:
    """F-01, F-02, F-03: Parse intent, extract ticker, check for injection, detect language."""
    raw_query = state.get("user_query", "")
    language = detect_language(raw_query)

    # F-14: Full security pipeline — injection detection, PII redaction,
    # length cap, control-char stripping. Centralized in backend.security.
    sanitized = sanitize_user_input(raw_query)
    if sanitized.blocked:
        logger.warning("Input blocked by sanitizer: %s", sanitized.reasons)
        try:
            from backend.observability.audit_trail import audit_log, AuditEvent, AuditKind
            audit_log(AuditEvent(
                kind=AuditKind.INPUT_BLOCKED,
                agent="orchestrator",
                message="; ".join(sanitized.reasons),
                details={"injection_hits": sanitized.injection_matches},
            ))
        except Exception:
            pass
        return {
            "intent": "rejected",
            "ticker": "",
            "language": language,
            "reasoning_chain": [{
                "agent": "orchestrator",
                "action": "rejected",
                "reason": "; ".join(sanitized.reasons),
                "injection_hits": sanitized.injection_matches,
            }],
            "errors": [{"agent": "orchestrator", "error": f"Input rejected: {sanitized.reasons}"}],
        }

    if sanitized.reasons:
        logger.info("Sanitizer applied: %s", sanitized.reasons)

    query = sanitized.cleaned
    logger.info("Orchestrator processing query: %s (language=%s)", query[:100], language)

    system_prompt = (
        "You are an intent classification agent for a stock investment research system. "
        "Classify the user's query and extract any stock ticker symbols mentioned. "
        "Valid intents: stock_query (analyze a stock), stock_comparison (compare stocks), "
        "chitchat (casual conversation), out_of_scope (trading execution, non-stock topics). "
        "If the user mentions a company name, also provide the stock ticker."
    )

    result = call_llm_structured(
        user_prompt=f"Classify this query: \"{query}\"",
        response_model=IntentResult,
        system_prompt=system_prompt,
    )

    ticker = result.ticker.upper().strip() if result.ticker else ""
    logger.info("Intent classified: intent=%s, ticker=%s", result.intent, ticker)

    return {
        "intent": result.intent,
        "ticker": ticker,
        "language": language,
        "reasoning_chain": [{
            "agent": "orchestrator",
            "intent": result.intent,
            "ticker": ticker,
            "language": language,
            "explanation": result.explanation,
        }],
    }
