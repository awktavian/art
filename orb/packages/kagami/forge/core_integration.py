"""Core integration types for Forge services.

This module provides base components and types used across Forge modules.
Shared types (CharacterAspect, LLMRequest, LLMResponse, ReasoningStrategy,
CharacterContext) are re-exported from forge_llm_base.py as the canonical source.

Types unique to this module:
- BaseComponent, ForgeComponent: Base classes for Forge modules
- CharacterResult: Result wrapper for character processing
- ProcessingStatus: Processing state enum
- ForgeLLMAdapter: Config-based LLM integration with service adapter
"""

import logging
from enum import Enum
from typing import Any

# Re-export canonical types from forge_llm_base to avoid duplication
from .forge_llm_base import (
    CharacterAspect,
    CharacterContext,
    LLMRequest,
    LLMResponse,
    ReasoningStrategy,
)

logger = logging.getLogger(__name__)


class CharacterGenerationContext:
    """Context for character generation operations (distinct from LLM CharacterContext).

    Used for storing character metadata during the generation pipeline.
    """

    def __init__(
        self,
        character_id: str,
        concept: str,
        personality_traits: list[str] | None = None,
        genre: str | None = None,
    ) -> None:
        self.character_id = character_id
        self.concept = concept
        self.personality_traits = personality_traits if personality_traits is not None else []
        self.genre = genre


class BaseComponent:
    """Minimal base component for Forge modules."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._initialized = False

    def initialize(self, _config: Any = None) -> None:
        self._initialized = True


class CharacterResult:
    """Result wrapper for character processing operations."""

    def __init__(
        self,
        status: Any,
        aspect: Any,
        data: Any,
        metadata: Any = None,
        processing_time: float = 0.0,
        quality_score: float = 0.0,
        error: Any = None,
    ) -> None:
        self.status = status
        self.aspect = aspect
        self.data = data
        self.metadata = metadata if metadata is not None else {}
        self.processing_time = processing_time
        self.quality_score = quality_score
        self.error = error


class ProcessingStatus(Enum):
    """Processing state for character generation stages."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    OPTIMIZING = "optimizing"


class ForgeComponent(BaseComponent):
    """Base class for Forge module components."""

    def __init__(self, name: Any, config: Any = None) -> None:
        super().__init__(name)
        self.config = config if config is not None else {}

    def _get_required_config_fields(self) -> list[Any]:
        return []

    def _validate_config_specific(self, config: Any) -> bool:
        return True

    def _check_health(self) -> bool:
        return True

    def _get_status_specific(self) -> dict[str, Any]:
        return {}


class ForgeLLMAdapter:
    """Config-based LLM integration using KagamiOSLLMServiceAdapter.

    This is different from forge_llm_base.ForgeLLMBase (abstract base class).
    This version provides a concrete implementation using the service adapter.

    RENAMED (Dec 4, 2025): Was ForgeLLMBase, renamed to ForgeLLMAdapter to avoid
    collision with the abstract base class in forge_llm_base.py.
    """

    def __init__(self, config: Any = None) -> None:
        self.config = config if config is not None else {}
        self._llm_instance: Any = None

    async def initialize(self) -> bool:
        """Initialize real LLM connection using the factory."""
        try:
            from .llm_service_adapter import KagamiOSLLMServiceAdapter

            model_type = self.config.get("model_type", "qwen")
            provider = self.config.get("provider", "ollama")
            model_name = self.config.get("model_name", "qwen")
            fast_model_name = self.config.get("fast_model_name", "qwen3:7b")

            self._llm_instance = KagamiOSLLMServiceAdapter(
                model_type=model_type,
                provider=provider,
                model_name=model_name,
                fast_model_name=fast_model_name,
            )

            if hasattr(self._llm_instance, "initialize"):
                await self._llm_instance.initialize()

            return True

        except Exception as e:
            raise RuntimeError(f"Failed to initialize LLM: {e}") from None

    async def generate(self, request: Any) -> LLMResponse:
        """Generate response using real LLM."""
        if not self._llm_instance:
            raise RuntimeError("LLM not initialized. Call initialize() first.") from None

        if hasattr(self._llm_instance, "reason"):
            llm_request = LLMRequest(
                prompt=request.prompt,
                context=request.context,
                temperature=getattr(request, "temperature", 0.7),
                max_tokens=getattr(request, "max_tokens", 500),
            )

            response = await self._llm_instance.reason(llm_request)

            return LLMResponse(
                content=response.content,
                reasoning=response.reasoning,
                confidence=response.confidence,
                model_name=response.model_name,
                tokens_used=response.tokens_used,
            )
        else:
            content = await self._llm_instance.generate_text(
                request.prompt,
                temperature=getattr(request, "temperature", 0.7),
                max_tokens=getattr(request, "max_tokens", 500),
            )

            return LLMResponse(
                content=content,
                reasoning=None,
                confidence=1.0,
                model_name=self._llm_instance.model_name,
                tokens_used=0,
            )


__all__ = [
    # Unique to core_integration
    "BaseComponent",
    # Re-exported from forge_llm_base
    "CharacterAspect",
    "CharacterContext",
    "CharacterGenerationContext",
    "CharacterResult",
    "ForgeComponent",
    "ForgeLLMAdapter",
    "LLMRequest",
    "LLMResponse",
    "ProcessingStatus",
    "ReasoningStrategy",
]
