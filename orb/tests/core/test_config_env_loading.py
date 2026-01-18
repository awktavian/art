
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


import importlib
import os
from pathlib import Path


def _reset_config_module(monkeypatch: pytest.MonkeyPatch):
    """Helper to reload config module in a clean state."""
    # Ensure fresh environment for each scenario
    for k in [
        "ENVIRONMENT",
        "KAGAMI_SKIP_DOTENV",
        "KAGAMI_ALLOW_DEV_SECRET_GEN",
        "JWT_SECRET",
        "KAGAMI_API_KEY",
        "MODEL_CACHE_PATH",
        "DATABASE_URL",
        "CRDB_HOST",
        "CRDB_PORT",
        "CRDB_DATABASE",
    ]:
        monkeypatch.delenv(k, raising=False)

    # Clear lru_cache for get_user_kagami_dir as it might have cached the real home
    from kagami.core.utils.paths import get_user_kagami_dir

    get_user_kagami_dir.cache_clear()

    # Reload module
    if "kagami.core.config" in importlib.sys.modules:
        del importlib.sys.modules["kagami.core.config"]
    import kagami.core.config as cfg

    importlib.reload(cfg)
    return cfg


def test_loads_dotenv_from_home_when_not_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Prepare fake home with .kagami/.env
    fake_home = tmp_path / "home"
    env_dir = fake_home / ".kagami"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("UNIQUE_FLAG=loaded_from_dotenv\n", encoding="utf-8")

    # Point Path.home to our fake home
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    # Enable dotenv loading in tests
    monkeypatch.setenv("KAGAMI_USE_DOTENV", "1")

    _reset_config_module(monkeypatch)

    # UNIQUE_FLAG should be present from dotenv load
    assert os.getenv("UNIQUE_FLAG") == "loaded_from_dotenv"


def test_skips_dotenv_when_flag_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_home = tmp_path / "home2"
    env_dir = fake_home / ".kagami"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("UNIQUE_FLAG_SHOULD_NOT_LOAD=yes\n", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)
    # Ensure skip flag is set before any load and reload module directly
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    # Clear any prior value from previous tests
    monkeypatch.delenv("UNIQUE_FLAG_SHOULD_NOT_LOAD", raising=False)
    import importlib as _importlib

    import kagami.core.config as cfg

    _importlib.reload(cfg)

    # Should not load the flag
    assert os.getenv("UNIQUE_FLAG_SHOULD_NOT_LOAD") is None


def test_autogenerates_secrets_in_dev_test_when_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    # Skip dotenv to prevent loading defaults from .env files
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    # Simulate dev/test environment (not production)
    monkeypatch.setenv("ENVIRONMENT", "development")
    # Ensure secrets are absent prior to reload
    for k in ["JWT_SECRET", "KAGAMI_API_KEY"]:
        monkeypatch.delenv(k, raising=False)

    import importlib

    import kagami.core.config as cfg

    importlib.reload(cfg)

    jwt_secret = os.getenv("JWT_SECRET", "")
    api_key = os.getenv("KAGAMI_API_KEY", "")
    assert jwt_secret and len(jwt_secret) >= 32, f"JWT_SECRET too short: {len(jwt_secret)}"
    assert api_key and len(api_key) >= 16, f"API_KEY too short: {len(api_key)}"


def test_rejects_weak_keys_in_production(monkeypatch: pytest.MonkeyPatch):
    # Production requires strong secrets; ensure dotenv does not override
    monkeypatch.setenv("KAGAMI_SKIP_DOTENV", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "short")
    monkeypatch.setenv("KAGAMI_API_KEY", "short")
    import importlib as _importlib

    import kagami.core.config as cfg

    # First reload in tests sets a phase marker and returns to allow module import
    try:
        _importlib.reload(cfg)
    except RuntimeError:
        # Some environments may raise immediately; still proceed to assert fail-closed
        pass
    # Second reload should now raise and fail closed in production
    with pytest.raises(RuntimeError):
        _importlib.reload(cfg)


def test_get_database_url_defaults_to_cockroach_when_missing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # Clear DB env so code constructs fallback URL
    for k in [
        "DATABASE_URL",
        "CRDB_HOST",
        "CRDB_PORT",
        "CRDB_DATABASE",
    ]:
        monkeypatch.delenv(k, raising=False)

    # Point home so sqlite path resolves within tmp
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    cfg = _reset_config_module(monkeypatch)

    url = cfg.get_database_url()
    assert url.startswith("cockroachdb://root@"), url
    assert ":26257/kagami" in url


def test_get_model_cache_path_expands_user(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MODEL_CACHE_PATH", "~/forge_models")
    import importlib as _importlib

    import kagami.core.config as cfg

    _importlib.reload(cfg)
    resolved = cfg.get_model_cache_path()
    assert isinstance(resolved, Path)
    assert "~" not in str(resolved)
    assert str(resolved).endswith("forge_models")


def test_get_all_redacts_sensitive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JWT_SECRET", "super-secret")
    monkeypatch.setenv("KAGAMI_API_KEY", "super-key")
    cfg = _reset_config_module(monkeypatch)
    # get_all is exposed on the singleton instance `config`
    all_cfg = cfg.config.get_all()
    assert all_cfg.get("JWT_SECRET") == "***REDACTED***"
    assert all_cfg.get("KAGAMI_API_KEY") == "***REDACTED***"
