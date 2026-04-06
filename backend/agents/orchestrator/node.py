"""Orchestrator agent: intent classification, ticker extraction, prompt injection check."""

import logging
from backend.llm_client import call_llm_structured
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    "ignore previous", "ignore all instructions", "system prompt",
    "you are now", "disregard", "forget your instructions",
    "reveal your prompt", "show me your instructions",
]


class IntentResult(BaseModel):
    """Structured output for intent classification."""
    intent: str = Field(description="One of: stock_query, stock_comparison, chitchat, out_of_scope")
    ticker: str = Field(default="", description="Extracted stock ticker symbol, e.g. AAPL")
    company_name: str = Field(default="", description="Company name if mentioned")
    explanation: str = Field(default="", description="Brief explanation of intent classification")


def orchestrator_node(state: dict) -> dict:
    """F-01, F-02, F-03: Parse intent, extract ticker, check for injection."""
    query = state.get("user_query", "")
    logger.info("Orchestrator processing query: %s", query[:100])

    # F-14: Prompt injection check (runs before LLM call)
    query_lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern in query_lower:
            logger.warning("Prompt injection detected: pattern='%s'", pattern)
            return {
                "intent": "rejected",
                "ticker": "",
                "reasoning_chain": [{"agent": "orchestrator", "action": "rejected", "reason": "prompt injection detected"}],
                "errors": [{"agent": "orchestrator", "error": "Prompt injection detected"}],
            }

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
        "reasoning_chain": [{
            "agent": "orchestrator",
            "intent": result.intent,
            "ticker": ticker,
            "explanation": result.explanation,
        }],
    }
