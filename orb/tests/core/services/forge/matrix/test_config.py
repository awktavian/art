"""Tests for forge matrix config module."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os
from pathlib import Path
from unittest.mock import patch

from kagami.forge.matrix.config import (
    get_cache_root,
    load_forge_config,
)


class TestLoadForgeConfig:
    """Tests for load_forge_config function."""

    def test_load_default_config(self):
        """Test loading config with defaults."""
        config = load_forge_config()

        assert "require_unirig" in config
        assert "modules" in config
        assert "rigging" in config["modules"]
        assert config["modules"]["rigging"]["method"] == "unirig"

    def test_load_config_with_overrides(self):
        """Test loading config with provided overrides."""
        config = load_forge_config({"require_unirig": False, "custom_key": "value"})

        assert config["require_unirig"] is False
        assert config["custom_key"] == "value"
        assert "modules" in config

    def test_unirig_requirement_from_env(self):
        """Test UniRig requirement from environment."""
        with patch.dict(os.environ, {"FORGE_REQUIRE_UNIRIG": "0"}):
            config = load_forge_config()
            assert config["require_unirig"] is False

        with patch.dict(os.environ, {"FORGE_REQUIRE_UNIRIG": "1"}):
            config = load_forge_config()
            assert config["require_unirig"] is True


class TestGetCacheRoot:
    """Tests for get_cache_root function."""

    def test_returns_path(self):
        """Test that get_cache_root returns a Path."""
        cache_root = get_cache_root()
        assert isinstance(cache_root, Path)

    def test_cache_directory_exists(self):
        """Test that cache directory is created."""
        cache_root = get_cache_root()
        assert cache_root.exists()
        assert cache_root.is_dir()

    def test_cache_path_contains_forge(self):
        """Test cache path contains 'forge'."""
        cache_root = get_cache_root()
        assert "forge" in str(cache_root).lower()
