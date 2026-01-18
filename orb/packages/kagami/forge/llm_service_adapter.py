"""Adapter to use KagamiOSLLMService from Forge.

Thin wrapper that makes KagamiOSLLMService compatible with Forge's
ForgeLLMBase interface.
"""

import logging
from typing import Any

from kagami.core.services.llm.service import TaskType, get_llm_service

logger = logging.getLogger(__name__)


class KagamiOSLLMServiceAdapter:
    """Adapter that wraps KagamiOSLLMService for Forge compatibility."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize adapter with KagamiOSLLMService."""
        # IMPORTANT: reuse the global LLM service so model clients are cached
        # across Forge modules and we don't repeatedly warm up providers/models.
        self.llm_service = get_llm_service()
        self.config = kwargs
        # Best-effort label for observability / backward compat expectations.
        self.model_name = str(
            self.config.get("model_name")
            or self.config.get("fast_model_name")
            or self.config.get("model_type")
            or "kagami-llm"
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the underlying LLM service."""
        if not self._initialized:
            await self.llm_service.initialize()
            self._initialized = True
            logger.info("KagamiOSLLMServiceAdapter initialized")

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text using KagamiOSLLMService.

        Args:
            prompt: Input prompt
            **kwargs: Additional generation parameters

        Returns:
            Generated text
        """
        if not self._initialized:
            await self.initialize()

        # Map Forge parameters to KagamiOSLLMService parameters
        max_tokens = kwargs.get("max_tokens", 1000)
        temperature = kwargs.get("temperature", 0.7)
        app_name = kwargs.get("app_name", "forge")

        # Delegate to KagamiOSLLMService
        result = await self.llm_service.generate(
            prompt=prompt,
            app_name=app_name,
            task_type=TaskType.CREATIVE,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return str(result)

    # Forge compatibility methods
    async def generate_text(self, prompt: str, **kwargs: Any) -> str:  # compatibility shim
        return await self.generate(prompt, **kwargs)

    async def reason(self, llm_request: Any) -> Any:  # compatibility shim for LLMRequest
        prompt = getattr(llm_request, "prompt", str(llm_request))
        text = await self.generate(prompt, max_tokens=getattr(llm_request, "max_tokens", 1000))
        try:
            # Import from the canonical type source to avoid import cycles:
            # core_integration -> llm_service_adapter (ForgeLLMAdapter)
            from .forge_llm_base import LLMResponse as _LLMResponse

            return _LLMResponse(content=text, model_name="kagami-llm", confidence=0.9)
        except Exception:

            class _Resp:
                def __init__(self, content: str) -> None:
                    self.content = content
                    self.model_name = "kagami-llm"
                    self.confidence = 0.9

            return _Resp(text)

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Chat using KagamiOSLLMService.

        Args:
            messages: List of message dicts with role and content
            **kwargs: Additional generation parameters

        Returns:
            Generated response
        """
        if not self._initialized:
            await self.initialize()

        # Convert messages to prompt (simple concatenation)
        prompt = "\n".join(f"{msg['role']}: {msg['content']}" for msg in messages)

        # Delegate to KagamiOSLLMService
        max_tokens = kwargs.get("max_tokens", 1000)
        temperature = kwargs.get("temperature", 0.7)
        app_name = kwargs.get("app_name", "forge")

        result = await self.llm_service.generate(
            prompt=prompt,
            app_name=app_name,
            task_type=TaskType.CONVERSATION,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return str(result)

    async def analyze_content(self, content: str, task: str) -> dict[str, Any]:
        """Analyze content using KagamiOSLLMService.

        Args:
            content: Content to analyze
            task: Analysis task description

        Returns:
            Analysis result
        """
        if not self._initialized:
            await self.initialize()

        prompt = f"Task: {task}\n\nContent: {content}\n\nAnalysis:"

        result = await self.llm_service.generate(
            prompt=prompt,
            app_name="forge",
            task_type=TaskType.REASONING,
            max_tokens=500,
            temperature=0.7,
        )

        return {
            "task": task,
            "analysis": str(result),
            "confidence": 0.9,
        }
