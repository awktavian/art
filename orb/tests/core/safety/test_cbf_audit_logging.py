"""Unit tests for CBF Audit Logging.

CREATED: December 20, 2025
PURPOSE: Test audit logging for CBF enforcement bypass events

Test Coverage:
==============
1. Audit log configuration
2. Bypass event logging (CBF_ENFORCEMENT_DISABLED)
3. Restoration event logging (CBF_ENFORCEMENT_RESTORED)
4. Log file creation and permissions
5. JSON format output
6. Human-readable format output
7. Stack trace capture
8. Thread ID capture
9. Timestamp correctness
10. Multiple bypass events
11. Nested bypass events
12. Exception handling during bypass
13. Concurrent bypass events (thread safety)
"""

from __future__ import annotations


import pytest
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any

import torch

from kagami.core.safety import configure_audit_logging
from kagami.core.safety.universal_cbf_enforcer import (
    UniversalCBFEnforcer,
    cbf_enforcement_disabled,
    enforce_cbf,
)


@pytest.fixture(autouse=True)
def reset_enforcer() -> None:
    """Reset singleton and clear audit logger handlers before each test."""
    UniversalCBFEnforcer.reset_instance()

    # Clear audit logger handlers
    audit_logger = logging.getLogger("kagami.security.audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.NOTSET)

    yield

    # Cleanup after test
    UniversalCBFEnforcer.reset_instance()
    audit_logger.handlers.clear()


@pytest.fixture
def temp_log_file() -> str:
    """Create temporary log file path."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_path = f.name

    yield log_path

    # Cleanup
    if os.path.exists(log_path):
        os.remove(log_path)


@pytest.fixture
def temp_log_dir() -> Path:
    """Create temporary log directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir

    # Cleanup - recursively remove directory and all contents
    import shutil

    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def configure_test_audit_logging(log_file: str, json_format: bool = True) -> None:
    """Helper to configure audit logging for tests.

    Uses INFO level to capture both WARNING (DISABLED) and INFO (RESTORED) events.
    """
    configure_audit_logging(log_file=log_file, log_level=logging.INFO, json_format=json_format)


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


def test_configure_audit_logging_default_path(temp_log_dir: Path) -> None:
    """Test audit logging configuration with default path."""
    log_file = temp_log_dir / "cbf_audit.log"
    configure_audit_logging(log_file=str(log_file))

    # Check logger is configured
    audit_logger = logging.getLogger("kagami.security.audit")
    assert audit_logger.level == logging.WARNING
    assert len(audit_logger.handlers) == 1
    assert isinstance(audit_logger.handlers[0], logging.FileHandler)
    assert not audit_logger.propagate


def test_configure_audit_logging_creates_directory(temp_log_dir: Path) -> None:
    """Test that parent directory is created if it doesn't exist."""
    log_file = temp_log_dir / "nested" / "dir" / "audit.log"
    configure_audit_logging(log_file=str(log_file))

    assert log_file.parent.exists()
    assert log_file.parent.is_dir()


def test_configure_audit_logging_custom_level(temp_log_file: str) -> None:
    """Test configuration with custom log level."""
    configure_audit_logging(log_file=temp_log_file, log_level=logging.INFO)

    audit_logger = logging.getLogger("kagami.security.audit")
    assert audit_logger.level == logging.INFO


def test_configure_audit_logging_json_format(temp_log_file: str) -> None:
    """Test configuration with JSON format."""
    # Use INFO level to capture both DISABLED (WARNING) and RESTORED (INFO)
    configure_audit_logging(log_file=temp_log_file, json_format=True, log_level=logging.INFO)

    # Trigger a bypass event
    with cbf_enforcement_disabled(reason="test_json"):
        pass

    # Read and verify JSON format
    with open(temp_log_file) as f:
        lines = f.readlines()

    assert len(lines) >= 2  # DISABLED and RESTORED events

    # Parse first line (DISABLED event)
    log_entry = json.loads(lines[0])
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert log_entry["event"] == "CBF_ENFORCEMENT_DISABLED"
    assert "context" in log_entry


def test_configure_audit_logging_human_format(temp_log_file: str) -> None:
    """Test configuration with human-readable format."""
    configure_audit_logging(log_file=temp_log_file, json_format=False, log_level=logging.INFO)

    # Trigger a bypass event
    with cbf_enforcement_disabled(reason="test_human"):
        pass

    # Read and verify human format
    with open(temp_log_file) as f:
        content = f.read()

    assert "CBF_ENFORCEMENT_DISABLED" in content
    assert "CBF_ENFORCEMENT_RESTORED" in content
    assert "test_human" in content


def test_configure_audit_logging_multiple_calls(temp_log_file: str) -> None:
    """Test that multiple configuration calls don't create duplicate handlers."""
    configure_test_audit_logging(log_file=temp_log_file)
    configure_test_audit_logging(log_file=temp_log_file)
    configure_test_audit_logging(log_file=temp_log_file)

    audit_logger = logging.getLogger("kagami.security.audit")
    assert len(audit_logger.handlers) == 1


# =============================================================================
# BYPASS EVENT LOGGING TESTS
# =============================================================================


def test_bypass_event_logged(temp_log_file: str) -> None:
    """Test that bypass events are logged."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="test_bypass"):
        pass

    # Read log file
    with open(temp_log_file) as f:
        lines = f.readlines()

    assert len(lines) >= 2  # DISABLED and RESTORED

    # Parse DISABLED event
    disabled_event = json.loads(lines[0])
    assert disabled_event["event"] == "CBF_ENFORCEMENT_DISABLED"
    assert disabled_event["context"]["reason"] == "test_bypass"

    # Parse RESTORED event
    restored_event = json.loads(lines[1])
    assert restored_event["event"] == "CBF_ENFORCEMENT_RESTORED"


def test_bypass_event_contains_reason(temp_log_file: str) -> None:
    """Test that bypass events contain the reason."""
    configure_test_audit_logging(log_file=temp_log_file)

    reason = "controlled_exploration_for_RL_training"
    with cbf_enforcement_disabled(reason=reason):
        pass

    with open(temp_log_file) as f:
        content = f.read()

    assert reason in content


def test_bypass_event_contains_timestamp(temp_log_file: str) -> None:
    """Test that bypass events contain valid timestamps."""
    configure_test_audit_logging(log_file=temp_log_file)

    before = datetime.now(UTC)
    with cbf_enforcement_disabled(reason="test_timestamp"):
        pass
    after = datetime.now(UTC)

    # Read and parse first line
    with open(temp_log_file) as f:
        line = f.readline()

    log_entry = json.loads(line)
    timestamp_str = log_entry["context"]["timestamp"]

    # Parse ISO timestamp
    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    # Verify timestamp is in expected range (with tolerance)
    assert before <= timestamp <= after or (timestamp - before).total_seconds() < 1


def test_bypass_event_contains_stack_trace(temp_log_file: str) -> None:
    """Test that bypass events contain stack trace."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="test_stack"):
        pass

    with open(temp_log_file) as f:
        line = f.readline()

    log_entry = json.loads(line)
    stack_trace = log_entry["context"]["stack_trace"]

    assert isinstance(stack_trace, str)
    assert len(stack_trace) > 0
    assert "test_bypass_event_contains_stack_trace" in stack_trace
    assert "cbf_enforcement_disabled" in stack_trace


def test_bypass_event_contains_thread_id(temp_log_file: str) -> None:
    """Test that bypass events contain thread ID."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="test_thread"):
        pass

    with open(temp_log_file) as f:
        line = f.readline()

    log_entry = json.loads(line)
    thread_id = log_entry["context"]["thread_id"]

    assert isinstance(thread_id, int)
    assert thread_id == threading.get_ident()


def test_bypass_event_default_reason(temp_log_file: str) -> None:
    """Test bypass event with default reason."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled():  # No reason provided
        pass

    with open(temp_log_file) as f:
        line = f.readline()

    log_entry = json.loads(line)
    assert log_entry["context"]["reason"] == "exploration"


# =============================================================================
# RESTORATION EVENT LOGGING TESTS
# =============================================================================


def test_restoration_event_logged(temp_log_file: str) -> None:
    """Test that restoration events are logged."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="test_restore"):
        pass

    with open(temp_log_file) as f:
        lines = f.readlines()

    # Second line should be restoration event
    assert len(lines) >= 2
    restored_event = json.loads(lines[1])

    assert restored_event["event"] == "CBF_ENFORCEMENT_RESTORED"
    assert "timestamp" in restored_event["context"]
    assert restored_event["context"]["original_state"] is True


def test_restoration_event_after_exception(temp_log_file: str) -> None:
    """Test that restoration events are logged even after exceptions."""
    configure_test_audit_logging(log_file=temp_log_file)

    try:
        with cbf_enforcement_disabled(reason="test_exception"):
            raise ValueError("Test exception")
    except ValueError:
        pass

    with open(temp_log_file) as f:
        lines = f.readlines()

    # Should have both DISABLED and RESTORED events
    assert len(lines) >= 2

    disabled_event = json.loads(lines[0])
    assert disabled_event["event"] == "CBF_ENFORCEMENT_DISABLED"

    restored_event = json.loads(lines[1])
    assert restored_event["event"] == "CBF_ENFORCEMENT_RESTORED"


# =============================================================================
# MULTIPLE AND NESTED BYPASS TESTS
# =============================================================================


def test_multiple_sequential_bypasses(temp_log_file: str) -> None:
    """Test multiple sequential bypass events."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="first"):
        pass

    with cbf_enforcement_disabled(reason="second"):
        pass

    with cbf_enforcement_disabled(reason="third"):
        pass

    with open(temp_log_file) as f:
        lines = f.readlines()

    # Should have 6 events: 3 DISABLED + 3 RESTORED
    assert len(lines) >= 6

    # Check reasons
    assert "first" in lines[0]
    assert "second" in lines[2]
    assert "third" in lines[4]


def test_nested_bypasses(temp_log_file: str) -> None:
    """Test nested bypass events."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason="outer"):
        with cbf_enforcement_disabled(reason="inner"):
            pass

    with open(temp_log_file) as f:
        lines = f.readlines()

    # Should have 4 events: outer DISABLED, inner DISABLED, inner RESTORED, outer RESTORED
    assert len(lines) >= 4

    events = [json.loads(line) for line in lines]

    assert events[0]["event"] == "CBF_ENFORCEMENT_DISABLED"
    assert events[0]["context"]["reason"] == "outer"

    assert events[1]["event"] == "CBF_ENFORCEMENT_DISABLED"
    assert events[1]["context"]["reason"] == "inner"

    assert events[2]["event"] == "CBF_ENFORCEMENT_RESTORED"
    assert events[2]["context"]["reason"] == "inner"

    assert events[3]["event"] == "CBF_ENFORCEMENT_RESTORED"
    assert events[3]["context"]["reason"] == "outer"


# =============================================================================
# INTEGRATION WITH DECORATOR TESTS
# =============================================================================


def test_bypass_with_decorator(temp_log_file: str) -> None:
    """Test bypass logging with @enforce_cbf decorator."""
    configure_test_audit_logging(log_file=temp_log_file)

    @enforce_cbf(state_param="state", project_to_safe=False)
    def unsafe_function(state: torch.Tensor) -> torch.Tensor:
        return torch.ones(16) * 100.0

    state = torch.zeros(16)

    # Without bypass, would raise CBFViolationError (if barrier were trained)
    # With bypass, should pass through
    with cbf_enforcement_disabled(reason="decorator_test"):
        result = unsafe_function(state)

    assert torch.equal(result, torch.ones(16) * 100.0)

    # Check audit log
    with open(temp_log_file) as f:
        lines = f.readlines()

    assert len(lines) >= 2
    disabled_event = json.loads(lines[0])
    assert disabled_event["context"]["reason"] == "decorator_test"


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


def test_concurrent_bypass_events(temp_log_file: str) -> None:
    """Test concurrent bypass events from multiple threads."""
    configure_test_audit_logging(log_file=temp_log_file)

    def worker(thread_id: int) -> None:
        with cbf_enforcement_disabled(reason=f"thread_{thread_id}"):
            pass

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Read log file
    with open(temp_log_file) as f:
        lines = f.readlines()

    # Should have 10 events: 5 DISABLED + 5 RESTORED
    assert len(lines) >= 10

    # Verify all thread reasons are present
    content = "".join(lines)
    for i in range(5):
        assert f"thread_{i}" in content


def test_concurrent_bypass_thread_ids_unique(temp_log_file: str) -> None:
    """Test that concurrent bypasses record unique thread IDs."""
    configure_test_audit_logging(log_file=temp_log_file)

    thread_ids = []

    def worker() -> None:
        with cbf_enforcement_disabled(reason="concurrent"):
            pass

    threads = [threading.Thread(target=worker) for _ in range(3)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Parse log and extract thread IDs
    with open(temp_log_file) as f:
        lines = f.readlines()

    for line in lines:
        event = json.loads(line)
        if "thread_id" in event["context"]:
            thread_ids.append(event["context"]["thread_id"])

    # Should have multiple unique thread IDs
    unique_thread_ids = set(thread_ids)
    assert len(unique_thread_ids) >= 2


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


def test_bypass_without_configuration() -> None:
    """Test bypass works even without audit logging configuration."""
    # Don't configure audit logging
    with cbf_enforcement_disabled(reason="no_config"):
        pass  # Should not raise


def test_bypass_with_invalid_log_path() -> None:
    """Test configuration with invalid log path (permission issue)."""
    # Try to write to system directory (should fail gracefully)
    try:
        configure_audit_logging(log_file="/root/cannot_write_here.log")
    except (PermissionError, OSError):
        pass  # Expected on most systems

    # Bypass should still work even without proper audit configuration
    with cbf_enforcement_disabled(reason="invalid_path"):
        pass


def test_bypass_with_empty_reason(temp_log_file: str) -> None:
    """Test bypass with empty reason string."""
    configure_test_audit_logging(log_file=temp_log_file)

    with cbf_enforcement_disabled(reason=""):
        pass

    with open(temp_log_file) as f:
        line = f.readline()

    log_entry = json.loads(line)
    assert log_entry["context"]["reason"] == ""


def test_bypass_with_unicode_reason(temp_log_file: str) -> None:
    """Test bypass with Unicode characters in reason."""
    configure_test_audit_logging(log_file=temp_log_file)

    unicode_reason = "测试_тест_🔒"
    with cbf_enforcement_disabled(reason=unicode_reason):
        pass

    with open(temp_log_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Parse JSON to verify Unicode is properly encoded and decodable
    log_entry = json.loads(lines[0])
    assert log_entry["context"]["reason"] == unicode_reason


def test_log_file_appending(temp_log_file: str) -> None:
    """Test that log entries are appended, not overwritten."""
    configure_test_audit_logging(log_file=temp_log_file)

    # First bypass
    with cbf_enforcement_disabled(reason="first"):
        pass

    # Reconfigure (should append, not overwrite)
    configure_test_audit_logging(log_file=temp_log_file)

    # Second bypass
    with cbf_enforcement_disabled(reason="second"):
        pass

    with open(temp_log_file) as f:
        lines = f.readlines()

    # Should have all events
    content = "".join(lines)
    assert "first" in content
    assert "second" in content


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


@pytest.mark.skip(
    reason="pytest-benchmark not installed - install with: pip install pytest-benchmark"
)
@pytest.mark.benchmark
def test_bypass_logging_performance(temp_log_file: str) -> None:
    """Test performance impact of audit logging (requires pytest-benchmark)."""
    configure_test_audit_logging(log_file=temp_log_file)

    # Simple performance check without benchmark
    import time

    start = time.perf_counter()
    for _ in range(100):
        with cbf_enforcement_disabled(reason="perf_test"):
            pass
    elapsed = time.perf_counter() - start

    # Should complete 100 bypasses in reasonable time (< 1 second)
    assert elapsed < 1.0, f"100 bypasses took {elapsed:.3f}s (expected < 1.0s)"


# =============================================================================
# DOCUMENTATION TESTS
# =============================================================================


def test_audit_log_example_usage(temp_log_file: str) -> None:
    """Test the usage example from docstring."""
    # Configure at application startup
    configure_test_audit_logging(log_file=temp_log_file)

    # Use context manager with reason
    with cbf_enforcement_disabled(reason="controlled_exploration"):
        # Bypass event is logged to audit log
        unsafe_state = torch.ones(16) * 100.0

    # Verify log contains the operation
    with open(temp_log_file) as f:
        content = f.read()

    assert "controlled_exploration" in content
    assert "CBF_ENFORCEMENT_DISABLED" in content
    assert "CBF_ENFORCEMENT_RESTORED" in content
