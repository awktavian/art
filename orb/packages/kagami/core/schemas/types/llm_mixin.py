"""
LLMServiceMixin for K os.

Consolidates duplicate llm_service property found across 7+ classes in the codebase:
- core/reporting/receipt_reporter.py
- core/personality/emotional_intelligence.py
- core/agents/dynamic_evolution.py
- core/agents/micro_agent_factory.py
- core/intents/enhanced_parser.py
- core/continuous/continuous_mind.py
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from kagami.core.services.llm.service import LLMService  # type: ignore[attr-defined]


class LLMServiceMixin:
    """
    Mixin providing lazy LLM service access.

    Classes inheriting this mixin get access to `self.llm_service` property
    which lazily initializes the LLM service on first access.

    Usage:
        class MyClass(LLMServiceMixin):
            async def process(self):
                response = await self.llm_service.generate("prompt")
    """

    _llm_service: Optional["LLMService"] = None

    @property
    def llm_service(self) -> "LLMService":
        """
        Get the LLM service instance (lazy initialization).

        Returns:
            LLMService: Shared LLM service instance
        """
        if self._llm_service is None:
            from kagami.core.services.llm.service import get_llm_service

            self._llm_service = get_llm_service()
        return self._llm_service

    def _reset_llm_service(self) -> None:
        """
        Reset the LLM service instance (primarily for testing).

        This forces re-initialization on next access.
        """
        self._llm_service = None
