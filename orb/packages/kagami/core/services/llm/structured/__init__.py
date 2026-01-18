"""Structured JSON generation with constrained decoding.

This module provides enhanced structured generation capabilities:
- Grammar-constrained decoding (Outlines)
- Multiple generation strategies
- JSON repair and validation
- Semantic validation beyond Pydantic
"""

from kagami.core.services.llm.structured.enhanced import (
    EnhancedStructuredGenerator,
    GenerationResult,
    GenerationStrategy,
    JSONRepairModule,
    RepairStrategy,
    SemanticValidator,
    UserFeedback,
    generate_structured_enhanced,
    get_enhanced_generator,
    select_model_for,
)

__all__ = [
    # Core classes
    "EnhancedStructuredGenerator",
    "GenerationResult",
    "GenerationStrategy",
    "JSONRepairModule",
    "RepairStrategy",
    "SemanticValidator",
    "UserFeedback",
    # Public API
    "generate_structured_enhanced",
    "get_enhanced_generator",
    "select_model_for",
]
