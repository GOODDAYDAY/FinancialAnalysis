"""
Per-request LLM token tracker.

DeepSeek (OpenAI-compatible) returns usage.prompt_tokens and
usage.completion_tokens in every response. This module aggregates those
numbers across a single analysis request so we can:
  - show a cost summary in the UI
  - enforce a soft budget (warn if > BUDGET_TOKENS)
  - feed the MLSecOps pipeline dashboards

State is kept in a thread-local (a single Streamlit / CLI request is
one thread). For multi-threaded servers, each request should get a
fresh tracker; `get_tracker()` handles that via `threading.local`.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Cost constants — DeepSeek pricing as of 2026-04 (USD per 1M tokens).
# These are approximations used for reporting only; swap as needed.
COST_PER_MTOK_INPUT = 0.27
COST_PER_MTOK_OUTPUT = 1.10

# Soft budget per request — logged as warning if exceeded.
SOFT_BUDGET_TOKENS = 200_000


@dataclass
class LLMCallRecord:
    agent: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str


@dataclass
class TokenTracker:
    calls: list[LLMCallRecord] = field(default_factory=list)

    @property
    def total_prompt(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def total_completion(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def total(self) -> int:
        return self.total_prompt + self.total_completion

    def estimated_cost_usd(self) -> float:
        cost = (
            self.total_prompt / 1_000_000 * COST_PER_MTOK_INPUT +
            self.total_completion / 1_000_000 * COST_PER_MTOK_OUTPUT
        )
        return round(cost, 4)

    def by_agent(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for c in self.calls:
            row = out.setdefault(c.agent, {"calls": 0, "prompt": 0, "completion": 0, "total": 0})
            row["calls"] += 1
            row["prompt"] += c.prompt_tokens
            row["completion"] += c.completion_tokens
            row["total"] += c.total_tokens
        return out

    def summary(self) -> dict:
        return {
            "calls": len(self.calls),
            "prompt_tokens": self.total_prompt,
            "completion_tokens": self.total_completion,
            "total_tokens": self.total,
            "estimated_cost_usd": self.estimated_cost_usd(),
            "by_agent": self.by_agent(),
            "budget_exceeded": self.total > SOFT_BUDGET_TOKENS,
        }

    def reset(self) -> None:
        self.calls.clear()


_local = threading.local()


def get_tracker() -> TokenTracker:
    """Return (creating if needed) the current thread's tracker."""
    tracker: Optional[TokenTracker] = getattr(_local, "tracker", None)
    if tracker is None:
        tracker = TokenTracker()
        _local.tracker = tracker
    return tracker


def record_llm_call(agent: str, usage, model: str) -> None:
    """
    Record an LLM call. `usage` is the OpenAI-compatible usage object
    (has prompt_tokens / completion_tokens / total_tokens attributes).
    Agents pass their own name so we can attribute cost.
    """
    if usage is None:
        return
    try:
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    except Exception as e:
        logger.warning("token_tracker: could not parse usage (%s): %s", usage, e)
        return

    tracker = get_tracker()
    tracker.calls.append(LLMCallRecord(
        agent=agent,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
    ))

    if tracker.total > SOFT_BUDGET_TOKENS:
        logger.warning(
            "Token budget exceeded: %d tokens used (budget %d)",
            tracker.total, SOFT_BUDGET_TOKENS,
        )


def current_request_summary() -> dict:
    """Snapshot of the current thread's token usage for reporting."""
    return get_tracker().summary()
