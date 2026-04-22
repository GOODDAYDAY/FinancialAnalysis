"""
Append-only JSONL audit trail for security and compliance events.

Purpose: every security-relevant event (input sanitization blocks,
output filter flags, LLM errors, tool invocations, advisory overrides)
is written to `logs/audit_trail.jsonl` so that auditors can replay the
session. This is the primary evidence for the AI security risk register.

Format: one JSON object per line — never mutate existing lines. File
is created on first write; the caller is responsible for rotating or
archiving it in production.

Design constraints:
  - No external dependencies (stdlib only)
  - Thread-safe via a module-level lock
  - Best-effort: if disk is full, log a warning and keep going
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AuditKind(str, Enum):
    INPUT_SANITIZED = "input_sanitized"
    INPUT_BLOCKED = "input_blocked"
    OUTPUT_FILTERED = "output_filtered"
    LLM_CALL = "llm_call"
    LLM_ERROR = "llm_error"
    AGENT_ERROR = "agent_error"
    ADVISORY_OVERRIDE = "advisory_override"
    TOOL_INVOCATION = "tool_invocation"
    SECURITY_ALERT = "security_alert"


@dataclass
class AuditEvent:
    kind: AuditKind
    agent: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ticker: str = ""
    request_id: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


_LOCK = threading.Lock()
_AUDIT_PATH = Path(os.environ.get("AUDIT_LOG_PATH", "logs/audit_trail.jsonl"))


def _ensure_dir() -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning("Could not create audit log dir %s: %s", _AUDIT_PATH.parent, e)


def audit_log(event: AuditEvent) -> None:
    """
    Append an event to the audit trail. Never raises — failures are
    logged to the normal logger so the main pipeline keeps running.
    """
    try:
        _ensure_dir()
        record = asdict(event)
        # Enum -> string
        record["kind"] = event.kind.value if isinstance(event.kind, AuditKind) else str(event.kind)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _LOCK:
            with open(_AUDIT_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.warning("audit_log failed (non-fatal): %s", e)


def quick(kind: AuditKind, agent: str, message: str, **details) -> None:
    """Convenience shortcut: audit_log(AuditEvent(...)) in one call."""
    audit_log(AuditEvent(
        kind=kind,
        agent=agent,
        message=message,
        details=dict(details),
    ))
