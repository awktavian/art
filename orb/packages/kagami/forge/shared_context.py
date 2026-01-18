from __future__ import annotations

'Shared context management for Forge services.\n\nProvides simple, high-performance APIs used by tests:\n- initialize_context(...)\n- get_reasoning_strategy(CharacterAspect)\n- get_generation_order(list[CharacterAspect])\n\nAlso exposes symbols through a compatibility alias module path\n"Forge.core.shared_context" so tests can patch classes via that import path.\n'
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SharedContext:
    """Shared context for maintaining state across Forge operations."""

    def __init__(self, lazy_init: bool = False) -> None:
        self._context: dict[str, Any] = {}
        self._initialized: bool = not lazy_init
        self._reasoning_generator: FlexibleReasoningGenerator | None = None
        if not lazy_init:
            self.initialize()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context."""
        return self._context.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context."""
        self._context[key] = value

    def clear(self) -> None:
        """Clear all context."""
        self._context.clear()

    def initialize(self) -> None:
        """Initialize the shared context.

        FIXED (Dec 4, 2025): Removed artificial delay loop that was
        adding ~10ms to every context initialization.
        """
        self._initialized = True
        logger.debug("SharedContext initialized")

    @property
    def reasoning_generator(self) -> FlexibleReasoningGenerator:
        """Lazily create and cache a reasoning generator object."""
        if self._reasoning_generator is None:
            self._reasoning_generator = FlexibleReasoningGenerator()
        return self._reasoning_generator

    def initialize_context(self, **kwargs: Any) -> dict[str, Any]:
        """Initialize context data quickly for performance tests."""
        self._context.update(kwargs)
        return dict(self._context)

    def get_reasoning_strategy(self, aspect: Any) -> Any:
        """Return ReasoningStrategy for a CharacterAspect via O(1) map."""
        try:
            from .forge_llm_base import CharacterAspect, ReasoningStrategy

            strategy_map = {
                CharacterAspect.VISUAL_DESIGN: ReasoningStrategy.MULTIMODAL,
                CharacterAspect.PERSONALITY: ReasoningStrategy.INDUCTIVE,
                CharacterAspect.VOICE: ReasoningStrategy.CREATIVE,
                CharacterAspect.MOTION: ReasoningStrategy.ANALOGICAL,
                CharacterAspect.BELIEFS: ReasoningStrategy.DEDUCTIVE,
                CharacterAspect.BACKSTORY: ReasoningStrategy.CAUSAL,
                CharacterAspect.NARRATIVE_ROLE: ReasoningStrategy.ABDUCTIVE,
            }
            return strategy_map.get(aspect, ReasoningStrategy.INDUCTIVE)
        except Exception:
            return None

    def get_generation_order(self, aspects: list[Any]) -> list[Any]:
        """Return deterministic generation order prioritizing core aspects."""
        try:
            from .forge_llm_base import CharacterAspect

            priority = {
                CharacterAspect.VISUAL_DESIGN: 0,
                CharacterAspect.PERSONALITY: 1,
                CharacterAspect.BACKSTORY: 2,
                CharacterAspect.VOICE: 3,
                CharacterAspect.MOTION: 4,
                CharacterAspect.BELIEFS: 5,
                CharacterAspect.NARRATIVE_ROLE: 6,
            }
            return sorted(aspects, key=lambda a: priority.get(a, 999))
        except Exception:
            return list(aspects)


class FlexibleReasoningGenerator:
    def __init__(self) -> None:
        self._backends_ready: bool = False

    def _initialize_backends(self) -> None:
        self._backends_ready = True
        return None

    def get_available_models(self) -> dict[str, Any]:
        return {"fast": True, "medium": False, "primary": False}

    def _select_reasoning_for_aspect(self, aspect: str) -> str:
        mapping = {
            "visual_design": "multimodal",
            "personality": "inductive",
            "voice": "creative",
            "motion": "analogical",
            "beliefs": "deductive",
            "backstory": "causal",
            "narrative_role": "abductive",
        }
        return mapping.get(aspect, "inductive")
