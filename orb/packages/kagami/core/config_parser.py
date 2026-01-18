"""Configuration parsing helpers.

Extracted from Config.load_environment to reduce complexity.
Part of Phase 4.1 complexity reduction.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level flag to prevent redundant log messages
_dotenv_logged: bool = False


def load_dotenv_file(env_path: Path) -> bool:
    """Load environment variables from .env file.

    Args:
        env_path: Path to .env file

    Returns:
        True if loaded successfully, False otherwise
    """
    global _dotenv_logged
    try:
        from dotenv import load_dotenv

        if env_path.exists():
            load_dotenv(env_path, override=False)
            if not _dotenv_logged:
                logger.info(f"Loaded environment from {env_path}")
                _dotenv_logged = True
            return True
    except ImportError:
        # Fallback to manual loading if python-dotenv not available
        if env_path.exists():
            return load_env_file_manual(env_path)

    return False


def load_env_file_manual(env_path: Path) -> bool:
    """Manually load environment variables from file.

    Args:
        env_path: Path to .env file

    Returns:
        True if loaded successfully
    """
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    os.environ[key] = value

        logger.info(f"Manually loaded environment from {env_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to load environment file {env_path}: {e}")
        return False


def normalize_environment_mode() -> str:
    """Normalize environment mode from various sources.

    Returns:
        Normalized environment mode ('development', 'staging', 'production', 'test')
    """
    # Check ENVIRONMENT first
    environment = os.getenv("ENVIRONMENT", "").strip().lower()

    # Fallback to KAGAMI_ENV
    if not environment:
        kagami_env = (os.getenv("KAGAMI_ENV") or "").strip().lower()
        alias_map = {
            "prod": "production",
            "stage": "staging",
            "dev": "development",
            "testing": "test",
        }
        environment = alias_map.get(kagami_env, kagami_env)

    # Default to development
    if not environment:
        environment = "development"

    return environment


def detect_environment_conflicts() -> None:
    """Detect and warn about conflicting environment variable settings."""
    try:
        env_vars = {
            "ENVIRONMENT": os.getenv("ENVIRONMENT"),
            "KAGAMI_ENV": os.getenv("KAGAMI_ENV"),
        }

        normalized = {k: (v or "").strip().lower() for k, v in env_vars.items()}
        vals = {v for v in normalized.values() if v}

        # Normalize aliases
        alias_map = {
            "prod": "production",
            "stage": "staging",
            "dev": "development",
            "testing": "test",
        }
        vals_norm = {alias_map.get(v, v) for v in vals}

        # Warn if conflicting (except development+test which is valid)
        if len(vals_norm) > 1 and not vals_norm <= {"development", "test"}:
            environment = normalize_environment_mode()
            logger.warning(
                f"Conflicting environment flags detected: {normalized}. "
                f"Using canonical ENVIRONMENT={environment}"
            )
    except Exception:
        pass


def set_environment_defaults(environment: str) -> None:
    """Set minimal default environment variables.

    Only sets variables that are actually read by the codebase.
    """
    os.environ.setdefault("KAGAMI_BOOT_MODE", "full")
    os.environ.setdefault("LOG_LEVEL", "INFO")

    # Model defaults (actually read by LLM clients)
    os.environ.setdefault("KAGAMI_BASE_MODEL", "Qwen/Qwen2.5-14B-Instruct")
    os.environ.setdefault("KAGAMI_TRANSFORMERS_MODEL_FAST", "Qwen/Qwen2.5-0.5B-Instruct")
    os.environ.setdefault("KAGAMI_TRANSFORMERS_MODEL_DEFAULT", "Qwen/Qwen2.5-14B-Instruct")
