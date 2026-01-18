"""Utilities for handling optional external repositories.

External repos are optional dependencies for advanced features.
This module provides graceful error handling when they're missing.

鏡 K OS External Repository Management
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

# Import from central exception hierarchy
from kagami.core.exceptions import ExternalRepoError

logger = logging.getLogger(__name__)


class RepoStatus(NamedTuple):
    """Status of an external repository."""

    name: str
    path: Path
    available: bool
    error_message: str | None = None
    setup_command: str | None = None


def check_repo(
    repo_path: str | Path,
    repo_name: str,
    *,
    setup_command: str | None = None,
) -> RepoStatus:
    """Check if an external repository is available.

    Args:
        repo_path: Path to the repository directory
        repo_name: Human-readable name of the repository

    Returns:
        RepoStatus indicating availability
    """
    path = Path(repo_path) if isinstance(repo_path, str) else repo_path

    # Default setup hint (Makefile-driven in this repo)
    setup = setup_command or "make forge-setup"

    # Check if directory exists and has contents
    if not path.exists():
        return RepoStatus(
            name=repo_name,
            path=path,
            available=False,
            error_message=f"Directory not found: {path}",
            setup_command=setup,
        )

    if not any(path.iterdir()):
        return RepoStatus(
            name=repo_name,
            path=path,
            available=False,
            error_message=f"Directory is empty: {path}",
            setup_command=setup,
        )

    return RepoStatus(name=repo_name, path=path, available=True)


def check_hf_model(model_id: str, model_name: str) -> RepoStatus:
    """Check if a HuggingFace model is available in cache.

    Models auto-download on first use, so this checks cache presence.

    Args:
        model_id: HuggingFace model ID (e.g., "org/model")
        model_name: Human-readable name

    Returns:
        RepoStatus indicating cache presence
    """
    # HF cache location
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    model_cache_name = f"models--{model_id.replace('/', '--')}"
    model_path = hf_cache / model_cache_name

    if model_path.exists() and any(model_path.rglob("*")):
        return RepoStatus(
            name=model_name,
            path=model_path,
            available=True,
        )

    return RepoStatus(
        name=model_name,
        path=model_path,
        available=True,  # Available because models auto-download when needed
        error_message=None,
        setup_command="Model will auto-download on first use",
    )


# Convenience functions for specific repos
def check_motion_agent() -> RepoStatus:
    """Check Motion Agent repository availability."""
    return check_repo(
        "external/motion_agent_repo",
        "Motion Agent (Animation)",
        setup_command="make forge-motion",
    )


def check_unirig() -> RepoStatus:
    """Check UniRig availability (uses Hugging Face models).

    UniRig models auto-download from Hugging Face on first use,
    so we mark it as available if the placeholder directory exists.
    """
    # UniRig is special - it's just a placeholder, actual models in HF cache
    path = Path("external/unirig_repo")
    if not path.exists():
        return RepoStatus(
            name="UniRig (Character Rigging)",
            path=path,
            available=False,
            error_message="UniRig placeholder not found",
            setup_command="make forge-unirig",
        )

    # Check for HF cache to provide informative setup message
    hf_cache = Path.home() / ".cache" / "huggingface" / "models--VAST-AI--UniRig"
    models_cached = hf_cache.exists() and any(hf_cache.rglob("*"))

    # Always mark as available since models will auto-download on first use
    return RepoStatus(
        name="UniRig (Character Rigging)",
        path=path,
        available=True,  # Available because models auto-download when needed
        error_message=None,
        setup_command=(None if models_cached else "Models will auto-download on first use"),
    )


def check_all_repos() -> dict[str, RepoStatus]:
    """Check status of all external repositories.

    Returns:
        Dict mapping repo name to status
    """
    return {
        "motion_agent": check_motion_agent(),
        "unirig": check_unirig(),
    }


_CHECKERS: dict[str, Callable[[], RepoStatus]] = {
    "motion_agent": check_motion_agent,
    "unirig": check_unirig,
}


def get_repo_or_none(name: str) -> RepoStatus | None:
    """Return the repo status if known, otherwise None."""
    checker = _CHECKERS.get(name)
    if checker is None:
        logger.debug("No external repo configured for %s", name)
        return None
    status = checker()
    return status if status.available else None


def require_repo(name: str) -> RepoStatus:
    """Require that a given repo is available, raising if missing."""
    checker = _CHECKERS.get(name)
    if checker is None:
        raise ExternalRepoError(name, "make forge-setup")
    status = checker()
    if not status.available:
        raise ExternalRepoError(name, status.setup_command)
    return status


def graceful_repo_error(name: str) -> str:
    """Return a human friendly error message for missing repositories."""
    checker = _CHECKERS.get(name)
    if checker is None:
        return f"Optional repository '{name}' is not configured."
    status = checker()
    if status.available:
        return ""
    hint = status.setup_command or "make forge-setup"
    message = status.error_message or f"Repository '{name}' is unavailable."
    logger.warning("%s — set[Any] up via %s", message, hint)
    return f"{message} Set up via: {hint}"
