"""
Centralized path utilities for Kagami.

All user data, caches, and runtime state live under ~/.kagami (KAGAMI_HOME).
Project source code is separate from user data.

Directory Structure:
    ~/.kagami/
    ├── data/           # Training datasets, downloaded data
    ├── cache/          # Ephemeral caches (can be deleted)
    │   └── models/     # Model cache
    ├── logs/           # Application logs
    ├── state/          # Persistent state (checkpoints, etc.)
    ├── browser-profile/# Browser automation profile
    └── patterns/       # Learned patterns
"""

import os
from functools import lru_cache
from pathlib import Path

# =============================================================================
# User Home Directory (~/.kagami)
# =============================================================================


@lru_cache(maxsize=1)
def get_kagami_home() -> Path:
    """
    Get the Kagami home directory (~/.kagami).

    Can be overridden by KAGAMI_HOME environment variable.
    Creates the directory if it doesn't exist.

    Returns:
        Path: Absolute path to kagami home directory
    """
    env_home = os.getenv("KAGAMI_HOME")
    if env_home:
        home = Path(env_home).expanduser().resolve()
    else:
        home = Path.home() / ".kagami"

    home.mkdir(parents=True, exist_ok=True)
    return home


# Alias for compatibility
get_user_kagami_dir = get_kagami_home


def get_kagami_data_dir() -> Path:
    """
    Get the data directory (~/.kagami/data).

    For training datasets, downloaded data, etc.
    """
    path = get_kagami_home() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_cache_dir() -> Path:
    """
    Get the cache directory (~/.kagami/cache).

    For ephemeral caches that can be safely deleted.
    """
    path = get_kagami_home() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_model_cache_dir() -> Path:
    """
    Get the model cache directory (~/.kagami/cache/models).

    Can be overridden by KAGAMI_MODEL_CACHE_DIR environment variable.
    """
    env_cache = os.getenv("KAGAMI_MODEL_CACHE_DIR")
    if env_cache:
        path = Path(env_cache).expanduser().resolve()
    else:
        path = get_kagami_cache_dir() / "models"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_logs_dir() -> Path:
    """
    Get the logs directory (~/.kagami/logs).
    """
    path = get_kagami_home() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_state_dir() -> Path:
    """
    Get the state directory (~/.kagami/state).

    For persistent state like checkpoints, learned patterns, etc.
    """
    path = get_kagami_home() / "state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_checkpoints_dir() -> Path:
    """
    Get the checkpoints directory (~/.kagami/state/checkpoints).
    """
    path = get_kagami_state_dir() / "checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_patterns_dir() -> Path:
    """
    Get the patterns directory (~/.kagami/patterns).
    """
    path = get_kagami_home() / "patterns"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_kagami_browser_profile_dir() -> Path:
    """
    Get the browser profile directory (~/.kagami/browser-profile).
    """
    path = get_kagami_home() / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


# =============================================================================
# Project Source Directory (for development)
# =============================================================================


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    Get the project root directory (source code location).

    This is the monorepo root, NOT user data.
    Result is cached for performance.

    Returns:
        Path: Absolute path to project root
    """
    # This file is at: packages/kagami/core/utils/paths.py
    # Project root is 4 levels up (packages/kagami/core/utils -> root)
    return Path(__file__).parent.parent.parent.parent.parent.resolve()


# Alias for compatibility
get_repo_root = get_project_root


@lru_cache(maxsize=1)
def get_kagami_package_root() -> Path:
    """
    Get the kagami package root directory.

    Returns:
        Path: Absolute path to packages/kagami/ directory
    """
    return Path(__file__).parent.parent.parent.resolve()


def get_project_config_dir() -> Path:
    """
    Get the project config directory (project_root/config).

    For project-level configuration files (not user data).
    """
    return get_project_root() / "config"
