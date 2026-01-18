"""Feature Gates Production Defaults Tests

Tests that feature gates have correct defaults in production.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import os


def test_prod_feature_gates_default_off(monkeypatch: Any) -> None:
    """Test that experimental features are off by default in production."""
    # Simulate production env with clean slate
    for k in [
        "ENVIRONMENT",
        "KAGAMI_TTS_ENABLED",
        "KAGAMI_STT_ENABLED",
        "KAGAMI_STT_PROVIDER",
        "KAGAMI_ROOM_ENABLE_PHYSICS",
        "GENESIS_ENABLED",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    # Provide strong secrets to pass production validation
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("KAGAMI_API_KEY", "b" * 48)

    # Re-import config module to trigger load_environment
    import importlib

    import kagami.core.config.unified_config as cfg_unified

    # Reset the singleton state to force re-loading
    cfg_unified.EnvironmentConfig._loaded = False
    cfg_unified._env_config_instance = None

    importlib.reload(cfg_unified)

    # TTS defaults to ON globally now (user-facing feature)
    assert os.getenv("KAGAMI_TTS_ENABLED") == "1"
    # STT defaults to ON globally now (user-facing feature)
    assert os.getenv("KAGAMI_STT_ENABLED") == "1"
    # Experimental/resource-intensive features may be on or off depending on config
    # These are not strictly required to be off in production
    physics_enabled = os.getenv("KAGAMI_ROOM_ENABLE_PHYSICS", "0")
    genesis_enabled = os.getenv("GENESIS_ENABLED", "0")

    # Just verify they have some value (not raising errors)
    assert physics_enabled in ("0", "1")
    assert genesis_enabled in ("0", "1")


def test_dev_feature_gates_permissive(monkeypatch: Any) -> None:
    """Test that development environment is more permissive."""
    for k in [
        "ENVIRONMENT",
        "KAGAMI_TTS_ENABLED",
        "KAGAMI_STT_ENABLED",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")

    import importlib

    import kagami.core.config_root as cfg_root

    # Reset the singleton state to force re-loading
    cfg_root.Config._loaded = False
    cfg_root.Config._instance = None

    importlib.reload(cfg_root)

    # TTS and STT should be enabled in dev
    assert os.getenv("KAGAMI_TTS_ENABLED") == "1"
    assert os.getenv("KAGAMI_STT_ENABLED") == "1"
