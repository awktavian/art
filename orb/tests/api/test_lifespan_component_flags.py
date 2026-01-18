"""Lifespan Component Flags Tests

Tests boot action component enablement flags.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import importlib
import os

boot_actions = importlib.import_module("kagami.boot.actions")


def _set_modes(monkeypatch: pytest.MonkeyPatch, *, full: bool, test: bool) -> None:
    """Patch boot-mode helpers to deterministic values."""
    monkeypatch.setattr(boot_actions, "is_full_mode", lambda: full, raising=False)
    monkeypatch.setattr(boot_actions, "is_test_mode", lambda: test, raising=False)


class TestLoaderEnablement:
    """Tests for loader enablement logic."""

    def teardown_method(self, _method):
        """Clean up env vars after each test."""
        os.environ.pop("TEST_FLAG", None)

    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that explicit env override wins over defaults."""
        _set_modes(monkeypatch, full=True, test=False)
        monkeypatch.setenv("TEST_FLAG", "0")
        assert (
            boot_actions._should_enable_loader("TEST_FLAG", default_full=True) is False
        ), "Explicit env override must win even in Full mode"

    def test_full_mode_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that full mode uses default_full."""
        _set_modes(monkeypatch, full=True, test=False)
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert boot_actions._should_enable_loader("TEST_FLAG", default_full=True) is True

    def test_test_mode_default_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that test mode uses default_test."""
        _set_modes(monkeypatch, full=False, test=True)
        monkeypatch.delenv("TEST_FLAG", raising=False)
        enabled = boot_actions._should_enable_loader(
            "TEST_FLAG", default_full=True, default_test=True
        )
        assert enabled is True

    def test_test_mode_default_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that test mode defaults to off when default_test is False."""
        _set_modes(monkeypatch, full=False, test=True)
        monkeypatch.delenv("TEST_FLAG", raising=False)
        enabled = boot_actions._should_enable_loader(
            "TEST_FLAG", default_full=True, default_test=False
        )
        assert enabled is False
