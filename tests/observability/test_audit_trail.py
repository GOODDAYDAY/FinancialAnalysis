"""
Tests for the append-only JSONL audit trail.

Covers: event writing, format correctness, thread safety, best-effort error handling,
and the quick() convenience function.
"""

import json
import os
import threading
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.observability.audit_trail import (
    AuditEvent,
    AuditKind,
    audit_log,
    quick,
    _AUDIT_PATH,
    _LOCK,
    _ensure_dir,
)


def test_audit_event_auto_timestamp():
    event = AuditEvent(kind=AuditKind.INPUT_SANITIZED, agent="test")
    assert event.timestamp != ""
    # Should be a valid ISO format
    from datetime import datetime
    datetime.fromisoformat(event.timestamp)


def test_audit_event_explicit_timestamp():
    ts = "2026-01-01T00:00:00+00:00"
    event = AuditEvent(kind=AuditKind.INPUT_SANITIZED, agent="test", timestamp=ts)
    assert event.timestamp == ts


def test_audit_log_writes_jsonl(tmp_path, monkeypatch):
    log_file = tmp_path / "audit_trail.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(log_file))
    # Force re-read of env var by patching the module-level path
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    audit_log(AuditEvent(
        kind=AuditKind.INPUT_SANITIZED,
        agent="sanitizer",
        message="test injection blocked",
        ticker="600519.SS",
        request_id="req-001",
    ))

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["kind"] == "input_sanitized"
    assert record["agent"] == "sanitizer"
    assert record["message"] == "test injection blocked"
    assert record["ticker"] == "600519.SS"
    assert record["request_id"] == "req-001"
    assert "timestamp" in record


def test_audit_log_appends(tmp_path, monkeypatch):
    log_file = tmp_path / "audit_trail.jsonl"
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    audit_log(AuditEvent(kind=AuditKind.LLM_CALL, agent="advisory", message="call 1"))
    audit_log(AuditEvent(kind=AuditKind.LLM_CALL, agent="advisory", message="call 2"))

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["message"] == "call 1"
    assert json.loads(lines[1])["message"] == "call 2"


def test_audit_log_all_event_kinds(tmp_path, monkeypatch):
    log_file = tmp_path / "audit_trail.jsonl"
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    for kind in AuditKind:
        audit_log(AuditEvent(kind=kind, agent="test", message=str(kind.value)))

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == len(AuditKind)
    kinds_written = [json.loads(line)["kind"] for line in lines]
    assert set(kinds_written) == {k.value for k in AuditKind}


def test_audit_log_ensure_ascii_false(tmp_path, monkeypatch):
    """Chinese characters should be stored as-is, not \\uXXXX escapes."""
    log_file = tmp_path / "audit_trail.jsonl"
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    audit_log(AuditEvent(
        kind=AuditKind.AGENT_ERROR,
        agent="quant",
        message="处理失败: 数据异常",
    ))

    raw = log_file.read_text(encoding="utf-8")
    assert "处理失败" in raw
    # Verify NOT escaped as \uXXXX in the raw JSON
    assert "\\u5904" not in raw


def test_audit_log_thread_safety(tmp_path, monkeypatch):
    """Multiple threads writing concurrently should not corrupt JSONL."""
    log_file = tmp_path / "audit_trail.jsonl"
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    num_threads = 10
    writes_per_thread = 20

    def writer(thread_id):
        for i in range(writes_per_thread):
            audit_log(AuditEvent(
                kind=AuditKind.LLM_CALL,
                agent=f"thread-{thread_id}",
                message=f"msg-{i}",
            ))

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == num_threads * writes_per_thread
    # Every line should be valid JSON
    for line in lines:
        json.loads(line)  # raises if corrupted


def test_audit_log_failure_does_not_raise(tmp_path, monkeypatch, caplog):
    """When disk write fails, audit_log should log warning and not raise."""
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", Path("/nonexistent/dir/audit.jsonl"))

    # Should not raise
    audit_log(AuditEvent(kind=AuditKind.INPUT_SANITIZED, agent="test", message="test"))


def test_quick_convenience(tmp_path, monkeypatch):
    log_file = tmp_path / "audit_trail.jsonl"
    import backend.observability.audit_trail as mod
    monkeypatch.setattr(mod, "_AUDIT_PATH", log_file)

    quick(AuditKind.SECURITY_ALERT, agent="scanner", message="xss found", severity="high")

    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    record = json.loads(lines[0])
    assert record["kind"] == "security_alert"
    assert record["agent"] == "scanner"
    assert record["message"] == "xss found"
    assert record["details"]["severity"] == "high"


def test_ensure_dir_creates_path(tmp_path, monkeypatch):
    nested = tmp_path / "deep" / "nested" / "dir"
    import backend.observability.audit_trail as mod
    orig = mod._AUDIT_PATH
    monkeypatch.setattr(mod, "_AUDIT_PATH", nested / "audit.jsonl")
    _ensure_dir()
    assert nested.exists()
    monkeypatch.setattr(mod, "_AUDIT_PATH", orig)
