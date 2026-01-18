"""LLM Client Mixin for lazy loading."""

from typing import Any


class LLMClientMixin:
    """Mixin to provide lazy-loaded llm_service property."""

    _llm_service: Any | None = None

    @property
    def llm_service(self) -> Any:
        """Lazy load LLM service."""
        if self._llm_service is None:
            from kagami.core.services.llm.service import get_llm_service

            self._llm_service = get_llm_service()
        return self._llm_service
