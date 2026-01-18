"""Shared LLM types to prevent circular dependencies.

Contains model selection and configuration types shared between
model_resolver.py and runtime clients.

UNIFIED MODEL CONFIGURATION (December 2025):
============================================
This module is the SINGLE SOURCE OF TRUTH for:
1. Model name resolution (no more scattered os.getenv calls)
2. TaskType enum (consolidated from 5 duplicate definitions)
3. Provider selection types
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache

# =============================================================================
# UNIFIED MODEL NAME RESOLUTION
# =============================================================================


@lru_cache(maxsize=1)
def get_default_model() -> str:
    """Get default LLM model name from environment.

    Priority (highest to lowest):
    1. KAGAMI_JOINT_LLM_MODEL - For joint world model training
    2. KAGAMI_TRANSFORMERS_MODEL_DEFAULT - For general transformers
    3. KAGAMI_BASE_MODEL - Base model fallback
    4. Hardcoded default

    Returns:
        Model name string (e.g., "Qwen/Qwen2.5-14B-Instruct")
    """
    return (
        os.getenv("KAGAMI_JOINT_LLM_MODEL")
        or os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT")
        or os.getenv("KAGAMI_BASE_MODEL")
        or "Qwen/Qwen2.5-14B-Instruct"
    )


@lru_cache(maxsize=1)
def get_coder_model() -> str:
    """Get coder-optimized model name.

    Returns:
        Model name string for code generation tasks
    """
    return os.getenv("KAGAMI_TRANSFORMERS_MODEL_CODER") or "Qwen/Qwen3-Coder-30B-A3B-Instruct"


@lru_cache(maxsize=1)
def get_fast_model() -> str:
    """Get fast/lightweight model name.

    Returns:
        Model name string for low-latency tasks
    """
    return os.getenv("KAGAMI_TRANSFORMERS_MODEL_FAST") or "Qwen/Qwen3-14B"


@lru_cache(maxsize=1)
def get_reasoning_model() -> str:
    """Get reasoning-optimized model name.

    Returns:
        Model name string for chain-of-thought reasoning
    """
    return os.getenv("KAGAMI_TRANSFORMERS_MODEL_REASONING") or "Qwen/Qwen3-Coder-30B-A3B-Instruct"


@lru_cache(maxsize=1)
def get_test_model() -> str:
    """Get lightweight test model name.

    Used in test mode to avoid loading heavy models.

    Returns:
        Model name string for testing
    """
    return os.getenv("KAGAMI_TRANSFORMERS_MODEL_TEST") or "sshleifer/tiny-gpt2"


def is_test_mode() -> bool:
    """Check if running in test/echo mode.

    Returns:
        True if KAGAMI_TEST_ECHO_LLM is set[Any] or PYTEST_CURRENT_TEST is present
    """
    if os.getenv("KAGAMI_TEST_ECHO_LLM", "0").lower() in ("1", "true", "yes"):
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    return False


def resolve_model_for_task(task_type: TaskType | None = None) -> str:
    """Resolve optimal model name for a given task type.

    Args:
        task_type: Optional TaskType enum for task-aware selection

    Returns:
        Model name string
    """
    if is_test_mode():
        return get_test_model()

    if task_type is None:
        return get_default_model()

    # Task-type aware model selection
    code_tasks = {TaskType.EXTRACTION, TaskType.CONFIGURATION}
    reasoning_tasks = {TaskType.REASONING, TaskType.PLANNING, TaskType.ANALYSIS}
    fast_tasks = {TaskType.CLASSIFICATION, TaskType.PREDICTION}

    if task_type in code_tasks:
        return get_coder_model()
    if task_type in reasoning_tasks:
        return get_reasoning_model()
    if task_type in fast_tasks:
        return get_fast_model()

    return get_default_model()


# =============================================================================
# UNIFIED TASK TYPE ENUM
# =============================================================================


class TaskType(Enum):
    """Unified LLM task types for optimal model selection.

    CANONICAL DEFINITION - Import from here, not elsewhere.
    Consolidates duplicate TaskType definitions from:
    - kagami/core/services/llm/service.py
    - kagami/core/routing/llm_task_classifier.py
    - kagami/core/routing/multi_model_router.py
    """

    # Core generation tasks
    INSIGHT = auto()
    RECOMMENDATION = auto()
    PERSONALIZATION = auto()
    CONVERSATION = auto()
    CREATIVE = auto()

    # Reasoning tasks
    REASONING = auto()
    PLANNING = auto()
    ANALYSIS = auto()

    # Processing tasks
    SUMMARY = auto()
    EXTRACTION = auto()
    CONFIGURATION = auto()
    CLASSIFICATION = auto()
    PREDICTION = auto()

    # Action tasks
    OPTIMIZATION = auto()
    EXECUTION = auto()
    SYNTHESIS = auto()

    # Code-specific (from multi_model_router)
    CODE_GENERATION = auto()
    CODE_REVIEW = auto()
    CODE_EXPLANATION = auto()
    CODE_DEBUGGING = auto()

    # Research tasks (from llm_task_classifier)
    MATH_PROOF = auto()
    SCIENCE_RESEARCH = auto()
    WEB_RESEARCH = auto()
    CREATIVE_WRITING = auto()
    DATA_ANALYSIS = auto()
    GENERAL_REASONING = auto()
    FAST_QUERY = auto()

    # Multimodal tasks (from multi_model_router)
    MULTIMODAL = auto()
    MULTIMODAL_VISION = auto()
    MULTIMODAL_AUDIO = auto()

    # Domain-specific tasks (from multi_model_router)
    LONG_CONTEXT = auto()
    FINANCIAL_ANALYSIS = auto()
    MEDICAL_RESEARCH = auto()
    MULTILINGUAL = auto()

    # Agent tasks
    TOOL_SELECTION = auto()
    MEMORY_RETRIEVAL = auto()
    GOAL_PLANNING = auto()


# =============================================================================
# MODEL SELECTION TYPES
# =============================================================================


@dataclass(frozen=True)
class ModelSelection:
    """Resolved model selection for LLM service.

    Attributes:
        provider: Provider name (local/transformers, api (OpenAI-compatible), gemini, etc.)
        model_name: Model identifier
        base_url: Optional base URL for API
        is_heavy: Whether this is a computationally heavy model
    """

    provider: str
    model_name: str
    base_url: str | None = None
    is_heavy: bool = False


@dataclass(frozen=True)
class ImageModelSelection:
    """Resolved model selection for image generation.

    Attributes:
        provider: Provider name (stability, openai, etc.)
        model_name: Model identifier
        size_policy: Image size policy (auto, small, medium, large)
    """

    provider: str
    model_name: str
    size_policy: str = "auto"


__all__ = [
    "ImageModelSelection",
    # Selection types
    "ModelSelection",
    # Task types (CANONICAL - import from here)
    "TaskType",
    "get_coder_model",
    # Model resolution (CANONICAL - use these instead of os.getenv)
    "get_default_model",
    "get_fast_model",
    "get_reasoning_model",
    "get_test_model",
    "is_test_mode",
    "resolve_model_for_task",
]
