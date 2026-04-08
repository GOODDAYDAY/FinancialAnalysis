"""
Observability module — token accounting, audit trail, structured events.

Provides:
  - token_tracker: per-agent and per-request token usage with simple cost
    estimation. Used for MLSecOps budget alerts and cost reporting.
  - audit_trail: append-only JSONL log of all LLM interactions and
    security events. Feeds the risk register with real-world evidence.

Agents call into this module through the thin helpers below so that
the main pipeline stays decoupled from storage / tracing backends.
"""

from backend.observability.token_tracker import (
    TokenTracker,
    get_tracker,
    record_llm_call,
    current_request_summary,
)
from backend.observability.audit_trail import (
    audit_log,
    AuditEvent,
    AuditKind,
)

__all__ = [
    "TokenTracker",
    "get_tracker",
    "record_llm_call",
    "current_request_summary",
    "audit_log",
    "AuditEvent",
    "AuditKind",
]
