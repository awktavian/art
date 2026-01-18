"""User-Facing Model Selection — Simplified Model Choices for UI.

This module provides the USER-FACING model options, distinct from the internal
model resolution system. Users see simple names; the system maps to actual models.

Design Philosophy:
- Max 6 options to avoid choice paralysis
- Clear descriptions of strengths
- Auto as default (let Kagami choose)
- Colony-aligned colors for theming

Created: December 30, 2025
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# =============================================================================
# USER MODEL DEFINITIONS
# =============================================================================


class UserModelKey(str, Enum):
    """User-selectable model keys.

    These are the ONLY valid values for the `model` field in API requests.
    """

    AUTO = "auto"  # System chooses optimal model
    CLAUDE = "claude"  # Claude Sonnet (Anthropic)
    GPT4O = "gpt4o"  # GPT-4o (OpenAI)
    DEEPSEEK = "deepseek"  # DeepSeek V3 (best value)
    GEMINI = "gemini"  # Gemini 2.0 Pro (Google)
    LOCAL = "local"  # Local Transformers (offline)


@dataclass(frozen=True)
class UserModel:
    """User-facing model definition."""

    key: UserModelKey
    display_name: str
    icon: str  # Emoji or symbol
    description: str
    colony_color: str  # CSS color name for theming
    provider: str
    internal_model: str | None  # Actual model name (None = auto-resolved)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "key": self.key.value,
            "displayName": self.display_name,
            "icon": self.icon,
            "description": self.description,
            "colonyColor": self.colony_color,
            "provider": self.provider,
        }


# =============================================================================
# MODEL DEFINITIONS
# =============================================================================

USER_MODELS: dict[UserModelKey, UserModel] = {
    UserModelKey.AUTO: UserModel(
        key=UserModelKey.AUTO,
        display_name="Auto",
        icon="🤖",
        description="Let Kagami choose the best model",
        colony_color="crystal",
        provider="system",
        internal_model=None,
    ),
    UserModelKey.CLAUDE: UserModel(
        key=UserModelKey.CLAUDE,
        display_name="Claude",
        icon="◆",
        description="Balanced intelligence and safety",
        colony_color="nexus",
        provider="anthropic",
        internal_model="claude-sonnet-4-20250514",
    ),
    UserModelKey.GPT4O: UserModel(
        key=UserModelKey.GPT4O,
        display_name="GPT-4o",
        icon="◎",
        description="Strong reasoning and analysis",
        colony_color="beacon",
        provider="openai",
        internal_model="gpt-4o",
    ),
    UserModelKey.DEEPSEEK: UserModel(
        key=UserModelKey.DEEPSEEK,
        display_name="DeepSeek",
        icon="⟠",
        description="Best for code and value",
        colony_color="forge",
        provider="deepseek",
        internal_model="deepseek-chat",
    ),
    UserModelKey.GEMINI: UserModel(
        key=UserModelKey.GEMINI,
        display_name="Gemini",
        icon="◇",
        description="Long context and reasoning",
        colony_color="grove",
        provider="google",
        internal_model="gemini-2.0-flash",
    ),
    UserModelKey.LOCAL: UserModel(
        key=UserModelKey.LOCAL,
        display_name="Local",
        icon="⊙",
        description="Offline, private processing",
        colony_color="flow",
        provider="local",
        internal_model="Qwen/Qwen2.5-14B-Instruct",
    ),
}

# Ordered list for UI display
USER_MODELS_ORDERED: list[UserModel] = [
    USER_MODELS[UserModelKey.AUTO],
    USER_MODELS[UserModelKey.CLAUDE],
    USER_MODELS[UserModelKey.GPT4O],
    USER_MODELS[UserModelKey.DEEPSEEK],
    USER_MODELS[UserModelKey.GEMINI],
    USER_MODELS[UserModelKey.LOCAL],
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_user_model(key: str | UserModelKey) -> UserModel | None:
    """Get user model by key.

    Args:
        key: Model key string or enum

    Returns:
        UserModel if found, None otherwise
    """
    if isinstance(key, str):
        try:
            key = UserModelKey(key)
        except ValueError:
            return None
    return USER_MODELS.get(key)


def resolve_user_model_to_internal(key: str | UserModelKey | None) -> str | None:
    """Resolve user model key to internal model name.

    Args:
        key: User model key (or None for auto)

    Returns:
        Internal model name, or None to use system auto-selection
    """
    if key is None:
        return None

    model = get_user_model(key)
    if model is None:
        return None

    return model.internal_model


def is_valid_model_key(key: str | None) -> bool:
    """Check if a model key is valid.

    Args:
        key: Model key to check

    Returns:
        True if valid or None (auto), False otherwise
    """
    if key is None:
        return True
    try:
        UserModelKey(key)
        return True
    except ValueError:
        return False


def get_models_for_api() -> list[dict[str, Any]]:
    """Get list of models for API response.

    Returns:
        List of model dictionaries for JSON serialization
    """
    return [model.to_dict() for model in USER_MODELS_ORDERED]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "USER_MODELS",
    "USER_MODELS_ORDERED",
    "UserModel",
    "UserModelKey",
    "get_models_for_api",
    "get_user_model",
    "is_valid_model_key",
    "resolve_user_model_to_internal",
]
