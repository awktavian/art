"""Base LLM integration for Forge services."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from kagami.core.rules_loader import build_prompt_prelude

logger = logging.getLogger(__name__)


class CharacterAspect(Enum):
    """Different aspects of character that can be analyzed."""

    VISUAL_DESIGN = "visual_design"
    PERSONALITY = "personality"
    VOICE = "voice"
    MOTION = "motion"
    BELIEFS = "beliefs"
    BACKSTORY = "backstory"
    NARRATIVE_ROLE = "narrative_role"


class ReasoningStrategy(Enum):
    """Different reasoning strategies for LLM operations."""

    MULTIMODAL = "multimodal"
    INDUCTIVE = "inductive"
    CREATIVE = "creative"
    ANALOGICAL = "analogical"
    DEDUCTIVE = "deductive"
    CAUSAL = "causal"
    ABDUCTIVE = "abductive"


@dataclass
class CharacterContext:
    """Context information for character processing."""

    character_id: str
    name: str
    description: str = ""
    aspect: CharacterAspect = CharacterAspect.VISUAL_DESIGN
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LLMRequest:
    """Request structure for LLM operations.

    Supports both general LLM calls (prompt-first) and aspect-specific generation
    (aspect-first for character aspects like personality, voice, etc.).
    """

    prompt: str
    context: CharacterContext | dict[str, Any] | None = None
    temperature: float = 0.5
    max_tokens: int = 500
    metadata: dict[str, Any] | None = None
    aspect: CharacterAspect | None = None
    require_json: bool = False
    template: str | None = None  # Optional template name for structured generation

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LLMResponse:
    """Response structure from LLM operations."""

    content: str
    reasoning: str | None = None
    confidence: float = 1.0
    model_name: str | None = None
    tokens_used: int = 0

    def __post_init__(self) -> None:
        if self.model_name is None:
            raise ValueError("model_name is required")


@dataclass
class PromptTemplate:
    """Template for generating prompts."""

    template: str
    variables: list[str]
    category: str = "general"

    def format(self, **kwargs: Any) -> str:
        """Format template with provided variables."""
        return self.template.format(**kwargs)


class ForgeLLMBase(ABC):
    """Base class for LLM integrations in Forge."""

    def __init__(self, model_name: str = "default") -> None:
        self.model_name = model_name
        self.initialized = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the LLM provider/client and return True on success."""
        ...

    @abstractmethod
    async def generate_text(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt.

        Implementations must call a real provider. In tests, echo fallback
        may be enabled via LLM_PROVIDER=echo config. Production must not use
        placeholders.
        """
        ...

    @abstractmethod
    async def analyze_content(self, content: str, task: str) -> dict[str, Any]:
        """Analyze content for specific task.

        Implementations must call a real provider. In tests, echo fallback
        may be enabled via LLM_PROVIDER=echo config.
        """
        ...

    @staticmethod
    def _get_prompt_prelude() -> str:
        try:
            import os as _os

            app = _os.getenv("KAGAMI_PROMPT_APP") or "Forge"
            prelude: str = str(build_prompt_prelude(app_name=app))
            return prelude if prelude.endswith("\n\n") else prelude + "\n"
        except Exception:
            return "System Contract (synchronized):\n- Prefer structured outputs; respect token budgets; declare tools/scope.\n- Keep responses concise and professional.\n\n"

    @staticmethod
    def _inject_prelude_if_missing(text: str) -> str:
        if not isinstance(text, str) or not text:
            return ForgeLLMBase._get_prompt_prelude()
        if "System Contract (synchronized):" in text:
            return text
        return ForgeLLMBase._get_prompt_prelude() + text


__all__ = [
    "CharacterAspect",
    "CharacterContext",
    "ForgeLLMBase",
    "LLMRequest",
    "LLMResponse",
    "PromptTemplate",
    "ReasoningStrategy",
]
