"""Tests for kagami/policy/constitution.py - Constitutional self-critique."""

from __future__ import annotations


from dataclasses import dataclass
from typing import Any


@dataclass
class MockIntent:
    """Mock intent for testing."""

    action: str = ""
    target: str = ""
    metadata: dict[str, Any] | None = None


class TestSelfCritique:
    """Tests for self_critique() function."""

    def test_self_critique_pass_benign_intent(self) -> None:
        """Test that benign intents pass constitutional check."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(action="read", target="file", metadata={})
        result, reason = self_critique(intent)

        assert result == "pass"
        assert reason == "ok"

    def test_self_critique_blocks_rm_rf(self) -> None:
        """Test that rm -rf in command is blocked."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="execute",
            target="shell",
            metadata={"command": "rm -rf /"},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "rm -rf" in reason

    def test_self_critique_blocks_drop_table(self) -> None:
        """Test that DROP TABLE is blocked."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="query",
            target="database",
            metadata={"command": "DROP TABLE users;"},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "drop table" in reason

    def test_self_critique_blocks_shutdown(self) -> None:
        """Test that shutdown command is blocked."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="shutdown",
            target="server",
            metadata={},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "shutdown" in reason

    def test_self_critique_blocks_sabotage(self) -> None:
        """Test that sabotage intent is blocked."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="sabotage",
            target="system",
            metadata={},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "sabotage" in reason

    def test_self_critique_blocks_excessive_tokens(self) -> None:
        """Test that max_tokens > 8000 fails."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="generate",
            target="text",
            metadata={"max_tokens": 10000},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert reason == "max_tokens_excess"

    def test_self_critique_allows_normal_tokens(self) -> None:
        """Test that max_tokens <= 8000 passes."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="generate",
            target="text",
            metadata={"max_tokens": 4000},
        )
        result, reason = self_critique(intent)

        assert result == "pass"
        assert reason == "ok"

    def test_self_critique_blocks_excessive_budget(self) -> None:
        """Test that budget_ms > 60000 fails."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="query",
            target="api",
            metadata={"budget_ms": 120000},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert reason == "budget_ms_excess"

    def test_self_critique_allows_normal_budget(self) -> None:
        """Test that budget_ms <= 60000 passes."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="query",
            target="api",
            metadata={"budget_ms": 30000},
        )
        result, reason = self_critique(intent)

        assert result == "pass"
        assert reason == "ok"

    def test_self_critique_handles_none_metadata(self) -> None:
        """Test graceful handling of None metadata."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(action="read", target="file", metadata=None)
        result, reason = self_critique(intent)

        assert result == "pass"
        assert reason == "ok"

    def test_self_critique_handles_missing_attributes(self) -> None:
        """Test handling of intent without expected attributes."""
        from kagami.policy.constitution import self_critique

        # Object without action/target/metadata
        class MinimalIntent:
            pass

        intent = MinimalIntent()
        result, reason = self_critique(intent)

        # Should pass since no blocked terms found
        assert result == "pass"
        assert reason == "ok"

    def test_self_critique_case_insensitive(self) -> None:
        """Test that blocked term detection is case-insensitive."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="SHUTDOWN",
            target="SERVER",
            metadata={},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "shutdown" in reason

    def test_self_critique_checks_notes_field(self) -> None:
        """Test that notes field in metadata is checked."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="read",
            target="file",
            metadata={"notes": "rm -rf everything"},
        )
        result, reason = self_critique(intent)

        assert result == "fail"
        assert "rm -rf" in reason

    def test_self_critique_handles_invalid_token_type(self) -> None:
        """Test graceful handling of non-integer max_tokens."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="generate",
            target="text",
            metadata={"max_tokens": "invalid"},
        )
        result, _reason = self_critique(intent)

        # Should pass through - parser skips invalid values
        assert result == "pass"

    def test_self_critique_handles_invalid_budget_type(self) -> None:
        """Test graceful handling of non-integer budget_ms."""
        from kagami.policy.constitution import self_critique

        intent = MockIntent(
            action="query",
            target="api",
            metadata={"budget_ms": "invalid"},
        )
        result, _reason = self_critique(intent)

        # Should pass through - parser skips invalid values
        assert result == "pass"
