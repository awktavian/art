"""LLM Service module."""

# Re-export unified cache for backward compatibility
from kagami.core.caching.response_cache import ResponseCache, hash_key

from .client_manager import ClientManager

# Frozen LLM service for goal generation and world model alignment
from .frozen_llm_service import (
    FrozenLLMService,
    batch_generate_text,
    generate_text,
    get_frozen_llm,
    get_frozen_llm_device,
    get_frozen_llm_service,
    get_frozen_llm_stats,
    is_frozen_llm_available,
)
from .observer import LLMObserver, get_observer
from .rate_limiter import AdaptiveLimiter, get_adaptive_limiter, get_llm_semaphore
from .service import KagamiOSLLMService, TaskType, get_llm_service

__all__ = [
    "AdaptiveLimiter",
    "ClientManager",
    # Frozen LLM
    "FrozenLLMService",
    "KagamiOSLLMService",
    "LLMObserver",
    "ResponseCache",
    "TaskType",
    "batch_generate_text",
    "generate_text",
    "get_adaptive_limiter",
    "get_frozen_llm",
    "get_frozen_llm_device",
    "get_frozen_llm_service",
    "get_frozen_llm_stats",
    "get_llm_semaphore",
    "get_llm_service",
    "get_observer",
    "hash_key",
    "is_frozen_llm_available",
]
