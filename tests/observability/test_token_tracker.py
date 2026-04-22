"""
Tests for the LLM token tracker.

Covers: token aggregation, cost calculation, per-agent breakdown,
budget warnings, thread-local isolation, and error handling on bad usage data.
"""

import pytest
from unittest.mock import patch

from backend.observability.token_tracker import (
    TokenTracker,
    LLMCallRecord,
    record_llm_call,
    get_tracker,
    current_request_summary,
    SOFT_BUDGET_TOKENS,
    COST_PER_MTOK_INPUT,
    COST_PER_MTOK_OUTPUT,
)


class TestTokenTracker:
    def test_empty_tracker(self):
        t = TokenTracker()
        assert t.total_prompt == 0
        assert t.total_completion == 0
        assert t.total == 0
        assert t.estimated_cost_usd() == 0.0
        assert t.calls == []

    def test_single_call(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(
            agent="advisory", prompt_tokens=100, completion_tokens=50,
            total_tokens=150, model="deepseek-chat",
        ))
        assert t.total_prompt == 100
        assert t.total_completion == 50
        assert t.total == 150

    def test_multiple_calls_aggregate(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(agent="a", prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m"))
        t.calls.append(LLMCallRecord(agent="b", prompt_tokens=200, completion_tokens=100, total_tokens=300, model="m"))
        assert t.total_prompt == 300
        assert t.total_completion == 150
        assert t.total == 450

    def test_cost_calculation(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(
            agent="x", prompt_tokens=1_000_000, completion_tokens=1_000_000,
            total_tokens=2_000_000, model="m",
        ))
        expected = (1_000_000 / 1_000_000 * COST_PER_MTOK_INPUT +
                    1_000_000 / 1_000_000 * COST_PER_MTOK_OUTPUT)
        assert t.estimated_cost_usd() == round(expected, 4)

    def test_by_agent(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(agent="advisory", prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m"))
        t.calls.append(LLMCallRecord(agent="advisory", prompt_tokens=200, completion_tokens=100, total_tokens=300, model="m"))
        t.calls.append(LLMCallRecord(agent="quant", prompt_tokens=50, completion_tokens=25, total_tokens=75, model="m"))
        breakdown = t.by_agent()
        assert len(breakdown) == 2
        assert breakdown["advisory"]["calls"] == 2
        assert breakdown["advisory"]["prompt"] == 300
        assert breakdown["advisory"]["total"] == 450
        assert breakdown["quant"]["calls"] == 1

    def test_summary_structure(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(agent="a", prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m"))
        s = t.summary()
        assert "calls" in s
        assert "prompt_tokens" in s
        assert "completion_tokens" in s
        assert "total_tokens" in s
        assert "estimated_cost_usd" in s
        assert "by_agent" in s
        assert "budget_exceeded" in s
        assert s["calls"] == 1
        assert s["budget_exceeded"] is False

    def test_budget_exceeded(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(
            agent="a", prompt_tokens=SOFT_BUDGET_TOKENS + 1, completion_tokens=0,
            total_tokens=SOFT_BUDGET_TOKENS + 1, model="m",
        ))
        assert t.summary()["budget_exceeded"] is True

    def test_reset(self):
        t = TokenTracker()
        t.calls.append(LLMCallRecord(agent="a", prompt_tokens=100, completion_tokens=50, total_tokens=150, model="m"))
        t.reset()
        assert t.total == 0
        assert len(t.calls) == 0


class TestRecordLLMCall:
    def setup_method(self):
        # Reset thread-local tracker before each test
        import backend.observability.token_tracker as mod
        if hasattr(mod._local, "tracker"):
            del mod._local.tracker

    def _make_usage(self, prompt=100, completion=50):
        u = type("Usage", (), {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        })()
        return u

    def test_records_single_call(self):
        record_llm_call("test_agent", self._make_usage(100, 50), "deepseek-chat")
        tracker = get_tracker()
        assert len(tracker.calls) == 1
        assert tracker.calls[0].agent == "test_agent"
        assert tracker.calls[0].prompt_tokens == 100

    def test_aggregates_multiple_calls(self):
        record_llm_call("a", self._make_usage(100, 50), "m")
        record_llm_call("b", self._make_usage(200, 100), "m")
        tracker = get_tracker()
        assert tracker.total_prompt == 300
        assert tracker.total_completion == 150

    def test_none_usage_ignored(self):
        record_llm_call("a", None, "m")
        tracker = get_tracker()
        assert len(tracker.calls) == 0

    def test_budget_warning_logged(self, caplog):
        huge = self._make_usage(SOFT_BUDGET_TOKENS + 1, 0)
        record_llm_call("a", huge, "m")
        assert "budget exceeded" in caplog.text.lower()

    def test_current_request_summary(self):
        record_llm_call("agent1", self._make_usage(100, 50), "m")
        record_llm_call("agent2", self._make_usage(200, 100), "m")
        summary = current_request_summary()
        assert summary["calls"] == 2
        assert summary["prompt_tokens"] == 300
        assert summary["total_tokens"] == 450
